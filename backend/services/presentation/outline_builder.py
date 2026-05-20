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
    TrainingSlideSection,
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
OUTLINE_BODY_TIMEOUT_SECONDS = 30.0
MAX_PARALLEL_OUTLINE_CALLS = 3
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

def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _preview_chunks(chunks: list[Any], *, limit: int = 5, excerpt_limit: int = 900) -> str:
    parts: list[str] = []
    for chunk in chunks[:limit]:
        refs = ", ".join((r.title or r.source_id or r.source_type) for r in getattr(chunk, "source_refs", [])[:2])
        excerpt = re.sub(r"\s+", " ", str(getattr(chunk, "text", ""))).strip()[:excerpt_limit]
        parts.append(f"### {getattr(chunk, 'title', '内容')}\n来源：{refs}\n{excerpt}")
    return "\n\n".join(parts)[:8000]


def _normalize_body_paragraphs(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    paragraphs: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item)).strip(" -•\t")
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs[:5]


def _normalize_section_paragraphs(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    paragraphs: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item)).strip(" -•\t")
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs[:4]


def _section_from_point(point: TrainingOutlinePoint, idx: int) -> TrainingSlideSection:
    subtitle = (point.title or point.description or f"小节{idx}").strip() or f"小节{idx}"
    paragraphs = _normalize_section_paragraphs(point.description)
    return TrainingSlideSection(
        id=f"section-{uuid.uuid4().hex[:8]}",
        subtitle=subtitle[:48],
        paragraphs=paragraphs,
        notes=point.description or None,
    )


def _section_summary(section: TrainingSlideSection, max_len: int = 140) -> str:
    parts = [section.subtitle]
    parts.extend(section.paragraphs[:2])
    return _shorten(" ".join(parts), max_len)


def _sections_to_points(sections: list[TrainingSlideSection]) -> list[TrainingOutlinePoint]:
    points: list[TrainingOutlinePoint] = []
    for section in sections:
        desc = _section_summary(section, 180)
        points.append(TrainingOutlinePoint(title=section.subtitle[:28], description=desc if desc != section.subtitle else ""))
    return points


def _flatten_section_paragraphs(sections: list[TrainingSlideSection]) -> list[str]:
    paragraphs: list[str] = []
    for section in sections:
        for paragraph in section.paragraphs:
            cleaned = re.sub(r"\s+", " ", str(paragraph)).strip()
            if cleaned:
                paragraphs.append(cleaned)
    return paragraphs


