"""把培训大纲转换为可渲染的 SlideSpec。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.config import config
from backend.services.llm import llm_service
from .models import ContentPack, PresentationSpec, SlideSpec, SourceRef, TrainingOutline, TrainingOutlineSection, TrainingOutlineSlide


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _normalize_source_refs(refs: list[Any]) -> list[SourceRef]:
    normalized: list[SourceRef] = []
    for ref in refs:
        ref_data = _as_dict(ref)
        if not ref_data:
            continue
        normalized.append(SourceRef(**ref_data))
    return normalized


def _normalize_points(points: list[str]) -> list[str]:
    cleaned = []
    for point in points:
        text = re.sub(r"\s+", " ", str(point)).strip()
        if not text:
            continue
        cleaned.append(text[:48])
    return cleaned[:5]


def _point_lines(slide: TrainingOutlineSlide) -> list[str]:
    if slide.points:
        lines = []
        for point in slide.points:
            title = re.sub(r"\s+", " ", str(point.title)).strip()
            description = re.sub(r"\s+", " ", str(point.description or "")).strip()
            if title and description:
                lines.append(f"{title}：{description}")
            elif title:
                lines.append(title)
            elif description:
                lines.append(description)
        return lines[:5]
    return _normalize_points(slide.key_points or [slide.title])


def _slide_type_from_outline(slide: TrainingOutlineSlide) -> str:
    slide_type = slide.slide_type
    if slide_type in {
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
        return slide_type
    return "content"


def _visual_type(slide_type: str) -> str:
    return {
        "cover": "cards",
        "agenda": "cards",
        "workflow": "process_flow",
        "risk_scene": "risk_matrix",
        "legal_requirement": "table",
        "control_measures": "cards",
        "case_discussion": "qa",
        "checklist": "checklist",
        "quiz": "qa",
        "summary": "cards",
    }.get(slide_type, "two_column")


def _safety_level(slide_type: str) -> str:
    return {
        "risk_scene": "attention",
        "case_discussion": "attention",
        "legal_requirement": "warning",
        "quiz": "attention",
    }.get(slide_type, "normal")


def _legacy_sections_to_slides(outline: TrainingOutline) -> list[TrainingOutlineSlide]:
    slides: list[TrainingOutlineSlide] = []
    slides.append(
        TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=1,
            title=outline.title or outline.topic,
            key_points=[
                f"受众：{outline.audience}",
                f"时长：{outline.duration_minutes} 分钟",
                f"风格：{outline.style}",
            ],
            notes="封面页。",
            layout_hint="封面",
            slide_type="cover",
            source_refs=[],
            visual_type="cards",
            safety_level="normal",
        )
    )
    if outline.sections:
        slides.append(
            TrainingOutlineSlide(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=2,
                title="目录",
                key_points=[section.title for section in outline.sections[:5]],
                notes="目录页。",
                layout_hint="目录",
                slide_type="agenda",
                source_refs=[],
                visual_type="cards",
                safety_level="normal",
            )
        )
    for section in outline.sections:
        slide_type = "content"
        joined = " ".join([section.title, section.goal, " ".join(section.key_points)])
        if any(k in joined for k in ["法规", "制度", "职责", "条款", "要求"]):
            slide_type = "legal_requirement"
        elif any(k in joined for k in ["流程", "步骤", "处置", "报警", "疏散", "应急"]):
            slide_type = "workflow"
        elif any(k in joined for k in ["风险", "隐患", "危险", "事故"]):
            slide_type = "risk_scene"
        elif any(k in joined for k in ["检查", "清单", "核对", "排查"]):
            slide_type = "checklist"
        elif any(k in joined for k in ["案例", "情景", "讨论"]):
            slide_type = "case_discussion"
        elif any(k in joined for k in ["措施", "防护", "管控", "控制"]):
            slide_type = "control_measures"
        elif any(k in joined for k in ["测验", "复盘"]):
            slide_type = "quiz"
        slides.append(
            TrainingOutlineSlide(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=len(slides) + 1,
                title=section.title,
                key_points=_normalize_points(section.key_points or [section.goal]),
                notes=section.goal,
                layout_hint="正文页",
                slide_type=slide_type,  # type: ignore[arg-type]
                source_refs=_normalize_source_refs(section.source_refs),
                visual_type=_visual_type(slide_type),
                safety_level=_safety_level(slide_type),
            )
        )
    slides.append(
        TrainingOutlineSlide(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=len(slides) + 1,
            title="总结与行动清单",
            key_points=["复盘关键风险点", "确认岗位职责和上报路径", "形成整改清单并闭环"],
            notes="总结页。",
            layout_hint="总结",
            slide_type="summary",
            source_refs=[ref for section in outline.sections for ref in section.source_refs][:4],
            visual_type="cards",
            safety_level="normal",
        )
    )
    return slides


def _make_spec_slides(outline: TrainingOutline) -> list[TrainingOutlineSlide]:
    if outline.slides:
        return outline.slides
    return _legacy_sections_to_slides(outline)


def _convert_outline_slide(slide: TrainingOutlineSlide) -> SlideSpec:
    slide_type = _slide_type_from_outline(slide)
    bullets = _point_lines(slide)
    return SlideSpec(
        id=slide.id,
        slide_no=slide.slide_no,
        slide_type=slide_type,  # type: ignore[arg-type]
        title=slide.title,
        subtitle=slide.layout_hint,
        key_message=slide.notes or slide.title,
        bullets=bullets,
        notes=None,
        visual_type=(slide.visual_type or _visual_type(slide_type)),  # type: ignore[arg-type]
        source_refs=_normalize_source_refs(slide.source_refs),
        safety_level=(slide.safety_level or _safety_level(slide_type)),  # type: ignore[arg-type]
    )


async def plan_slides(outline: TrainingOutline, content_pack: ContentPack, settings: Any, llm_client=llm_service) -> PresentationSpec:
    settings_dict = _as_dict(settings)
    template_id = str(settings_dict.get("template_id") or settings_dict.get("template") or "standard_training")
    title = outline.title or outline.topic

    model_roles = config.get("models", {}).get("model_roles", {})
    model_id = model_roles.get("ppt_gen") or config.get("current_model_id")
    providers = config.get("models", {}).get("providers", [])
    model_available = False
    if model_id:
        for provider in providers:
            if any(model.get("id") == model_id for model in provider.get("models", [])) and provider.get("api_key"):
                model_available = True
                break

    outline_slides = _make_spec_slides(outline)
    slides: list[SlideSpec] = []
    for slide in outline_slides:
        slides.append(_convert_outline_slide(slide))

    if model_available and len(slides) < 3 and outline.sections:
        # 兼容旧式章节输入，确保至少有完整的封面、目录和总结
        for section in outline.sections:
            slides.append(
                SlideSpec(
                    id=f"slide-{uuid.uuid4().hex[:8]}",
                    slide_no=len(slides) + 1,
                    slide_type="content",
                    title=section.title,
                subtitle=section.goal,
                key_message=section.goal,
                bullets=_normalize_points(section.key_points or [section.goal]),
                notes=section.goal,
                visual_type="two_column",
                source_refs=_normalize_source_refs(section.source_refs),
                safety_level="normal",
            )
        )

    for idx, slide in enumerate(slides, start=1):
        slide.slide_no = idx

    quality_warnings = list(outline.warnings) + list(content_pack.warnings)
    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
        quality_warnings.append("该内容主要由模型生成，未绑定企业原文来源")

    return PresentationSpec(
        id=f"spec-{uuid.uuid4().hex[:10]}",
        title=title,
        topic=outline.topic,
        audience=outline.audience,
        duration_minutes=outline.duration_minutes,
        style=outline.style,
        template_id=template_id,
        slides=slides,
        quality_warnings=quality_warnings,
    )
