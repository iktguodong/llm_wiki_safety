"""培训大纲生成：基于素材通过 LLM 构建结构化大纲。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from threading import Event
from typing import Any

from backend.config import config
from backend.models import (
    TrainingOutline,
    TrainingOutlinePoint,
    TrainingOutlineSection,
    TrainingOutlineSlide,
    TrainingSourceRef,
)
def _to_api_ref(ref) -> TrainingSourceRef:
    """将内部 SourceRef 转换为 API 模型 TrainingSourceRef。"""
    if isinstance(ref, TrainingSourceRef):
        return ref
    data = ref.model_dump() if hasattr(ref, "model_dump") else dict(ref)
    return TrainingSourceRef(**data)
from backend.services.llm import llm_service
from backend.services.presentation.content_pack import ContentPack
from backend.services.presentation.project_store import update_job_progress

logger = logging.getLogger(__name__)

OUTLINE_TIMEOUT_SECONDS = 60.0
ALLOWED_STYLES = {"standard_training", "management_briefing", "frontline_shift_training"}


def _coerce_style(value: str) -> str:
    return value if value in ALLOWED_STYLES else "standard_training"


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _shorten(text: str, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _cover_slide(settings: dict[str, Any], pack: ContentPack) -> TrainingOutlineSlide:
    title = settings.get("title") or settings.get("topic") or pack.title or pack.topic
    report_date = str(settings.get("report_date") or "").strip()
    presenter = str(settings.get("presenter") or "").strip()
    audience = str(settings.get("audience") or pack.audience or "").strip()
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
        key_points=[f"{p.title}：{p.description}" if p.description else p.title for p in points],
        slide_type="cover",
        visual_type="cards",
        safety_level="normal",
    )


def _split_points(text: str) -> list[str]:
    candidates = []
    for line in re.split(r"[\n。；;]+", text):
        item = re.sub(r"\s+", " ", line).strip(" -•\t")
        if item:
            candidates.append(item[:80])
    return candidates[:5]


def _point_from_text(text: str) -> TrainingOutlinePoint:
    cleaned = re.sub(r"\s+", " ", str(text)).strip(" -•\t")
    if not cleaned:
        return TrainingOutlinePoint(title="要点")
    for sep in ("：", ":", " - ", "—", "，", ","):
        if sep in cleaned:
            title, description = cleaned.split(sep, 1)
            return TrainingOutlinePoint(title=title.strip()[:32], description=description.strip()[:160])
    return TrainingOutlinePoint(title=cleaned[:32], description=cleaned[:160] if len(cleaned) > 32 else "")


def _paragraphs_from_value(value: Any) -> list[str]:
    if isinstance(value, str):
        chunks = [value]
    elif isinstance(value, list):
        chunks = [str(item) for item in value]
    else:
        chunks = []

    paragraphs: list[str] = []
    for chunk in chunks:
        cleaned = re.sub(r"\s+", " ", str(chunk)).strip(" -•\t")
        if not cleaned:
            continue
        if "\n" in chunk:
            pieces = [re.sub(r"\s+", " ", part).strip(" -•\t") for part in re.split(r"\n{1,2}", chunk) if part.strip()]
            paragraphs.extend([piece for piece in pieces if piece])
        else:
            paragraphs.append(cleaned)
    return paragraphs[:4]


def _points_from_texts(items: list[str]) -> list[TrainingOutlinePoint]:
    return [_point_from_text(item) for item in items if item.strip()][:5]



def _visual_type(slide_type: str) -> str:
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


def _safety_level(slide_type: str) -> str:
    return {
        "risk_scene": "attention",
        "case_discussion": "attention",
        "legal_requirement": "warning",
        "quiz": "attention",
    }.get(slide_type, "normal")


def _chunk_groups(pack: ContentPack, group_count: int) -> list[list[Any]]:
    chunks = list(pack.chunks)
    if not chunks:
        return [[] for _ in range(max(1, group_count))]
    groups: list[list[Any]] = [[] for _ in range(max(1, group_count))]
    for idx, chunk in enumerate(chunks):
        groups[idx % len(groups)].append(chunk)
    return groups


def _build_llm_prompt(pack: ContentPack, settings: dict[str, Any]) -> str:
    chunks_text = []
    for chunk in pack.chunks[:20]:
        refs = ", ".join((r.title or r.source_id or r.source_type) for r in chunk.source_refs[:2])
        chunks_text.append(f"### {chunk.title}\n来源：{refs}\n{chunk.text[:1500]}")
    preview = "\n\n".join(chunks_text)[:16000]
    content_count = max(1, int(settings.get("slide_count") or 8) - 1)
    title = settings.get("title") or settings.get("topic") or pack.title or pack.topic
    audience = settings.get("audience") or pack.audience or "相关岗位人员"
    req = settings.get("requirements") or settings.get("requirement") or ""
    focus_areas = settings.get("focus_areas") or []
    return f"""你是一位专业的安全生产内容策划专家，擅长将材料整理为适用于培训、汇报和分享场景的PPT逐页文字稿。请根据以下输入材料生成逐页文字稿内容。

