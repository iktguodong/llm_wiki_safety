"""HTML 训练材料的轻量质量检查。"""

from __future__ import annotations

import re
from typing import Any

from .html_deck import HtmlDeckSpec
from .models import ContentPack, QualityIssue, QualityReport


def _bullet_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _settings_dict(settings: Any | None) -> dict[str, Any]:
    if settings is None:
        return {}
    if hasattr(settings, "model_dump"):
        return dict(settings.model_dump())
    if isinstance(settings, dict):
        return dict(settings)
    return dict(getattr(settings, "__dict__", {}))


def _has_external_sources(deck: HtmlDeckSpec, content_pack: ContentPack) -> bool:
    for page in deck.pages:
        for ref in page.source_refs:
            if ref.source_type != "prompt":
                return True
    for chunk in content_pack.chunks:
        for ref in chunk.source_refs:
            if ref.source_type != "prompt":
                return True
    return False


def check_html_deck(deck: HtmlDeckSpec, content_pack: ContentPack, settings: Any | None = None) -> QualityReport:
    issues: list[QualityIssue] = []
    settings_dict = _settings_dict(settings)
    target_slide_count = int(settings_dict.get("slide_count") or 0)

    banned_phrases = {
        "开场介绍培训主题和背景",
        "参考签署页和目录结构",
        "本页目标",
        "请按页面要点讲解",
        "内容将根据来源自动整理",
    }

    for page in deck.pages:
        if not page.title.strip():
            issues.append(QualityIssue(level="error", code="empty_title", message="页面标题不能为空", slide_id=page.id, suggestion="补充清晰的页面标题"))
        text_blob = " ".join([page.title, page.subtitle or "", page.summary or "", page.notes or "", " ".join(page.bullets)])
        compact = re.sub(r"\s+", "", text_blob)
        if any(phrase in compact for phrase in banned_phrases):
            issues.append(QualityIssue(level="error", code="boilerplate_leak", message="检测到模板化说明文字混入网页内容", slide_id=page.id, suggestion="改为直接描述培训内容与行动要点"))
        if len(page.bullets) > 5:
            issues.append(QualityIssue(level="warning", code="too_many_bullets", message="每页 bullet 超过 5 条", slide_id=page.id, suggestion="精简到 5 条以内"))
        for bullet in page.bullets:
            if _bullet_len(bullet) > 40:
                issues.append(QualityIssue(level="warning", code="bullet_too_long", message="bullet 尽量不超过 40 个汉字", slide_id=page.id, suggestion="拆分为更短的表达"))

        source_labels = []
        seen: set[str] = set()
        for ref in page.source_refs:
            label = ref.title or ref.page_name or ref.document_id or ref.upload_id or ref.source_id or ref.source_type
            if label in seen:
                continue
            seen.add(label)
            source_labels.append(label)
        if len(source_labels) > 2:
            issues.append(QualityIssue(level="warning", code="source_overweight", message="来源展示过多，建议压缩为少量辅助标签", slide_id=page.id, suggestion="每页仅保留 1-2 个来源标签"))

    if target_slide_count:
        diff = abs(len(deck.pages) - target_slide_count)
        if diff > 4:
            issues.append(QualityIssue(level="warning", code="slide_count_mismatch", message="页数与目标页数差距较大", suggestion="调整素材分组或节奏页数量"))

    if not _has_external_sources(deck, content_pack):
        issues.append(QualityIssue(level="warning", code="prompt_only", message="该内容主要由模型生成，未绑定企业原文来源", suggestion="如需更高可信度，请补充知识库或原始文档来源"))

    for warn in content_pack.warnings + deck.quality_warnings:
        if "扫描" in warn or "OCR" in warn or "无法提取可读文本" in warn:
            issues.append(QualityIssue(level="error", code="extraction_failed", message=warn, suggestion="请改用可提取文本的 PDF、Word、TXT 或 Markdown 文档"))

    passed = not any(issue.level == "error" for issue in issues)
    summary = f"检查完成：{len(deck.pages)} 页，发现 {sum(1 for issue in issues if issue.level == 'error')} 个错误，{sum(1 for issue in issues if issue.level == 'warning')} 个警告。"
    return QualityReport(passed=passed, issues=issues, summary=summary)
