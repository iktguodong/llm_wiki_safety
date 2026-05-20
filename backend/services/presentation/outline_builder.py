"""培训大纲生成。"""

from __future__ import annotations

import asyncio
import json
import re
import uuid

from backend.config import config
from backend.services.llm import llm_service
from .models import ContentPack, SourceRef, TrainingOutline, TrainingOutlinePoint, TrainingOutlineSection, TrainingOutlineSlide

ALLOWED_STYLES = {"standard_training", "management_briefing", "frontline_shift_training"}
OUTLINE_MAX_TOKENS = 3000
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


def _point_from_text(text: str) -> TrainingOutlinePoint:
    cleaned = re.sub(r"\s+", " ", str(text)).strip(" -•\t")
    if not cleaned:
        return TrainingOutlinePoint(title="要点", description="")
    for sep in ("：", ":", " - ", "—", "，", ","):
        if sep in cleaned:
            title, description = cleaned.split(sep, 1)
            title = title.strip()[:28] or cleaned[:28]
            description = description.strip()[:96]
            return TrainingOutlinePoint(title=title, description=description)
    return TrainingOutlinePoint(title=cleaned[:28], description=cleaned[:96] if len(cleaned) > 28 else "")


def _points_from_texts(items: list[str]) -> list[TrainingOutlinePoint]:
    points = [_point_from_text(item) for item in items if str(item).strip()]
    return points[:5]


def _point_label(point: TrainingOutlinePoint) -> str:
    return f"{point.title}：{point.description}" if point.description else point.title


