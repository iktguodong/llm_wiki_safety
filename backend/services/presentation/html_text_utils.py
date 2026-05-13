"""HTML 链路可复用文本工具（Style A 电子杂志风）。

从 html_planner.py 中拆出，供 html_llm_planner.py / html_quality.py 等共用，
不依赖旧规则规划器的 _SentenceItem / _extract_pool 等结构。
"""

from __future__ import annotations

import re
from typing import Any

from .models import ContentPack, SourceRef

# --------------------------------------------------------------------------
# Boilerplate 短语与关键词
# --------------------------------------------------------------------------

BOILERPLATE_PHRASES: set[str] = {
    "开场介绍培训主题和背景",
    "参考签署页和目录结构",
    "本页目标",
    "请按页面要点讲解",
    "内容将根据来源自动整理",
    "单页即可分享",
}

BOILERPLATE_PATTERNS: list[str] = [
    r"围绕\s*[\u4e00-\u9fff]+\s*形成节奏转换",
    r"重点抓住\s*[\u4e00-\u9fff、]+\s*和\s*[\u4e00-\u9fff、]+",
]

ACTION_KEYWORDS = ("流程", "步骤", "处置", "报警", "上报", "联动", "复盘", "执行")
CHECK_KEYWORDS = ("检查", "核对", "清单", "确认", "排查", "闭环", "落实")
RISK_KEYWORDS = ("风险", "隐患", "事故", "危险", "火灾", "爆炸", "伤害", "失控")
LEGAL_KEYWORDS = ("制度", "职责", "法规", "标准", "要求", "规定", "义务", "责任")

# Layout 登记名单
REGISTERED_LAYOUTS: set[str] = {
    "hero",
    "agenda",
    "section",
    "quote",
    "contrast",
    "workflow",
    "checklist",
    "summary",
    "content",
}


def bullet_limit_for_layout(layout: str) -> int:
    """返回当前 layout 允许的 bullet 数上限。"""
    return 6 if layout in {"agenda", "checklist"} else 5

# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------


def _settings_dict(settings: Any | None) -> dict[str, Any]:
    if settings is None:
        return {}
    if hasattr(settings, "model_dump"):
        return dict(settings.model_dump())
    if isinstance(settings, dict):
        return dict(settings)
    return dict(getattr(settings, "__dict__", {}))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


# --------------------------------------------------------------------------
# 话题清洗
# --------------------------------------------------------------------------


def clean_topic(text: str) -> str:
    """清理话题文本，移除常见的提示前缀、公司名等。"""
    raw = _normalize(text)
    if not raw:
        return "安全培训"
    cleaned = re.sub(
        r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是).*",
        "",
        raw,
    )
    cleaned = re.sub(
        r"^(这是我公司的|这是我们公司的|这是本公司的|这是公司的|我公司的|我们公司的|本公司的|公司的)",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"^(请|请您|请重点|请突出|请围绕|围绕|关于|针对|以|生成|制作|输出|整理|汇总)+",
        "",
        cleaned,
    )
    cleaned = cleaned.strip("：:，,。.;；/\\ ")
    cleaned = re.split(r"[，,。；;]+", cleaned)[0].strip("：:，,。.;；/\\ ")
    return cleaned or "安全培训"


def _looks_like_source_heading(text: str) -> bool:
    compact = _compact(text)
    if not compact:
        return True
    if compact.endswith(("）", ")", "】", "、", "，", "。", "；", ":", "：")):
        return True
    parts = [part for part in re.split(r"[、,，]+", compact) if part]
    if len(parts) >= 3 and len(compact) <= 14 and all(len(part) <= 4 for part in parts):
        return True
    if any(
        marker in compact
        for marker in (
            "目录",
            "签署页",
            "版本号",
            "编制",
            "批准页",
            "应急预案",
            "综合应急预案",
            "专项应急预案",
            "现场处置方案",
            "事故现场处置方案",
        )
    ):
        return True
    if re.match(r"^第[一二三四五六七八九十0-9]+[章节篇部分]", compact):
        return True
    if re.match(r"^[0-9一二三四五六七八九十]+\s*[、.．)]", compact) and len(compact) > 10:
        return True
    if len(compact) > 16 and any(
        token in compact for token in ("预案", "方案", "流程", "处置", "措施", "职责")
    ):
        return True
    return False


def topic_fragments(text: str) -> list[str]:
    """从话题文本中提取碎片关键词。"""
    cleaned = clean_topic(text)
    cleaned = re.sub(
        r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是).*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"^(这是我公司的|这是我们公司的|这是本公司的|这是公司的|我公司的|我们公司的|本公司的|公司的)",
        "",
        cleaned,
    )
    cleaned = cleaned.strip("：:，,。.;；/\\ ")
    clauses = [
        clause.strip() for clause in re.split(r"[，,。；;、]+", cleaned) if clause.strip()
    ]
    fragments: list[str] = []
    for clause in clauses:
        if len(clause) < 3:
            continue
        if re.search(
            r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|面向|针对|适用于)",
            clause,
        ):
            continue
        if _looks_like_source_heading(clause):
            continue
        fragments.append(clause[:18])
    return fragments


