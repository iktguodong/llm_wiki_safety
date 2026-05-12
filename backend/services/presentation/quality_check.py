"""轻量质量检查。"""

from __future__ import annotations

import re
from typing import Any

from .models import ContentPack, QualityIssue, QualityReport, PresentationSpec


def _has_sources(spec: PresentationSpec) -> bool:
    for slide in spec.slides:
        if slide.source_refs:
            return True
    return False


def _bullet_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def check_presentation(spec: PresentationSpec, content_pack: ContentPack, settings: Any | None = None) -> QualityReport:
    issues: list[QualityIssue] = []
    settings_dict = {}
    if settings is not None:
        if hasattr(settings, "model_dump"):
            settings_dict = dict(settings.model_dump())
        elif isinstance(settings, dict):
            settings_dict = dict(settings)

    target_slide_count = int(settings_dict.get("slide_count") or 0)

    for slide in spec.slides:
        if not slide.title.strip():
            issues.append(QualityIssue(level="error", code="empty_title", message="页面标题不能为空", slide_id=slide.id, suggestion="补充清晰的页面标题"))
        if len(slide.bullets) > 5:
            issues.append(QualityIssue(level="warning", code="too_many_bullets", message="每页 bullet 超过 5 条", slide_id=slide.id, suggestion="精简到 5 条以内"))
        for bullet in slide.bullets:
            if _bullet_len(bullet) > 30:
                issues.append(QualityIssue(level="warning", code="bullet_too_long", message="bullet 尽量不超过 30 个汉字", slide_id=slide.id, suggestion="拆分为更短的表达"))
        if any(k in slide.title + " " + " ".join(slide.bullets) for k in ["法规", "制度", "职责", "阈值", "流程"]) and not slide.source_refs:
            issues.append(QualityIssue(level="error", code="missing_source", message="法规/制度/职责/流程类内容必须保留来源", slide_id=slide.id, suggestion="补充 source_refs"))
        if slide.slide_type == "legal_requirement" and not slide.source_refs:
            issues.append(QualityIssue(level="warning", code="legal_without_source", message="法规制度页缺少来源", slide_id=slide.id, suggestion="仅在有明确来源时使用该页型"))
        if slide.safety_level == "critical" and not any(k in (slide.title + " " + " ".join(slide.bullets)) for k in ["严重", "禁止", "重大", "爆炸", "伤亡"]):
            issues.append(QualityIssue(level="warning", code="critical_mismatch", message="critical 仅用于严重后果或禁止事项", slide_id=slide.id, suggestion="下调安全级别或补充严重风险信息"))
        if slide.slide_type == "quiz" and not slide.notes:
            issues.append(QualityIssue(level="error", code="quiz_missing_answer", message="测验页必须包含答案备注", slide_id=slide.id, suggestion="在 notes 中写出答案"))

    if target_slide_count:
        diff = abs(len(spec.slides) - target_slide_count)
        if diff > 4:
            issues.append(QualityIssue(level="warning", code="slide_count_mismatch", message="页数与目标页数差距较大", suggestion="调整章节数量或拆分/合并页面"))

    if not _has_sources(spec) and any(chunk.chunk_type == "prompt_generated" for chunk in content_pack.chunks):
        issues.append(QualityIssue(level="warning", code="prompt_only", message="该内容主要由模型生成，未绑定企业原文来源", suggestion="如需更高可信度，请补充知识库或原始文档来源"))

    for warn in content_pack.warnings + spec.quality_warnings:
        if "扫描" in warn or "OCR" in warn or "无法提取可读文本" in warn:
            issues.append(QualityIssue(level="error", code="extraction_failed", message=warn, suggestion="请改用可提取文本的 PDF、Word、TXT 或 Markdown 文档"))

    passed = not any(issue.level == "error" for issue in issues)
    summary = f"检查完成：{len(spec.slides)} 页，发现 {sum(1 for issue in issues if issue.level == 'error')} 个错误，{sum(1 for issue in issues if issue.level == 'warning')} 个警告。"
    return QualityReport(passed=passed, issues=issues, summary=summary)
