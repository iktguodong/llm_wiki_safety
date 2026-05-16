"""培训大纲生成。"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

from backend.config import config
from backend.services.llm import llm_service
from .models import ContentPack, SourceRef, TrainingOutline, TrainingOutlineSection, TrainingOutlineSlide

ALLOWED_STYLES = {"standard_training", "management_briefing", "frontline_shift_training"}
OUTLINE_MAX_TOKENS = 1500
OUTLINE_TIMEOUT_SECONDS = 60.0


def _coerce_style(value: str) -> str:
    return value if value in ALLOWED_STYLES else "standard_training"


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    return cleaned


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = _strip_fence(text)
    for start_char in ("{", "["):
        start = cleaned.find(start_char)
        if start == -1:
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


def _shorten(text: str, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _split_points(text: str) -> list[str]:
    candidates = []
    for line in re.split(r"[\n。；;]+", text):
        item = re.sub(r"\s+", " ", line).strip(" -•\t")
        if item:
            candidates.append(item[:48])
    return candidates[:5]


def _slide_type_from_text(title: str, body: str) -> str:
    joined = f"{title} {body}"
    if any(k in joined for k in ["风险", "隐患", "危险", "事故"]):
        return "risk_scene"
    if any(k in joined for k in ["法规", "制度", "职责", "条款", "要求"]):
        return "legal_requirement"
    if any(k in joined for k in ["流程", "步骤", "处置", "报警", "疏散", "应急"]):
        return "workflow"
    if any(k in joined for k in ["检查", "清单", "核对", "排查"]):
        return "checklist"
    if any(k in joined for k in ["案例", "情景", "讨论"]):
        return "case_discussion"
    if any(k in joined for k in ["措施", "防护", "管控", "控制"]):
        return "control_measures"
    if any(k in joined for k in ["测验", "复盘", "答题"]):
        return "quiz"
    return "content"


def _visual_type_for_slide_type(slide_type: str) -> str:
    return {
        "legal_requirement": "table",
        "workflow": "process_flow",
        "risk_scene": "risk_matrix",
        "checklist": "checklist",
        "case_discussion": "qa",
        "control_measures": "cards",
        "quiz": "qa",
        "summary": "cards",
        "cover": "cards",
        "agenda": "cards",
    }.get(slide_type, "two_column")


def _safety_level_for_slide_type(slide_type: str) -> str:
    return {
        "risk_scene": "attention",
        "case_discussion": "attention",
        "legal_requirement": "warning",
        "quiz": "attention",
    }.get(slide_type, "normal")


def _refs_for_chunks(chunks, start: int, step: int, max_refs: int = 3):
    refs = []
    for chunk in chunks[start::step]:
        refs.extend(chunk.source_refs)
        if len(refs) >= max_refs:
            break
    return refs[:max_refs]


def _chunk_groups(content_pack: ContentPack, group_count: int) -> list[list[Any]]:
    chunks = list(content_pack.chunks)
    if not chunks:
        return [[] for _ in range(group_count)]
    groups: list[list[Any]] = [[] for _ in range(group_count)]
    for idx, chunk in enumerate(chunks):
        groups[idx % group_count].append(chunk)
    return groups


def _slide_from_group(
    *,
    slide_no: int,
    title: str,
    group: list[Any],
    slide_type: str = "content",
    layout_hint: str | None = None,
    notes_prefix: str | None = None,
    source_refs: list[SourceRef] | None = None,
) -> TrainingOutlineSlide:
    body_text = "\n".join(chunk.text for chunk in group if getattr(chunk, "text", "")).strip()
    points = []
    for chunk in group:
        text = str(getattr(chunk, "text", "")).strip()
        points.extend(_split_points(text))
    if not points:
        points = [title]
    if len(points) > 5:
        points = points[:5]
    notes = notes_prefix or (points[0] if points else title)
    if body_text:
        notes = f"{notes}\n\n{_shorten(body_text, 240)}"
    refs = source_refs if source_refs is not None else [ref for chunk in group for ref in getattr(chunk, "source_refs", [])][:3]
    if not refs:
        refs = []
    return TrainingOutlineSlide(
        id=f"slide-{uuid.uuid4().hex[:8]}",
        slide_no=slide_no,
        title=title,
        key_points=points,
        notes=notes,
        layout_hint=layout_hint,
        slide_type=slide_type,  # type: ignore[arg-type]
        source_refs=refs,
        visual_type=_visual_type_for_slide_type(slide_type),  # type: ignore[arg-type]
        safety_level=_safety_level_for_slide_type(slide_type),  # type: ignore[arg-type]
    )


def _slide_to_section(slide: TrainingOutlineSlide) -> TrainingOutlineSection:
    return TrainingOutlineSection(
        id=slide.id,
        title=slide.title,
        goal=slide.notes or slide.title,
        key_points=list(slide.key_points),
        estimated_minutes=0,
        source_refs=list(slide.source_refs),
    )


def _default_outline(content_pack: ContentPack, settings: dict[str, Any]) -> TrainingOutline:
    target_slide_count = max(3, int(settings.get("slide_count") or 8))
    include_quiz = bool(settings.get("include_quiz", True))
    content_slide_count = max(1, target_slide_count - 3 - (1 if include_quiz and target_slide_count >= 5 else 0))

    groups = _chunk_groups(content_pack, content_slide_count)
    slides: list[TrainingOutlineSlide] = []

    slides.append(
        TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=1,
            title=str(settings.get("title") or content_pack.title or settings.get("topic") or content_pack.topic),
            key_points=[
                f"受众：{settings.get('audience') or content_pack.audience}",
                f"时长：{int(settings.get('duration_minutes') or content_pack.duration_minutes or 60)} 分钟",
                f"风格：{_coerce_style(str(settings.get('style') or 'standard_training'))}",
            ],
            notes="封面页，直接说明主题、受众和本次培训定位。",
            layout_hint="封面",
            slide_type="cover",
            source_refs=[],
            visual_type="cards",
            safety_level="normal",
        )
    )

    agenda_titles = []
    for idx in range(min(5, content_slide_count)):
        chunk_group = groups[idx] if idx < len(groups) else []
        if chunk_group:
            agenda_titles.append(chunk_group[0].title)
    if not agenda_titles:
        agenda_titles = ["背景与目标", "重点风险", "关键流程", "现场措施"]
    slides.append(
        TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=2,
            title="目录",
            key_points=agenda_titles[:5],
            notes="先讲背景，再讲风险与要求，最后落到执行动作。",
            layout_hint="目录",
            slide_type="agenda",
            source_refs=[],
            visual_type="cards",
            safety_level="normal",
        )
    )

    current_no = 3
    for idx, group in enumerate(groups):
        if not group:
            group_title = f"核心内容 {idx + 1}"
        else:
            group_title = str(getattr(group[0], "title", f"核心内容 {idx + 1}"))
        body_text = " ".join(str(getattr(chunk, "text", "")) for chunk in group).strip()
        slide_type = _slide_type_from_text(group_title, body_text)
        if slide_type == "content" and idx % 3 == 1:
            slide_type = "workflow"
        elif slide_type == "content" and idx % 3 == 2:
            slide_type = "checklist"
        slides.append(
            _slide_from_group(
                slide_no=current_no,
                title=group_title[:40],
                group=group,
                slide_type=slide_type,
                layout_hint="正文页",
                notes_prefix=_shorten(body_text, 140) if body_text else group_title,
            )
        )
        current_no += 1

    if include_quiz and target_slide_count >= 5:
        quiz_refs = [ref for chunk in content_pack.chunks for ref in chunk.source_refs][:3]
        slides.append(
            TrainingOutlineSlide(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=current_no,
                title="测验与复盘",
                key_points=[
                    "发现异常后先做什么",
                    "哪些情况必须立即上报",
                    "岗位动作如何落实",
                ],
                notes="建议把答案写成可口头复述的简短表达，方便现场提问。",
                layout_hint="测验页",
                slide_type="quiz",
                source_refs=quiz_refs,
                visual_type="qa",
                safety_level="attention",
            )
        )
        current_no += 1

    slides.append(
        TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=current_no,
            title="总结与行动清单",
            key_points=[
                "复盘关键风险点",
                "确认岗位职责和上报路径",
                "检查控制措施是否到位",
                "形成整改清单并闭环",
            ],
            notes="总结页，落到可执行的现场动作和后续闭环。",
            layout_hint="总结页",
            slide_type="summary",
            source_refs=[ref for chunk in content_pack.chunks for ref in chunk.source_refs][:4],
            visual_type="cards",
            safety_level="normal",
        )
    )

    # 如目标页数较小，尽量裁剪到目标页数；若较大，保留全部内容页便于后续编辑
    if len(slides) > target_slide_count:
        keep = slides[: max(2, target_slide_count - 1)] + [slides[-1]]
        slides = keep

    for idx, slide in enumerate(slides, start=1):
        slide.slide_no = idx

    sections = [_slide_to_section(slide) for slide in slides if slide.slide_type not in {"cover", "agenda", "summary", "quiz"}]
    warnings = list(content_pack.warnings)
    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
        warnings.append("该内容主要由模型生成，未绑定企业原文来源")

    return TrainingOutline(
        id=f"ol-{uuid.uuid4().hex[:10]}",
        title=str(settings.get("title") or content_pack.title or settings.get("topic") or content_pack.topic),
        topic=str(settings.get("topic") or content_pack.topic),
        audience=str(settings.get("audience") or content_pack.audience),
        duration_minutes=int(settings.get("duration_minutes") or content_pack.duration_minutes or 60),
        style=_coerce_style(str(settings.get("style") or "standard_training")),
        slides=slides,
        sections=sections,
        warnings=warnings,
    )


def _build_prompt(content_pack: ContentPack, settings: dict[str, Any]) -> str:
    chunks_text = []
    for chunk in content_pack.chunks[:8]:
        refs = ", ".join((ref.title or ref.source_id or ref.source_type) for ref in chunk.source_refs[:3])
        chunks_text.append(f"### {chunk.title}\n来源：{refs}\n{chunk.text[:1200]}")
    content_preview = "\n\n".join(chunks_text)[:12000]
    return f"""