def _sections_from_value(value: Any) -> list[TrainingSlideSection]:
    raw_sections: list[Any]
    if isinstance(value, list):
        raw_sections = value
    else:
        raw_sections = []
    sections: list[TrainingSlideSection] = []
    for idx, item in enumerate(raw_sections, start=1):
        if isinstance(item, dict):
            subtitle = str(item.get("subtitle") or item.get("title") or item.get("label") or "").strip() or f"小节{idx}"
            paragraphs = _normalize_section_paragraphs(
                item.get("paragraphs")
                or item.get("body")
                or item.get("content")
                or item.get("text")
            )
            if not paragraphs:
                content = str(item.get("description") or item.get("summary") or "").strip()
                if content:
                    paragraphs = _normalize_section_paragraphs(content)
            sections.append(TrainingSlideSection(
                id=f"section-{uuid.uuid4().hex[:8]}",
                subtitle=subtitle[:48],
                paragraphs=paragraphs,
                notes=str(item.get("notes") or item.get("goal") or item.get("description") or "").strip() or None,
            ))
        else:
            text = str(item).strip()
            if text:
                sections.append(TrainingSlideSection(
                    id=f"section-{uuid.uuid4().hex[:8]}",
                    subtitle=text[:48],
                    paragraphs=[],
                ))
    return sections


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
    preview = _preview_chunks(list(pack.chunks), limit=20, excerpt_limit=1500)
    content_count = max(1, int(settings.get("slide_count") or 8) - 1)
    title = settings.get("title") or settings.get("topic") or pack.title or pack.topic
    audience = settings.get("audience") or pack.audience or "相关岗位人员"
    req = settings.get("requirements") or settings.get("requirement") or ""
    focus_areas = settings.get("focus_areas") or []
    return f"""你是一位专业的安全生产内容策划专家，擅长将材料整理为适用于培训、汇报和分享场景的PPT逐页正文骨架。请根据以下输入材料生成逐页结构，后续系统会再并发扩写每个小节的正文。

## 核心要求

1. **基于材料，不编造**：严格遵守输入材料中的事实和数据，不得编造企业制度条款、事故案例、法规条文、公司名称、品牌口号、页脚文案或岗位职责。如果材料信息不足，可以概括通用安全知识，但必须标注「通用知识」。
2. **逻辑连贯**：整体内容应从导入→主体→总结形成完整的叙事逻辑，页面之间有递进关系。
3. **针对性强**：内容要贴合「{audience}」的岗位特点和认知水平，重点突出与受众相关的实操内容、管理要求和落地动作。
4. **写成 PPT 正文骨架**：每个页面必须包含 `title`、`sections`。每个 section 必须包含 `subtitle`，后续系统会根据这个 `subtitle` 并发扩写对应的 `paragraphs`。
5. **内容要够充实**：每页保留 2-4 个 sections，必要时可到 5 个；每个 section 的 `subtitle` 要表达一个独立小节主题，方便后续并发扩写成多段正文。
6. **结构清晰**：整页 `title` 负责总题目，`sections[].subtitle` 负责小节标题，后续正文会直接显示在 PPT 页面中，不能只是同义改写。
7. **避免重复**：不要在标题和各个 subtitle 里重复同一句话，不要把同一条内容在一页里写两遍，不要输出模板化品牌词。
8. **不要编号化表达**：不要把页面标题写成“1/2/3/4”或“第一、第二、第三”这种纯序号式表达；每页标题要有明确语义，点题即可。

## 输出格式要求

- 只输出一个严格 JSON 对象，不要 Markdown 代码块
- slides 必须是数组，严格生成 {content_count} 个内容页
- 不要封面页（封面页由系统自动生成）
- 每个 slide 包含 `title`、`sections` 字段
- `sections` 是数组，每项都要包含 `subtitle`
- 每个 section 的 `subtitle` 要对应一个可独立展开的小节，不要只写极短标签
- 如果材料结构复杂，可以适当增加 sections 数量，但要保持层次清晰
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

{{"slides": [{{"title": "页面标题", "sections": [{{"subtitle": "小节标题A"}}, {{"subtitle": "小节标题B"}}]}}]}}"""