# --------------------------------------------------------------------------
# 来源标签
# --------------------------------------------------------------------------


def _source_key(ref: SourceRef) -> str:
    parts = [
        ref.source_type,
        ref.source_id or "",
        ref.kb_id or "",
        ref.document_id or "",
        ref.page_name or "",
        ref.upload_id or "",
        ref.title or "",
    ]
    return "|".join(str(p) for p in parts)


def source_label(ref: SourceRef) -> str:
    for candidate in (
        ref.title,
        ref.page_name,
        ref.document_id,
        ref.upload_id,
        ref.kb_id,
        ref.source_id,
    ):
        if candidate:
            return str(candidate)
    return ref.source_type


def dedupe_refs(refs: list[SourceRef], limit: int = 2) -> list[SourceRef]:
    unique: list[SourceRef] = []
    seen: set[str] = set()
    for ref in refs:
        key = _source_key(ref)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
        if len(unique) >= limit:
            break
    return unique


# --------------------------------------------------------------------------
# Boilerplate 检测
# --------------------------------------------------------------------------


def sentence_is_boilerplate(text: str) -> bool:
    compact = _compact(text)
    if not compact:
        return True
    if compact.startswith("请") or compact.startswith("面向") or compact.startswith("围绕"):
        return True
    if any(
        marker in compact
        for marker in (
            "培训对象为",
            "培训对象是",
            "培训名字为",
            "培训名称为",
            "培训名为",
            "标题为",
            "题目为",
            "名称为",
            "主题为",
        )
    ):
        return True
    if any(
        prefix in compact
        for prefix in (
            "这是我公司的",
            "这是我们公司的",
            "这是本公司的",
            "这是公司的",
            "我公司的",
            "我们公司的",
            "本公司的",
            "公司的",
        )
    ):
        return True
    if compact in BOILERPLATE_PHRASES:
        return True
    if any(phrase in compact for phrase in BOILERPLATE_PHRASES):
        return True
    if compact.startswith("开场介绍") or compact.startswith("参考签署页"):
        return True
    if compact.startswith("本页目标") or compact.startswith("请按页面要点讲解"):
        return True
    if compact.startswith("内容将根据来源"):
        return True
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, compact):
            return True
    return False


# --------------------------------------------------------------------------
# Emoji 检测
# --------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # 杂项符号及图形
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


# --------------------------------------------------------------------------
# 焦点关键词
# --------------------------------------------------------------------------


def focus_terms(pack: ContentPack, settings: dict[str, Any]) -> list[str]:
    """从 ContentPack 提取焦点关键词，不依赖旧规则评分系统。"""
    terms: list[str] = []
    for item in settings.get("focus_areas") or []:
        text = _normalize(item)
        if text:
            terms.append(text)

    for source in (pack.title, pack.topic):
        for token in topic_fragments(source):
            if token == pack.title or token == pack.topic:
                continue
            terms.append(token)

    # 直接从 chunks 扫描安全关键词
    chunk_text = " ".join(
        f"{chunk.title} {chunk.text[:200]}"
        for chunk in pack.chunks[:12]
    )
    safety_keywords = [
        "应急处置",
        "现场处置",
        "报警流程",
        "初期火灾扑救",
        "风险识别",
        "岗位职责",
        "检查清单",
        "复盘闭环",
        "应急响应",
        "事故预防",
        "隐患排查",
        "安全培训",
    ]
    for keyword in safety_keywords:
        if keyword in chunk_text or keyword in pack.topic or keyword in pack.title:
            terms.append(keyword)

    # 去重 + 去子串包含
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.strip("：:，,。.;；/\\ ")
        if not key or key in seen:
            continue
        if key == _normalize(pack.title) or key == _normalize(pack.topic):
            continue
        # 处理子串包含
        if any(key in existing or existing in key for existing in unique):
            if any(len(key) > len(existing) and existing in key for existing in unique):
                unique = [existing for existing in unique if existing not in key]
            elif any(len(existing) >= len(key) and key in existing for existing in unique):
                continue
        seen.add(key)
        unique.append(key)

    if not unique:
        unique = ["应急处置", "现场响应", "行动清单", "总结复盘"]
    elif len(unique) < 4:
        for default_term in [
            "现场处置",
            "响应启动",
            "信息上报",
            "复盘闭环",
            "岗位职责",
            "风险识别",
        ]:
            if len(unique) >= 4:
                break
            if default_term not in unique:
                unique.append(default_term)
    return unique[:6]


# --------------------------------------------------------------------------
# Chunk 来源映射（供 LLM 输出校验用）
# --------------------------------------------------------------------------


def chunk_sources_map(pack: ContentPack) -> dict[str, list[SourceRef]]:
    """构建 chunk_id → source_refs 的映射，供 LLM 输出校验。"""
    return {chunk.id: list(chunk.source_refs) for chunk in pack.chunks}
