"""培训大纲 → SlideSpec 转换。"""

from __future__ import annotations

import asyncio
import re
import uuid
from threading import Event
from typing import Any

from backend.models import (
    PresentationSpec,
    SlideSpec,
    TrainingOutline,
    TrainingOutlineSlide,
    TrainingSourceRef,
)
from backend.services.presentation.content_pack import ContentPack


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _normalize_refs(refs: list[Any]) -> list[TrainingSourceRef]:
    result = []
    for ref in refs:
        d = _as_dict(ref)
        if d:
            result.append(TrainingSourceRef(**d))
    return result


def _point_lines(slide: TrainingOutlineSlide) -> list[str]:
    if slide.points:
        lines = []
        for p in slide.points:
            t = re.sub(r"\s+", " ", p.title).strip()
            d = re.sub(r"\s+", " ", (p.description or "")).strip()
            lines.append(f"{t}：{d}" if t and d else (t or d))
        return lines[:5]
    return [re.sub(r"\s+", " ", k).strip()[:48] for k in slide.key_points[:5]]


def _slide_type(st: str) -> str:
    valid = {"cover", "agenda", "content", "workflow", "risk_scene", "legal_requirement",
             "control_measures", "case_discussion", "checklist", "quiz", "summary"}
    return st if st in valid else "content"


def _visual_type(st: str) -> str:
    return {
        "cover": "cards", "agenda": "cards", "workflow": "process_flow",
        "risk_scene": "risk_matrix", "legal_requirement": "table",
        "control_measures": "cards", "case_discussion": "qa",
        "checklist": "checklist", "quiz": "qa", "summary": "cards",
    }.get(st, "two_column")


def _safety_level(st: str) -> str:
    return {"risk_scene": "attention", "case_discussion": "attention",
            "legal_requirement": "warning", "quiz": "attention"}.get(st, "normal")


def _convert_slide(slide: TrainingOutlineSlide) -> SlideSpec:
    st = _slide_type(slide.slide_type)
    bullets = _point_lines(slide)
    key_message = ""
    if bullets:
        key_message = "；".join(bullets[:2])
    if slide.notes:
        note_text = re.sub(r"\s+", " ", slide.notes).strip()
        if note_text:
            key_message = key_message or note_text[:90]
    return SlideSpec(
        id=slide.id, slide_no=slide.slide_no, slide_type=st,
        title=slide.title, subtitle=slide.layout_hint,
        key_message=key_message[:96] if key_message else slide.title,
        bullets=bullets, source_refs=_normalize_refs(slide.source_refs),
        visual_type=_visual_type(st), safety_level=_safety_level(st),
    )


def plan_slides(
    outline: TrainingOutline,
    content_pack: ContentPack,
    settings: Any | None = None,
    cancel_event: Event | None = None,
) -> PresentationSpec:
    settings_dict = _as_dict(settings) if settings is not None else {}
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()

    template_id = settings_dict.get("template_id") or settings_dict.get("template") or settings_dict.get("style", "standard_training")

    slides: list[SlideSpec] = []
    for slide in (outline.slides or []):
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()
        slides.append(_convert_slide(slide))

    # 兼容旧版：只有 sections 但没有 slides
    if not slides and outline.sections:
        slides.append(SlideSpec(
            id=f"slide-{uuid.uuid4().hex[:8]}", slide_no=1, slide_type="cover",
            title=outline.title or outline.topic,
            bullets=[f"受众：{outline.audience}", f"时长：{outline.duration_minutes}分钟"],
        ))
        for sec in outline.sections:
            slides.append(SlideSpec(
                id=f"slide-{uuid.uuid4().hex[:8]}", slide_no=len(slides)+1, slide_type="content",
                title=sec.title, key_message=sec.goal,
                bullets=sec.key_points[:5],
                source_refs=_normalize_refs(sec.source_refs),
            ))
        slides.append(SlideSpec(
            id=f"slide-{uuid.uuid4().hex[:8]}", slide_no=len(slides)+1, slide_type="summary",
            title="总结与行动清单",
            bullets=["复盘关键风险点", "确认岗位职责和上报路径", "形成整改清单并闭环"],
        ))

    for i, s in enumerate(slides, 1):
        s.slide_no = i

    quality_warnings = list(outline.warnings) + list(content_pack.warnings)

    return PresentationSpec(
        id=f"spec-{uuid.uuid4().hex[:10]}",
        title=outline.title or outline.topic,
        topic=outline.topic, audience=outline.audience,
        duration_minutes=outline.duration_minutes,
        style=outline.style, template_id=template_id,
        slides=slides, quality_warnings=quality_warnings,
    )