## 核心要求

1. **基于材料，不编造**：严格遵守输入材料中的事实和数据，不得编造企业制度条款、事故案例、法规条文、公司名称、品牌口号、页脚文案或岗位职责。如果材料信息不足，可以概括通用安全知识，但必须标注「通用知识」。
2. **逻辑连贯**：整体内容应从导入→主体→总结形成完整的叙事逻辑，页面之间有递进关系。
3. **针对性强**：内容要贴合「{audience}」的岗位特点和认知水平，重点突出与受众相关的实操内容、管理要求和落地动作。
4. **写成 PPT 文字稿**：每个页面必须包含 `title`、`subtitle`、`body`。`subtitle` 是一句概括性副标题，`body` 不是提纲而是可以直接放进 PPT 的段落正文。每个 body 段落至少写成 1-2 句完整表达，最好包含“是什么 / 为什么 / 怎么做 / 注意什么”中的两项以上，不要只写名词、短语或口号。
5. **内容要够充实**：每页保留 2-4 个 body 段落，必要时可到 5 个；每个段落要写出足够展开的说明，让页面看起来像培训/汇报文字稿，而不是只列标题。
6. **段落结构清晰**：`subtitle` 用来承接这一页的中心判断或关键结论，`body` 用来展开论证、动作要求、现场场景和注意事项。段落之间要有递进关系，不要只是同义改写。
7. **避免重复**：不要在标题、subtitle 和 body 里重复同一句话，不要把同一条内容在一页里写两遍，不要输出模板化品牌词。
8. **不要编号化表达**：不要把页面标题写成“1/2/3/4”或“第一、第二、第三”这种纯序号式表达；每页标题要有明确语义，点题即可。

## 输出格式要求

- 只输出一个严格 JSON 对象，不要 Markdown 代码块
- slides 必须是数组，严格生成 {content_count} 个内容页
- 不要封面页（封面页由系统自动生成）
- 每个 slide 包含 `title`、`subtitle`、`body` 字段
- `subtitle` 必须有，且要比 title 更像一句结论
- `body` 是数组，每项都是一段完整正文，建议 2-4 段；如果某页内容更复杂，可以到 5 段
- 每个 body 段落控制在 50-90 字之间；如果某个点确实复杂，可以接近 100 字，但不要过短
- body 段落要尽量写成可直接朗读的讲稿句子，而不是只写一句结论
- 不要输出 "安牛工作汇报"、"安牛安全汇报" 之类的系统品牌字样

## 输入信息

培训主题：{title}
目标受众：{audience}
内容页数：{content_count}
{"重点领域：" + "、".join(focus_areas) if focus_areas else ""}
{"额外要求：" + req if req else ""}

## 原始素材内容

以下是从用户提供的所有来源（文本输入、上传文档、知识库文档）中提取的原始素材内容，请仔细阅读并基于这些内容生成大纲：

{preview}

## 输出 JSON 格式