def _build_section_body_prompt(
    pack: ContentPack,
    settings: dict[str, Any],
    slide: TrainingOutlineSlide,
    section: TrainingSlideSection,
    group: list[Any],
) -> str:
    title = settings.get("title") or settings.get("topic") or pack.title or pack.topic
    audience = settings.get("audience") or pack.audience or "相关岗位人员"
    focus_points = [f"- {section.subtitle}"]
    if section.notes:
        focus_points.append(f"- 目标：{section.notes}")
    if section.paragraphs:
        focus_points.extend(f"- 参考草稿：{p}" for p in section.paragraphs[:2])
    source_preview = _preview_chunks(list(group), limit=4, excerpt_limit=900)
    return f"""你是一位专业的安全生产内容策划专家。请根据下面的页面骨架和素材，为这一页的一个小节扩写成适合 PPT 展示的正文段落。

## 页面信息

培训主题：{title}
目标受众：{audience}
页面标题：{slide.title}
小节标题：{section.subtitle}

## 小节骨架

{chr(10).join(focus_points) if focus_points else "- 请围绕主题展开"}

## 扩写要求

1. 只输出一个严格 JSON 对象，不要 Markdown 代码块。
2. 输出字段必须包含 `subtitle` 和 `paragraphs`。
3. `subtitle` 可以沿用或优化小节标题，但要保持一句话表达。
4. `paragraphs` 是数组，建议 2-4 段，每段 50-90 字，必要时可到 5 段。
5. 每段要写成可直接放进 PPT 的讲稿正文，围绕“是什么 / 为什么 / 怎么做 / 注意什么”展开，不要只写关键词。
6. 段落之间要有递进，不要重复小节标题的表述。
7. 结合下面的原始素材内容，不要编造。

## 原始素材内容

{source_preview}

## 输出 JSON 格式

{{"subtitle": "这一页的小节结论", "paragraphs": ["第一段正文", "第二段正文"]}}"""


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
        sections = _sections_from_value(s.get("sections"))
        if not sections:
            raw_points = s.get("points") or []
            if isinstance(raw_points, list) and raw_points:
                sections = []
                for pidx, item in enumerate(raw_points, start=1):
                    if isinstance(item, dict):
                        point = TrainingOutlinePoint(
                            title=str(item.get("title", "")).strip() or str(item.get("description", "")).strip() or f"小节{pidx}",
                            description=str(item.get("description", "")).strip(),
                        )
                    else:
                        raw_text = str(item).strip()
                        if not raw_text:
                            continue
                        point = _point_from_text(raw_text)
                    sections.append(_section_from_point(point, pidx))
        if not sections:
            body_source = s.get("body") or s.get("paragraphs") or s.get("content") or s.get("text")
            body_paragraphs = _normalize_section_paragraphs(body_source)
            if body_paragraphs:
                sections = [TrainingSlideSection(
                    id=f"section-{uuid.uuid4().hex[:8]}",
                    subtitle=subtitle or title,
                    paragraphs=body_paragraphs,
                )]
        if not sections:
            raw_keys = s.get("key_points") or []
            if isinstance(raw_keys, list) and raw_keys:
                sections = [TrainingSlideSection(
                    id=f"section-{uuid.uuid4().hex[:8]}",
                    subtitle=str(raw_keys[0]).strip()[:48] or title,
                    paragraphs=[str(k).strip() for k in raw_keys if str(k).strip()][:4],
                )]
        if not sections:
            body = " ".join(str(getattr(c, "text", "")) for c in group)
            fallback_texts = _split_points(body) or [title]
            sections = [TrainingSlideSection(
                id=f"section-{uuid.uuid4().hex[:8]}",
                subtitle=fallback_texts[0][:48],
                paragraphs=fallback_texts[1:4],
            )]
        points = _sections_to_points(sections)
        body_paragraphs = _flatten_section_paragraphs(sections)
        refs = [_to_api_ref(ref) for c in group for ref in getattr(c, "source_refs", [])][:3]
        slides.append(TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}", slide_no=len(slides)+1,
            title=title, subtitle=subtitle,
            sections=sections[:5], points=points[:5], body_paragraphs=body_paragraphs[:10],
            key_points=[f"{p.title}：{p.description}" if p.description else p.title for p in points[:5]],
            notes=_shorten(" ".join(str(getattr(c, "text", "")) for c in group), 240),
            slide_type=stype, source_refs=refs,
            visual_type="text", safety_level=_safety_level(stype),
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


def _fallback_section_paragraphs(slide: TrainingOutlineSlide, section: TrainingSlideSection, group: list[Any]) -> list[str]:
    paragraphs: list[str] = []

    subtitle = re.sub(r"\s+", " ", section.subtitle or slide.subtitle or slide.title).strip(" -•\t")
    if subtitle:
        paragraphs.append(subtitle if subtitle.endswith(("。", "！", "？")) else f"{subtitle}。")

    if section.notes:
        notes = re.sub(r"\s+", " ", section.notes).strip(" -•\t")
        if notes:
            paragraphs.append(notes if notes.endswith(("。", "！", "？")) else f"{notes}。")

    section_texts: list[str] = []
    for text in section.paragraphs[:4]:
        cleaned = re.sub(r"\s+", " ", text).strip(" -•\t")
        if cleaned:
            section_texts.append(cleaned)

    if section_texts:
        lead = f"{slide.title}中关于{subtitle}的小节，应当围绕这一主题展开。"
        if len(section_texts) > 1:
            lead = f"{slide.title}中关于{subtitle}的小节，应当围绕这一主题展开，并补充{section_texts[0]}等内容。"
        paragraphs.append(lead)
        for item in section_texts[:3]:
            paragraphs.append(f"同时要明确{item}，确保内容能够直接用于培训或汇报。")

    source_summary = _shorten(
        " ".join(str(getattr(c, "text", "")) for c in group),
        220,
    )
    if source_summary and len(paragraphs) < 2:
        cleaned = re.sub(r"\s+", " ", source_summary).strip(" -•\t")
        if cleaned:
            paragraphs.append(cleaned if cleaned.endswith(("。", "！", "？")) else f"{cleaned}。")

    if not paragraphs:
        paragraphs = [f"围绕{slide.title}展开说明。"]

    return _normalize_body_paragraphs(paragraphs)[:4]


