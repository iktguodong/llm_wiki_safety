"""把培训大纲转换为可渲染的 SlideSpec。"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from backend.config import config
from backend.services.llm import llm_service
from .models import ContentPack, PresentationSpec, SlideSpec, TrainingOutline, TrainingOutlineSection


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _normalize_points(points: list[str]) -> list[str]:
    cleaned = []
    for point in points:
        text = re.sub(r"\s+", "", str(point)).strip()
        if not text:
            continue
        cleaned.append(str(point).strip()[:48])
    return cleaned[:5]


def _slide_type_from_section(section: TrainingOutlineSection) -> str:
    title = section.title
    joined = " ".join([section.title, section.goal, " ".join(section.key_points)])
    if any(k in joined for k in ["法规", "制度", "职责", "条款", "阈值", "要求"]):
        return "legal_requirement"
    if any(k in joined for k in ["流程", "步骤", "处置", "报警", "疏散", "应急"]):
        return "workflow"
    if any(k in joined for k in ["风险", "隐患", "危险", "事故"]):
        return "risk_scene"
    if any(k in joined for k in ["检查", "清单", "核对"]):
        return "checklist"
    if any(k in joined for k in ["案例", "情景", "讨论"]):
        return "case_discussion"
    if any(k in joined for k in ["措施", "防护", "管控", "控制"]):
        return "control_measures"
    if "测验" in joined or "复盘" in joined:
        return "quiz"
    return "content"


def _make_section_slide(section: TrainingOutlineSection, slide_no: int, style: str) -> SlideSpec:
    slide_type = _slide_type_from_section(section)
    bullets = _normalize_points(section.key_points or [section.goal])
    visual_type = {
        "legal_requirement": "table",
        "workflow": "process_flow",
        "risk_scene": "risk_matrix",
        "checklist": "checklist",
        "case_discussion": "qa",
        "control_measures": "cards",
        "quiz": "qa",
    }.get(slide_type, "two_column")
    safety_level = "attention" if slide_type in {"risk_scene", "case_discussion"} else "normal"
    if slide_type == "legal_requirement":
        safety_level = "warning"
    return SlideSpec(
        id=f"slide-{uuid.uuid4().hex[:8]}",
        slide_no=slide_no,
        slide_type=slide_type,  # type: ignore[arg-type]
        title=section.title,
        subtitle=section.goal,
        key_message=section.goal,
        bullets=bullets,
        notes=section.goal,
        visual_type=visual_type,  # type: ignore[arg-type]
        source_refs=section.source_refs,
        safety_level=safety_level,  # type: ignore[arg-type]
    )


async def plan_slides(outline: TrainingOutline, content_pack: ContentPack, settings: Any, llm_client=llm_service) -> PresentationSpec:
    settings_dict = _as_dict(settings)
    template_id = str(settings_dict.get("template_id") or settings_dict.get("template") or "standard_training")
    title = outline.title or outline.topic
    slide_count = int(settings_dict.get("slide_count") or max(8, len(outline.sections) + 4))
    include_quiz = bool(settings_dict.get("include_quiz", True))
    include_speaker_notes = bool(settings_dict.get("include_speaker_notes", True))

    model_roles = config.get("models", {}).get("model_roles", {})
    model_id = model_roles.get("ppt_gen") or config.get("current_model_id")
    providers = config.get("models", {}).get("providers", [])
    model_available = False
    if model_id:
        for provider in providers:
            if any(model.get("id") == model_id for model in provider.get("models", [])) and provider.get("api_key"):
                model_available = True
                break

    slides: list[SlideSpec] = []
    slides.append(
        SlideSpec(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=1,
            slide_type="cover",
            title=title,
            subtitle=f"{outline.audience} · {outline.duration_minutes} 分钟 · {outline.style}",
            key_message=outline.topic,
            bullets=[
                f"受众：{outline.audience}",
                f"时长：{outline.duration_minutes} 分钟",
                f"风格：{outline.style}",
                f"生成日期：{content_pack.id[:8]}",
            ],
            notes="封面页，强调培训主题与适用对象。",
            visual_type="cards",
            source_refs=[],
            safety_level="normal",
        )
    )
    slides.append(
        SlideSpec(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=2,
            slide_type="toc",
            title="目录",
            subtitle="本次培训内容结构",
            key_message="先讲背景，再讲风险与要求，最后落到措施和复盘",
            bullets=[section.title for section in outline.sections[:5]],
            notes="目录页。",
            visual_type="cards",
            source_refs=[],
            safety_level="normal",
        )
    )

    slide_no = 3
    for idx, section in enumerate(outline.sections):
        if idx in {0, 3, 6}:
            slides.append(
                SlideSpec(
                    id=f"slide-{uuid.uuid4().hex[:8]}",
                    slide_no=slide_no,
                    slide_type="section_divider",
                    title=section.title,
                    subtitle=section.goal,
                    key_message=section.goal,
                    bullets=[],
                    notes="章节分隔页。",
                    visual_type="none",
                    source_refs=section.source_refs,
                    safety_level="normal",
                )
            )
            slide_no += 1
        slides.append(_make_section_slide(section, slide_no, outline.style))
        slide_no += 1

    if include_quiz:
        quiz_refs = [ref for section in outline.sections for ref in section.source_refs][:3]
        slides.append(
            SlideSpec(
                id=f"slide-{uuid.uuid4().hex[:8]}",
                slide_no=slide_no,
                slide_type="quiz",
                title="测验与复盘",
                subtitle="3 题小测，检查理解情况",
                key_message="检验关键点是否真正掌握",
                bullets=[
                    "题目1：发现隐患后第一步做什么？",
                    "题目2：哪些情形必须立即停止作业？",
                    "题目3：异常情况上报给谁？",
                ],
                notes="答案：1 立即报告并采取初期控制；2 存在重大风险、条件不满足或防护不到位；3 按制度上报值班/主管/应急联系人。",
                visual_type="qa",
                source_refs=quiz_refs,
                safety_level="attention",
            )
        )
        slide_no += 1

    slides.append(
        SlideSpec(
            id=f"slide-{uuid.uuid4().hex[:8]}",
            slide_no=slide_no,
            slide_type="summary",
            title="总结与行动清单",
            subtitle="把培训内容落实到现场",
            key_message="培训结束后要落实到检查、复盘和岗位行动",
            bullets=[
                "复盘关键风险点",
                "确认岗位职责和上报路径",
                "检查控制措施是否到位",
                "形成整改清单并闭环",
            ],
            notes="总结页。",
            visual_type="cards",
            source_refs=[ref for section in outline.sections for ref in section.source_refs][:4],
            safety_level="normal",
        )
    )

    if model_available and len(slides) < slide_count:
        # 轻量补页：将前面章节的关键点按需要切分
        extra_sections = outline.sections[: max(0, slide_count - len(slides))]
        for section in extra_sections:
            slides.insert(
                -1,
                SlideSpec(
                    id=f"slide-{uuid.uuid4().hex[:8]}",
                    slide_no=0,
                    slide_type="content",
                    title=f"{section.title} - 延伸",
                    subtitle=section.goal,
                    key_message=section.goal,
                    bullets=_normalize_points(section.key_points[:3]),
                    notes=section.goal,
                    visual_type="two_column",
                    source_refs=section.source_refs,
                    safety_level="normal",
                ),
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
        quality_warnings=quality_warnings if include_speaker_notes else quality_warnings,
    )