{{"slides": [{{"title": "页面标题", "subtitle": "这一页的核心结论", "body": ["第一段正文", "第二段正文"]}}]}}"""


def _parse_llm_slides(data: dict[str, Any], pack: ContentPack, settings: dict[str, Any]) -> TrainingOutline | None:
    raw = data.get("slides") or []
    if not isinstance(raw, list) or not raw:
        return None
    slides: list[TrainingOutlineSlide] = [_cover_slide(settings, pack)]
    groups = _chunk_groups(pack, max(1, len(raw)))
    for idx, s in enumerate(raw):
        if not isinstance(s, dict):
            continue
        stype = str(s.get("slide_type", "content"))
        if stype not in ("content", "workflow", "risk_scene", "legal_requirement", "control_measures", "case_discussion", "checklist", "quiz"):
            stype = "content"
        title = str(s.get("title", f"页面{idx+1}"))
        subtitle = str(s.get("subtitle") or s.get("sub_title") or s.get("label") or "").strip() or None
        group = groups[idx] if idx < len(groups) else []
        points: list[TrainingOutlinePoint] = []
        body_source = s.get("body") or s.get("paragraphs") or s.get("content") or s.get("text")
        body_paragraphs = _paragraphs_from_value(body_source)
        raw_points = s.get("points") or []
        if isinstance(raw_points, list):
            for item in raw_points:
                if isinstance(item, dict):
                    t = str(item.get("title", "")).strip()
                    d = str(item.get("description", "")).strip()
                    if t or d:
                        points.append(TrainingOutlinePoint(title=(t or d)[:28], description=d[:96]))
                elif str(item).strip():
                    points.append(_point_from_text(str(item)))
        if not points:
            # 兼容旧版 key_points 格式
            raw_keys = s.get("key_points") or []
            if isinstance(raw_keys, list) and raw_keys:
                points = _points_from_texts([str(k) for k in raw_keys if str(k).strip()])
        if not points:
            body = " ".join(str(getattr(c, "text", "")) for c in group)
            points = _points_from_texts(_split_points(body) or [title])
        refs = [_to_api_ref(ref) for c in group for ref in getattr(c, "source_refs", [])][:3]
        slides.append(TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}", slide_no=len(slides)+1,
            title=title, subtitle=subtitle, points=points[:5], body_paragraphs=body_paragraphs[:4],
            key_points=[f"{p.title}：{p.description}" if p.description else p.title for p in points[:5]],
            notes=_shorten(" ".join(str(getattr(c, "text", "")) for c in group), 240),
            slide_type=stype, source_refs=refs,
            visual_type="text" if (subtitle or body_paragraphs) else _visual_type(stype), safety_level=_safety_level(stype),
        ))

    if len(slides) < 3:
        return None

    sections = [
        TrainingOutlineSection(id=s.id, title=s.title, goal=s.notes or s.title, key_points=list(s.key_points), source_refs=list(s.source_refs))
        for s in slides if s.slide_type not in {"cover", "agenda", "summary", "quiz"}
    ]
    warnings = list(pack.warnings)
    return TrainingOutline(
        id=f"ol-{uuid.uuid4().hex[:10]}",
        title=data.get("title") or settings.get("title") or pack.topic,
        topic=pack.topic, audience=pack.audience,
        duration_minutes=pack.duration_minutes,
        style=_coerce_style(str(settings.get("style", "standard_training"))),
        slides=slides, sections=sections, warnings=warnings,
    )


async def generate_outline(
    pack: ContentPack,
    settings: Any,
    llm_client=llm_service,
    cancel_event: Event | None = None,
    job_id: str | None = None,
) -> TrainingOutline:
    settings_dict = _as_dict(settings)

    # 检查 LLM 模型是否已配置
    model_roles = config.get("models", {}).get("model_roles", {})
    model_id = model_roles.get("ppt_gen") or config.get("current_model_id")
    providers = config.get("models", {}).get("providers", [])
    model_available = bool(model_id and any(
        any(m.get("id") == model_id for m in p.get("models", [])) and p.get("api_key")
        for p in providers
    ))

    if not model_available:
        missing = f"ppt_gen 模型「{model_id}」" if model_id else "ppt_gen 模型"
        raise ValueError(f"LLM 模型不可用：请在设置中配置 {missing} 的 API Key")

    await asyncio.sleep(0)
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()

    expected_count = max(3, int(settings_dict.get("slide_count", 8)))
    update_job_progress(job_id, f"正在调用 AI 生成大纲（共{expected_count}页）...")
    await asyncio.sleep(0)

    try:
        prompt = _build_llm_prompt(pack, settings_dict)
        messages = [
        {
            "role": "system",
            "content": "你是安全生产内容策划专家。你的任务是基于用户提供的原始素材（直接输入文本、上传文档、知识库文档）进行综合分析，提炼关键知识点，生成结构合理、内容充实、适用于培训、汇报和分享场景的PPT逐页文字稿。只能使用这些来源中的信息或明确标注的通用知识；不要编造企业事实、公司名称、品牌口号、页脚文案，也不要重复同一句话。输出必须是严格 JSON。",
        },
            {"role": "user", "content": prompt},
        ]
        slide_count = max(3, int(settings_dict.get("slide_count", 8)))
        max_tokens = max(4500, slide_count * 260)
        logger.info("outline_llm_start", extra={
            "event": "outline_phase", "job_id": job_id,
            "slide_count": slide_count, "prompt_length": len(prompt),
            "model_id": model_id,
        })
        _t0 = time.monotonic()
        response = await asyncio.wait_for(
            llm_client.chat_sync(messages, model_id=model_id, temperature=0.2, max_tokens=max_tokens),
            timeout=OUTLINE_TIMEOUT_SECONDS,
        )
        _elapsed = time.monotonic() - _t0
        logger.info("outline_llm_done", extra={
            "event": "outline_phase", "job_id": job_id,
            "duration_ms": int(_elapsed * 1000),
            "response_length": len(response),
        })
    except asyncio.TimeoutError:
        raise ValueError(f"LLM 调用超时（{OUTLINE_TIMEOUT_SECONDS:.0f} 秒）")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        raise ValueError(f"LLM 调用失败：{str(exc)[:200]}")

    update_job_progress(job_id, "正在处理大纲结果...")
    await asyncio.sleep(0)

    # 解析 JSON
    raw = (response or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    data = None
    if start >= 0:
        try:
            data, _ = json.JSONDecoder().raw_decode(raw[start:])
        except json.JSONDecodeError:
            pass

    if not data:
        raise ValueError("LLM 返回无法解析为有效 JSON")

    outline = await asyncio.to_thread(_parse_llm_slides, data, pack, settings_dict)
    if not outline:
        raise ValueError("LLM 返回的大纲结构不符合要求")

    logger.info("outline_parsed", extra={
        "event": "outline_phase", "job_id": job_id,
        "slide_count": len(outline.slides), "section_count": len(outline.sections),
    })

    return outline