def _cover_slide(settings: dict[str, Any], content_pack: ContentPack) -> TrainingOutlineSlide:
    title = str(settings.get("title") or settings.get("topic") or content_pack.title or content_pack.topic)
    report_date = str(settings.get("report_date") or "").strip()
    presenter = str(settings.get("presenter") or "").strip()
    audience = str(settings.get("audience") or content_pack.audience or "").strip()
    points: list[TrainingOutlinePoint] = []
    if report_date:
        points.append(TrainingOutlinePoint(title="汇报时间", description=report_date))
    if presenter:
        points.append(TrainingOutlinePoint(title="汇报人", description=presenter))
    if audience:
        points.append(TrainingOutlinePoint(title="汇报对象", description=audience))
    if not points:
        points = [TrainingOutlinePoint(title="材料主题", description=title)]
    return TrainingOutlineSlide(
        id=f"slide-{uuid.uuid4().hex[:8]}",
        slide_no=1,
        title=title,
        points=points,
        key_points=[_point_label(point) for point in points],
        notes=None,
        layout_hint="封面",
        slide_type="cover",
        source_refs=[],
        visual_type="cards",
        safety_level="normal",
    )


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
    point_models = _points_from_texts(points)
    notes = notes_prefix or (points[0] if points else title)
    refs = source_refs if source_refs is not None else [ref for chunk in group for ref in getattr(chunk, "source_refs", [])][:3]
    if not refs:
        refs = []
    return TrainingOutlineSlide(
        id=f"slide-{uuid.uuid4().hex[:8]}",
        slide_no=slide_no,
        title=title,
        points=point_models,
        key_points=[_point_label(point) for point in point_models],
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
    content_slide_count = max(1, target_slide_count - 1)

    groups = _chunk_groups(content_pack, content_slide_count)
    slides: list[TrainingOutlineSlide] = [_cover_slide(settings, content_pack)]

    for idx, group in enumerate(groups):
        if not group:
            if idx == content_slide_count - 1:
                group_title = "总结与行动清单"
                fallback_points = ["复盘关键风险点", "确认岗位职责和上报路径", "形成整改清单并闭环"]
            else:
                group_title = f"核心内容 {idx + 1}"
                fallback_points = [group_title]
        else:
            group_title = str(getattr(group[0], "title", f"核心内容 {idx + 1}"))
            fallback_points = []
        body_text = " ".join(str(getattr(chunk, "text", "")) for chunk in group).strip()
        slide_type = _slide_type_from_text(group_title, body_text)
        if idx == content_slide_count - 1 and content_slide_count >= 3:
            slide_type = "summary"
        if slide_type == "content" and idx % 3 == 1:
            slide_type = "workflow"
        elif slide_type == "content" and idx % 3 == 2:
            slide_type = "checklist"
        if group:
            slides.append(
                _slide_from_group(
                    slide_no=len(slides) + 1,
                    title=group_title[:40],
                    group=group,
                    slide_type=slide_type,
                    layout_hint="正文页",
                    notes_prefix=_shorten(body_text, 140) if body_text else group_title,
                )
            )
        else:
            point_models = _points_from_texts(fallback_points)
            slides.append(
                TrainingOutlineSlide(
                    id=f"slide-{uuid.uuid4().hex[:8]}",
                    slide_no=len(slides) + 1,
                    title=group_title[:40],
                    points=point_models,
                    key_points=[_point_label(point) for point in point_models],
                    notes=None,
                    layout_hint="正文页",
                    slide_type=slide_type,  # type: ignore[arg-type]
                    source_refs=[],
                    visual_type=_visual_type_for_slide_type(slide_type),  # type: ignore[arg-type]
                    safety_level=_safety_level_for_slide_type(slide_type),  # type: ignore[arg-type]
                )
            )

    # 如目标页数较小，尽量裁剪到目标页数；若较大，保留全部内容页便于后续编辑
    if len(slides) > target_slide_count:
        keep = slides[: max(2, target_slide_count - 1)] + [slides[-1]]
        slides = keep

    for idx, slide in enumerate(slides, start=1):
        slide.slide_no = idx

    sections = [_slide_to_section(slide) for slide in slides if slide.slide_type not in {"cover", "summary"}]
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
    requested_slide_count = max(3, int(settings.get("slide_count") or 8))
    content_slide_count = max(1, requested_slide_count - 1)
    title = str(settings.get("title") or settings.get("topic") or content_pack.title or content_pack.topic)
    requirements = str(settings.get("requirements") or settings.get("requirement") or settings.get("topic") or "")
    return f"""
请基于以下输入材料生成安全生产培训 PPT 的内容页大纲，输出严格 JSON，不要 Markdown，不要代码块。

要求：
- 只输出一个 JSON 对象
- slides 必须是一个列表，严格生成 {content_slide_count} 个内容页
- 不要生成封面页；封面页由系统根据用户填写信息自动生成
- 每个 slide 只包含 title 和 points
- points 是列表，每项只包含 title 和 description
- 每页 3 到 5 个 points，description 用一句短句说明
- 不要编造企业事实、制度条款或来源
- 适合后续直接转成 PPT

输入设置：
{json.dumps({
    "title": title,
    "audience": settings.get("audience") or content_pack.audience,
    "requirements": requirements,
    "style": settings.get("style") or "standard_training",
    "total_slide_count": requested_slide_count,
    "content_slide_count": content_slide_count,
}, ensure_ascii=False, indent=2)}

输入材料：
{content_preview}

请输出 JSON 对象，结构示例：
{{
  "slides": [
    {{
      "title": "页面标题",
      "points": [
        {{"title": "要点标题", "description": "要点简述"}}
      ]
    }}
  ]
}}
""".strip()


def _outline_from_llm(data: dict[str, Any], content_pack: ContentPack, settings: dict[str, Any]) -> TrainingOutline | None:
    raw_slides = data.get("slides") or []
    if not isinstance(raw_slides, list) or not raw_slides:
        return None

    content_raw_slides = [
        slide
        for slide in raw_slides
        if not (isinstance(slide, dict) and str(slide.get("slide_type") or "").strip() == "cover")
    ]
    slides: list[TrainingOutlineSlide] = [_cover_slide(settings, content_pack)]
    chunk_groups = _chunk_groups(content_pack, max(1, len(content_raw_slides)))
    for idx, slide in enumerate(content_raw_slides):
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
        point_models: list[TrainingOutlinePoint] = []
        raw_points = slide.get("points")
        if isinstance(raw_points, list):
            for item in raw_points:
                if isinstance(item, dict):
                    point_title = str(item.get("title") or "").strip()
                    point_description = str(item.get("description") or item.get("desc") or "").strip()
                    if point_title or point_description:
                        point_models.append(
                            TrainingOutlinePoint(
                                title=(point_title or point_description)[:28],
                                description=point_description[:96],
                            )
                        )
                elif str(item).strip():
                    point_models.append(_point_from_text(str(item)))
        if not point_models:
            old_points = [str(item).strip() for item in slide.get("key_points", []) if str(item).strip()]
            point_models = _points_from_texts(old_points or _split_points(body_text) or [title])
        layout_hint = str(slide.get("layout_hint") or "")
        slides.append(
            TrainingOutlineSlide(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=len(slides) + 1,
                title=title,
                points=point_models[:5],
                key_points=[_point_label(point) for point in point_models[:5]],
                notes=None,
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
        title=str(data.get("title") or settings.get("title") or settings.get("topic") or content_pack.topic),
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
        # 在发起 LLM 调用前让出控制权，使 task.cancel() 能及时生效
        await asyncio.sleep(0)
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
            requested_slide_count = max(3, int(settings_dict.get("slide_count") or 8))
            max_tokens = max(OUTLINE_MAX_TOKENS, requested_slide_count * 140)
            response: str | None = None
            chat_events = getattr(llm_client, "chat_events", None)
            if callable(chat_events):
                parts: list[str] = []

                async def _collect_stream() -> str:
                    async for event in chat_events(
                        messages,
                        model_id=model_id,
                        stream=True,
                        temperature=0.2,
                        max_tokens=max_tokens,
                    ):
                        event_type = str(event.get("type") or "")
                        if event_type == "chunk":
                            content = str(event.get("content") or "")
                            if content:
                                parts.append(content)
                        elif event_type == "error":
                            message = str(event.get("message") or "请求错误").strip()
                            raise ValueError(message or "请求错误")
                    return "".join(parts)

                response = await asyncio.wait_for(_collect_stream(), timeout=OUTLINE_TIMEOUT_SECONDS)
            else:
                response = await asyncio.wait_for(
                    llm_client.chat_sync(
                        messages,
                        model_id=model_id,
                        temperature=0.2,
                        max_tokens=max_tokens,
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
