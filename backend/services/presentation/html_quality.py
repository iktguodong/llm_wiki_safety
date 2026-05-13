"""HTML 培训材料质量检查 — Style A 电子杂志风（guizang-ppt-skill）。

本模块专属于 HTML 生成链路，不与 PPT 质量检查（quality_check.py）共用逻辑。

检查层级：
  P0  会直接破坏风格、流程或输出可用性
  P1  明显偏离 Style A，高概率需要返工
  P2  可接受但建议修
"""

from __future__ import annotations

import re
from typing import Any

from .html_deck import HTML_THEMES, STYLE_A_ONLY, HtmlDeckSpec
from .html_text_utils import bullet_limit_for_layout
from .models import ContentPack, QualityIssue, QualityReport

# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"   # 杂项符号及图形
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U000024FF"
    "]+",
    flags=re.UNICODE,
)

_BOILERPLATE_COMPACT = {
    "开场介绍培训主题和背景",
    "参考签署页和目录结构",
    "本页目标",
    "请按页面要点讲解",
    "内容将根据来源自动整理",
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def _bullet_char_len(text: str) -> int:
    return len(_compact(text))


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


# --------------------------------------------------------------------------
# 主检查函数
# --------------------------------------------------------------------------

def check_html_deck(deck: HtmlDeckSpec, content_pack: ContentPack, settings: Any | None = None) -> QualityReport:
    """检查 HtmlDeckSpec 是否符合 Style A 约束，返回 QualityReport。"""

    issues: list[QualityIssue] = []
    settings_dict = _settings_dict(settings)
    target_slide_count = int(settings_dict.get("slide_count") or 0)

    # ------------------------------------------------------------------
    # P0：风格锁定验证
    # ------------------------------------------------------------------

    if deck.style != STYLE_A_ONLY:
        issues.append(QualityIssue(
            level="error",
            code="style_violation",
            message=f"当前风格为 '{deck.style}'，本项目只允许 Style A（magazine）",
            suggestion=f"将 style 改为 '{STYLE_A_ONLY}'",
        ))

    if deck.theme not in HTML_THEMES:
        issues.append(QualityIssue(
            level="error",
            code="invalid_theme",
            message=f"主题 '{deck.theme}' 不在预设列表中，禁止自定义 hex 色",
            suggestion=f"只能使用：{', '.join(HTML_THEMES.keys())}",
        ))

    # ------------------------------------------------------------------
    # P0：Hero 页存在性
    # ------------------------------------------------------------------

    has_hero = any(p.layout == "hero" for p in deck.pages)
    if not has_hero:
        issues.append(QualityIssue(
            level="error",
            code="missing_hero",
            message="没有 hero 页（封面页），hero/non-hero 节奏无法成立",
            suggestion="确保首页 layout='hero'",
        ))

    # ------------------------------------------------------------------
    # P0 / P1：逐页检查
    # ------------------------------------------------------------------

    for page in deck.pages:

        # P0：标题不能为空
        if not page.title.strip():
            issues.append(QualityIssue(
                level="error",
                code="empty_title",
                message="页面标题不能为空",
                slide_id=page.id,
                suggestion="补充清晰的页面标题",
            ))
            continue  # 标题为空时跳过后续检查

        # P0：Emoji 检测 — 破坏等宽/衬线字体分工
        for field_name, field_value in [
            ("title", page.title),
            ("subtitle", page.subtitle or ""),
            ("summary", page.summary or ""),
            ("notes", page.notes or ""),
        ]:
            if _has_emoji(field_value):
                issues.append(QualityIssue(
                    level="error",
                    code="emoji_detected",
                    message=f"字段 {field_name} 含有 emoji，会破坏衬线/非衬线字体分工",
                    slide_id=page.id,
                    suggestion="删除 emoji，改用文字表达",
                ))

        for i, bullet in enumerate(page.bullets):
            if _has_emoji(bullet):
                issues.append(QualityIssue(
                    level="error",
                    code="emoji_in_bullet",
                    message=f"第 {i+1} 条 bullet 含有 emoji",
                    slide_id=page.id,
                    suggestion="删除 emoji，改用文字表达",
                ))

        # P0：标题过长 — 会造成换行失控（>14 个汉字等价字符）
        title_len = len(_compact(page.title))
        if title_len > 16:
            issues.append(QualityIssue(
                level="error",
                code="title_too_long",
                message=f"标题 '{page.title[:20]}…' 过长（{title_len} 字），衬线大字体下会换行失控",
                slide_id=page.id,
                suggestion="标题控制在 14 字以内",
            ))

        # P1：模板化说明文字混入内容
        text_blob = _compact(" ".join([page.title, page.subtitle or "", page.summary or "", page.notes or ""]))
        for phrase in _BOILERPLATE_COMPACT:
            if phrase in text_blob:
                issues.append(QualityIssue(
                    level="warning",
                    code="boilerplate_leak",
                    message="检测到模板化说明文字混入页面内容",
                    slide_id=page.id,
                    suggestion="改为直接描述培训内容与行动要点",
                ))
                break

        # P1：bullet 数量
        bullet_limit = bullet_limit_for_layout(page.layout)
        if len(page.bullets) > bullet_limit:
            issues.append(QualityIssue(
                level="warning",
                code="too_many_bullets",
                message=f"该页 bullet 超过 {bullet_limit} 条（当前 {len(page.bullets)} 条）",
                slide_id=page.id,
                suggestion=f"精简到 {bullet_limit} 条以内，保持扫读节奏",
            ))

        # P1：bullet 过长
        for bullet in page.bullets:
            if _bullet_char_len(bullet) > 40:
                issues.append(QualityIssue(
                    level="warning",
                    code="bullet_too_long",
                    message=f"bullet 长度超过 40 字：'{bullet[:20]}…'",
                    slide_id=page.id,
                    suggestion="拆分成更短的表达",
                ))

        # P2：来源标签过多
        seen_labels: set[str] = set()
        for ref in page.source_refs:
            label = ref.title or ref.page_name or ref.document_id or ref.upload_id or ref.source_id or ref.source_type
            seen_labels.add(label)
        if len(seen_labels) > 2:
            issues.append(QualityIssue(
                level="warning",
                code="source_overweight",
                message="来源展示过多，建议压缩为 1-2 个辅助标签",
                slide_id=page.id,
                suggestion="每页最多保留 2 个来源标签",
            ))

    # --------------------------------------------------------------
    # P1：chrome-kicker 碰撞
    # --------------------------------------------------------------

    for page in deck.pages:
        if page.kicker and page.chrome and _compact(page.kicker) == _compact(page.chrome):
            issues.append(QualityIssue(
                level="warning",
                code="chrome_kicker_collision",
                message=f"chrome 与 kicker 相同：'{page.kicker}'，两者不能互相翻译",
                slide_id=page.id,
                suggestion="chrome 是稳定栏目标签，kicker 是本页独一份的引导句，应该不同",
            ))

    # --------------------------------------------------------------
    # P1：连续 3 页相同 layout
    # --------------------------------------------------------------

    layouts = [p.layout for p in deck.pages]
    for i in range(2, len(layouts)):
        if layouts[i] == layouts[i - 1] == layouts[i - 2]:
            issues.append(QualityIssue(
                level="warning",
                code="layout_streak",
                message=f"第 {i - 1}-{i + 1} 页连续 3 页 layout 均为 '{layouts[i]}'，违反节奏规则",
                slide_id=deck.pages[i].id,
                suggestion="在连续相同 layout 之间插入节奏页（section / quote / contrast）",
            ))
            break

    # --------------------------------------------------------------
    # P2：叙事弧断裂
    # --------------------------------------------------------------

    if deck.pages and deck.pages[0].layout != "hero":
        issues.append(QualityIssue(
            level="warning",
            code="narrative_arc_break",
            message="首页 layout 不是 'hero'，叙事弧可能断裂",
            suggestion="首页应使用 layout='hero' 作为封面 Hook",
        ))
    if deck.pages and deck.pages[-1].layout != "summary":
        issues.append(QualityIssue(
            level="warning",
            code="narrative_arc_break",
            message="末页 layout 不是 'summary'，叙事弧可能断裂",
            suggestion="末页应使用 layout='summary' 作为收束 Takeaway",
        ))

    # --------------------------------------------------------------
    # P1：页数匹配
    # --------------------------------------------------------------

    if target_slide_count and abs(len(deck.pages) - target_slide_count) > 4:
        issues.append(QualityIssue(
            level="warning",
            code="slide_count_mismatch",
            message=f"页数（{len(deck.pages)}）与目标页数（{target_slide_count}）差距超过 4",
            suggestion="调整素材分组或节奏页数量",
        ))

    # ------------------------------------------------------------------
    # P1：无外部来源
    # ------------------------------------------------------------------

    if not _has_external_sources(deck, content_pack):
        issues.append(QualityIssue(
            level="warning",
            code="prompt_only",
            message="该内容主要由模型生成，未绑定企业原文来源",
            suggestion="如需更高可信度，请补充知识库或原始文档来源",
        ))

    # ------------------------------------------------------------------
    # P0：文档提取失败
    # ------------------------------------------------------------------

    for warn in content_pack.warnings + deck.quality_warnings:
        if "扫描" in warn or "OCR" in warn or "无法提取可读文本" in warn:
            issues.append(QualityIssue(
                level="error",
                code="extraction_failed",
                message=warn,
                suggestion="请改用可提取文本的 PDF、Word、TXT 或 Markdown 文档",
            ))

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------

    error_count = sum(1 for i in issues if i.level == "error")
    warn_count  = sum(1 for i in issues if i.level == "warning")
    passed = error_count == 0
    summary = (
        f"检查完成：{len(deck.pages)} 页，{error_count} 个错误，{warn_count} 个警告。"
        if not passed
        else f"检查通过：{len(deck.pages)} 页，{warn_count} 个警告。"
    )
    return QualityReport(passed=passed, issues=issues, summary=summary)