请基于以下输入材料生成安全生产培训PPT逐页大纲，输出严格 JSON，不要 Markdown，不要代码块。

要求：
- 只输出一个 JSON 对象
- slides 必须是一个列表，尽量贴合目标页数
- 每个 slide 包含 title、key_points、notes、layout_hint、slide_type
- 不要编造企业事实、制度条款或来源
- 适合后续直接转成 PPT

输入设置：
{json.dumps(settings, ensure_ascii=False, indent=2)}

输入材料：
{content_preview}

请输出 JSON 对象，结构示例：
{{
  "title": "培训标题",
  "topic": "主题",
  "audience": "受众",
  "duration_minutes": 30,
  "style": "standard_training",
  "slides": [
    {{
      "title": "页面标题",
      "key_points": ["要点1", "要点2"],
      "notes": "讲稿备注",
      "layout_hint": "布局提示",
      "slide_type": "content"
    }}
  ],
  "warnings": ["可选警告"]
}}
""".strip()


def _outline_from_llm(data: dict[str, Any], content_pack: ContentPack, settings: dict[str, Any]) -> TrainingOutline | None:
    raw_slides = data.get("slides") or []
    if not isinstance(raw_slides, list) or not raw_slides:
        return None

    slides: list[TrainingOutlineSlide] = []
    chunk_groups = _chunk_groups(content_pack, max(1, len(raw_slides)))
    for idx, slide in enumerate(raw_slides):
        if not isinstance(slide, dict):
            continue
        group = chunk_groups[idx] if idx < len(chunk_groups) else []
        slide_type = str(slide.get("slide_type") or "content")
        if slide_type not in {
            "cover",
            "agenda",
            "content",
            "workflow",
            "risk_scene",
            "legal_requirement",
            "control_measures",
            "case_discussion",
            "checklist",
            "quiz",
            "summary",
        }:
            slide_type = "content"
        title = str(slide.get("title") or f"页面 {idx + 1}")
        body_text = " ".join(str(getattr(chunk, "text", "")) for chunk in group)
        points = [str(item).strip()[:48] for item in slide.get("key_points", []) if str(item).strip()][:5]
        if not points:
            points = _split_points(body_text) or [title]
        notes = str(slide.get("notes") or "")
        if not notes and points:
            notes = points[0]
        layout_hint = str(slide.get("layout_hint") or "")
        slides.append(
            TrainingOutlineSlide(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=idx + 1,
                title=title,
                key_points=points,
                notes=notes or None,
                layout_hint=layout_hint or None,
                slide_type=slide_type,  # type: ignore[arg-type]
                source_refs=[ref for chunk in group for ref in chunk.source_refs][:3],
                visual_type=_visual_type_for_slide_type(slide_type),  # type: ignore[arg-type]
                safety_level=_safety_level_for_slide_type(slide_type),  # type: ignore[arg-type]
            )
        )

    if len(slides) < 3:
        return None

    sections = [_slide_to_section(slide) for slide in slides if slide.slide_type not in {"cover", "agenda", "summary", "quiz"}]
    warnings = list(content_pack.warnings) + [str(w) for w in data.get("warnings", []) if str(w).strip()]
    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
        warnings.append("该内容主要由模型生成，未绑定企业原文来源")

    return TrainingOutline(
        id=f"ol-{uuid.uuid4().hex[:10]}",
        title=str(data.get("title") or settings.get("topic") or content_pack.topic),
        topic=str(data.get("topic") or settings.get("topic") or content_pack.topic),
        audience=str(data.get("audience") or settings.get("audience") or content_pack.audience),
        duration_minutes=int(data.get("duration_minutes") or settings.get("duration_minutes") or content_pack.duration_minutes or 60),
        style=_coerce_style(str(data.get("style") or settings.get("style") or "standard_training")),
        slides=slides,
        sections=sections,
        warnings=warnings,
    )


async def generate_outline(content_pack: ContentPack, settings: Any, llm_client=llm_service) -> TrainingOutline:
    settings_dict = _as_dict(settings)
    style = str(settings_dict.get("style") or "standard_training")
    topic = str(settings_dict.get("title") or content_pack.title or settings_dict.get("topic") or content_pack.topic)
    audience = str(settings_dict.get("audience") or content_pack.audience)
    duration_minutes = int(settings_dict.get("duration_minutes") or content_pack.duration_minutes or 60)

    model_roles = config.get("models", {}).get("model_roles", {})
    model_id = model_roles.get("ppt_gen") or config.get("current_model_id")
    providers = config.get("models", {}).get("providers", [])
    model_available = False
    if model_id:
        for provider in providers:
            if any(model.get("id") == model_id for model in provider.get("models", [])) and provider.get("api_key"):
                model_available = True
                break

    if model_available:
        try:
            prompt = _build_prompt(content_pack, settings_dict)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是安全生产培训课程设计专家。请基于输入材料生成企业安全培训逐页大纲。"
                        "要求：优先依据输入材料，不编造企业事实；如果只有用户主题提示，可以扩展通用培训结构，"
                        "但不得伪造法规条款、企业制度、岗位职责或来源；输出严格 JSON；适合后续转成 PPT。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            response = await asyncio.wait_for(
                llm_client.chat_sync(
                    messages,
                    model_id=model_id,
                    temperature=0.2,
                    max_tokens=OUTLINE_MAX_TOKENS,
                ),
                timeout=OUTLINE_TIMEOUT_SECONDS,
            )
            data = _extract_json(response or "")
            if data:
                outline = _outline_from_llm(data, content_pack, settings_dict)
                if outline:
                    return outline
            content_pack.warnings.append("LLM 大纲生成结果未通过结构解析，已回退到规则大纲")
        except asyncio.TimeoutError:
            content_pack.warnings.append(
                f"LLM 大纲生成超时（{OUTLINE_TIMEOUT_SECONDS:.0f} 秒），已回退到规则大纲"
            )
        except asyncio.CancelledError:
            # 必须显式重新抛出，不能在 except Exception 中被吞没
            # Python <3.11: CancelledError 继承自 Exception，会被 except Exception 捕获
            # Python 3.11+: CancelledError 继承自 BaseException，但仍需显式传递
            raise
        except Exception as exc:
            content_pack.warnings.append(f"LLM 大纲生成失败，已回退到规则大纲：{str(exc)[:200]}")

    outline = _default_outline(content_pack, settings_dict)
    outline.title = topic
    outline.topic = topic
    outline.audience = audience
    outline.duration_minutes = duration_minutes
    outline.style = _coerce_style(style)
    return outline