async def _expand_outline_section(
    pack: ContentPack,
    settings: dict[str, Any],
    slide: TrainingOutlineSlide,
    section: TrainingSlideSection,
    group: list[Any],
    llm_client,
    model_id: str,
    semaphore: asyncio.Semaphore,
    cancel_event: Event | None = None,
    job_id: str | None = None,
) -> TrainingSlideSection:
    if section.paragraphs:
        return section

    prompt = _build_section_body_prompt(pack, settings, slide, section, group)
    messages = [
        {
            "role": "system",
            "content": "你是安全生产内容策划专家。你的任务是根据页面和小节骨架、原始素材，扩写成适合 PPT 展示的正文段落。只能使用输入材料中的信息或明确标注的通用知识；不要编造企业事实、公司名称、品牌口号、页脚文案，也不要重复同一句话。输出必须是严格 JSON。",
        },
        {"role": "user", "content": prompt},
    ]

    async with semaphore:
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()
        logger.info("outline_body_start", extra={
            "event": "outline_body_phase",
            "job_id": job_id,
            "slide_no": slide.slide_no,
            "slide_title": slide.title,
            "model_id": model_id,
            "prompt_length": len(prompt),
        })
        try:
            response = await asyncio.wait_for(
                llm_client.chat_sync(messages, model_id=model_id, temperature=0.2, max_tokens=1800),
                timeout=OUTLINE_BODY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("outline_body_timeout", extra={
                "event": "outline_body_phase",
                "job_id": job_id,
                "slide_no": slide.slide_no,
                "slide_title": slide.title,
                "section_id": section.id,
                "section_subtitle": section.subtitle,
            })
            return section.model_copy(update={"paragraphs": _fallback_section_paragraphs(slide, section, group)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("outline_body_failed", extra={
                "event": "outline_body_phase",
                "job_id": job_id,
                "slide_no": slide.slide_no,
                "slide_title": slide.title,
                "section_id": section.id,
                "section_subtitle": section.subtitle,
                "error": str(exc)[:200],
            })
            return section.model_copy(update={"paragraphs": _fallback_section_paragraphs(slide, section, group)})

    data = _extract_json_object(response or "")
    if not data:
        return section.model_copy(update={"paragraphs": _fallback_section_paragraphs(slide, section, group)})

    subtitle = str(data.get("subtitle") or data.get("sub_title") or data.get("label") or "").strip() or section.subtitle
    body_paragraphs = _normalize_section_paragraphs(data.get("paragraphs") or data.get("body") or data.get("content") or data.get("text"))
    if len(body_paragraphs) < 2:
        body_paragraphs = _fallback_section_paragraphs(slide, section, group)

    return section.model_copy(update={"subtitle": subtitle, "paragraphs": body_paragraphs[:4]})


async def _expand_outline_sections(
    outline: TrainingOutline,
    pack: ContentPack,
    settings: dict[str, Any],
    llm_client,
    model_id: str,
    cancel_event: Event | None = None,
    job_id: str | None = None,
) -> TrainingOutline:
    content_slides = list(outline.slides[1:])
    if not content_slides:
        return outline

    groups = _chunk_groups(pack, len(content_slides))
    semaphore = asyncio.Semaphore(min(MAX_PARALLEL_OUTLINE_CALLS, len(content_slides)))
    tasks: list[asyncio.Task[TrainingSlideSection]] = []
    task_meta: list[tuple[int, int]] = []

    for slide_index, slide in enumerate(content_slides):
        slide_group = groups[slide_index] if slide_index < len(groups) else []
        slide_sections = list(slide.sections)
        if not slide_sections:
            slide_sections = [_section_from_point(point, idx + 1) for idx, point in enumerate(slide.points[:4])]
        for section_index, section in enumerate(slide_sections):
            task_meta.append((slide_index, section_index))
            tasks.append(asyncio.create_task(_expand_outline_section(
                pack,
                settings,
                slide,
                section,
                slide_group,
                llm_client,
                model_id,
                semaphore,
                cancel_event=cancel_event,
                job_id=job_id,
            )))

    if not tasks:
        return outline

    expanded_sections = await asyncio.gather(*tasks)
    slide_map: dict[int, list[TrainingSlideSection]] = {idx: [] for idx in range(len(content_slides))}
    for (slide_index, _section_index), section in zip(task_meta, expanded_sections):
        slide_map.setdefault(slide_index, []).append(section)

    expanded_slides: list[TrainingOutlineSlide] = []
    for slide_index, slide in enumerate(content_slides):
        sections = slide_map.get(slide_index, list(slide.sections))
        if not sections:
            sections = list(slide.sections)
        body_paragraphs = _flatten_section_paragraphs(sections)
        points = _sections_to_points(sections)
        expanded_slides.append(slide.model_copy(update={
            "sections": sections[:5],
            "points": points[:5],
            "body_paragraphs": body_paragraphs[:12],
            "key_points": [f"{p.title}：{p.description}" if p.description else p.title for p in points[:5]],
            "subtitle": slide.subtitle or (sections[0].subtitle if sections else None),
            "visual_type": "text",
        }))
    sections = [
        TrainingOutlineSection(
            id=s.id,
            title=s.title,
            goal=s.notes or s.title,
            key_points=list(s.key_points),
            source_refs=list(s.source_refs),
        )
        for s in ([outline.slides[0], *expanded_slides])
        if s.slide_type not in {"cover", "agenda", "summary", "quiz"}
    ]
    return outline.model_copy(update={"slides": [outline.slides[0], *expanded_slides], "sections": sections})


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
    update_job_progress(job_id, f"正在调用 AI 生成大纲骨架（共{expected_count}页）...")
    await asyncio.sleep(0)

    try:
        prompt = _build_llm_prompt(pack, settings_dict)
        messages = [
        {
            "role": "system",
            "content": "你是安全生产内容策划专家。你的任务是基于用户提供的原始素材（直接输入文本、上传文档、知识库文档）进行综合分析，提炼关键知识点，生成结构合理、内容充实、适用于培训、汇报和分享场景的PPT逐页骨架。只能使用这些来源中的信息或明确标注的通用知识；不要编造企业事实、公司名称、品牌口号、页脚文案，也不要重复同一句话。输出必须是严格 JSON。",
        },
            {"role": "user", "content": prompt},
        ]
        slide_count = max(3, int(settings_dict.get("slide_count", 8)))
        max_tokens = max(3600, slide_count * 220)
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

    update_job_progress(job_id, "正在处理页面骨架...")
    await asyncio.sleep(0)

    data = _extract_json_object(response or "")
    if not data:
        raise ValueError("LLM 返回无法解析为有效 JSON")

    outline = await asyncio.to_thread(_parse_llm_slides, data, pack, settings_dict)
    if not outline:
        raise ValueError("LLM 返回的大纲结构不符合要求")

    update_job_progress(job_id, "正在并发扩写各小节正文...")
    await asyncio.sleep(0)

    outline = await _expand_outline_sections(
        outline,
        pack,
        settings_dict,
        llm_client,
        model_id,
        cancel_event=cancel_event,
        job_id=job_id,
    )

    logger.info("outline_parsed", extra={
        "event": "outline_phase", "job_id": job_id,
        "slide_count": len(outline.slides), "section_count": len(outline.sections),
    })

    return outline
