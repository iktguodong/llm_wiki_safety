"""PPT 质量检查。"""

from __future__ import annotations

import asyncio
import re
from threading import Event
from typing import Any

from backend.models import PresentationSpec, QualityIssue, QualityReport
from backend.services.presentation.models import ContentPack


def _bullet_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


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
            if _bullet_len(b) > 30:
                issues.append(QualityIssue(level="warning", code="bullet_too_long", message="bullet 不宜超过 30 字", slide_id=slide.id))

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
