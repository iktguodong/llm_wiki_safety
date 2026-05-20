"""PPT 质量检查。"""

from __future__ import annotations

import asyncio
import re
from threading import Event
from typing import Any

from backend.models import PresentationSpec, QualityIssue, QualityReport, TrainingSourceRef
from backend.services.presentation.models import ContentPack


def _bullet_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _normalize_bullet(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned


def _collect_source_refs(content_pack: ContentPack) -> list[TrainingSourceRef]:
    refs: list[TrainingSourceRef] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for chunk in content_pack.chunks:
        for ref in chunk.source_refs:
            api_ref = ref if isinstance(ref, TrainingSourceRef) else TrainingSourceRef(**(ref.model_dump() if hasattr(ref, "model_dump") else dict(ref)))
            key = (api_ref.source_type, api_ref.source_id, api_ref.kb_id, api_ref.document_id)
            if key in seen:
                continue
            seen.add(key)
            refs.append(api_ref)
            if len(refs) >= 3:
                return refs
    return refs


def repair_presentation(
    spec: PresentationSpec,
    content_pack: ContentPack,
    settings: Any | None = None,
) -> PresentationSpec:
    repaired = spec.model_copy(deep=True)
    shared_refs = _collect_source_refs(content_pack)
    for slide in repaired.slides:
        slide.title = slide.title.strip() or "未命名页面"
        slide.bullets = [_normalize_bullet(b) for b in slide.bullets[:5] if str(b).strip()]
        if slide.slide_type == "quiz" and not slide.notes:
            slide.notes = "参考前后页内容确认答案"
        if not slide.source_refs and shared_refs and slide.slide_type in {"legal_requirement", "workflow", "risk_scene", "control_measures", "case_discussion", "checklist", "content"}:
            slide.source_refs = shared_refs[:2]
        if not slide.bullets:
            slide.bullets = ["内容待补充"]
    return repaired


def check_presentation(
    spec: PresentationSpec,
    content_pack: ContentPack,
    settings: Any | None = None,
    cancel_event: Event | None = None,
) -> QualityReport:
    issues: list[QualityIssue] = []
    settings_dict = {}
    if settings is not None:
        if hasattr(settings, "model_dump"):
            settings_dict = dict(settings.model_dump())
        elif isinstance(settings, dict):
            settings_dict = dict(settings)
    target_count = int(settings_dict.get("slide_count", 0))

    for slide in spec.slides:
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()

        if not slide.title.strip():
            issues.append(QualityIssue(level="error", code="empty_title", message="页面标题不能为空", slide_id=slide.id))

        if len(slide.bullets) > 5:
            issues.append(QualityIssue(level="warning", code="too_many_bullets", message="每页 bullet 超过 5 条", slide_id=slide.id))

        for b in slide.bullets:
            if _bullet_len(b) > 90:
                issues.append(QualityIssue(level="warning", code="bullet_too_long", message="bullet 建议控制在 90 字以内", slide_id=slide.id))

        has_legal_keywords = any(k in slide.title + " " + " ".join(slide.bullets) for k in ["法规", "制度", "职责", "阈值", "流程"])
        if has_legal_keywords and not slide.source_refs:
            issues.append(QualityIssue(level="error", code="missing_source", message="法规/制度/职责类内容需注明来源", slide_id=slide.id))

        if slide.slide_type == "legal_requirement" and not slide.source_refs:
            issues.append(QualityIssue(level="warning", code="legal_without_source", message="法规制度页缺少来源", slide_id=slide.id))

        if slide.slide_type == "quiz" and not slide.notes:
            issues.append(QualityIssue(level="error", code="quiz_missing_answer", message="测验页必须有答案备注", slide_id=slide.id))

    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()

    if target_count:
        diff = abs(len(spec.slides) - target_count)
        if diff > 4:
            issues.append(QualityIssue(level="warning", code="slide_count_mismatch", message="页数与目标相差较大"))

    passed = not any(i.level == "error" for i in issues)
    summary = f"检查完成：{len(spec.slides)} 页，{sum(1 for i in issues if i.level=='error')} 个错误，{sum(1 for i in issues if i.level=='warning')} 个警告。"
    return QualityReport(passed=passed, issues=issues, summary=summary)
