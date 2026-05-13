"""独立的 HTML 训练材料规划器。"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from .html_deck import HTML_THEMES, STYLE_A_ONLY, HtmlDeckPage, HtmlDeckSpec
from .models import ContentPack, SourceRef


_BOILERPLATE_PHRASES = {
    "开场介绍培训主题和背景",
    "参考签署页和目录结构",
    "本页目标",
    "请按页面要点讲解",
    "内容将根据来源自动整理",
    "单页即可分享",
}

_ACTION_KEYWORDS = ("流程", "步骤", "处置", "报警", "上报", "联动", "复盘", "执行")
_CHECK_KEYWORDS = ("检查", "核对", "清单", "确认", "排查", "闭环", "落实")
_RISK_KEYWORDS = ("风险", "隐患", "事故", "危险", "火灾", "爆炸", "伤害", "失控")
_LEGAL_KEYWORDS = ("制度", "职责", "法规", "标准", "要求", "规定", "义务", "责任")
_CONTRAST_KEYWORDS = ("不要", "避免", "相反", "而是", "对比", "区别", "误区", "常见")


@dataclass(frozen=True)
class _SentenceItem:
    text: str
    refs: list[SourceRef]
    keywords: list[str]
    score: int


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


def _clean_topic(text: str) -> str:
    raw = _normalize(text)
    if not raw:
        return "安全培训"
    cleaned = re.sub(r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是).*", "", raw)
    cleaned = re.sub(r"^(这是我公司的|这是我们公司的|这是本公司的|这是公司的|我公司的|我们公司的|本公司的|公司的)", "", cleaned)
    cleaned = re.sub(r"^(请|请您|请重点|请突出|请围绕|围绕|关于|针对|以|生成|制作|输出|整理|汇总)+", "", cleaned)
    cleaned = cleaned.strip("：:，,。.;；/\\ ")
    cleaned = re.split(r"[，,。；;]+", cleaned)[0].strip("：:，,。.;；/\\ ")
    return cleaned or "安全培训"


def _topic_fragments(text: str) -> list[str]:
    cleaned = _clean_topic(text)
    cleaned = re.sub(r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是).*", "", cleaned)
    cleaned = re.sub(r"^(这是我公司的|这是我们公司的|这是本公司的|这是公司的|我公司的|我们公司的|本公司的|公司的)", "", cleaned)
    cleaned = cleaned.strip("：:，,。.;；/\\ ")
    clauses = [clause.strip() for clause in re.split(r"[，,。；;、]+", cleaned) if clause.strip()]
    fragments: list[str] = []
    for clause in clauses:
        if len(clause) < 3:
            continue
        if re.search(r"(培训对象|培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|面向|针对|适用于)", clause):
            continue
        if _looks_like_source_heading(clause):
            continue
        fragments.append(clause[:18])
    return fragments


def _strip_markers(text: str) -> str:
    cleaned = _normalize(text)
    cleaned = re.sub(r"^\d+[\.、\)]\s*", "", cleaned)
    cleaned = re.sub(r"^[（(]?\d+[）)]\s*", "", cleaned)
    cleaned = re.sub(r"^[一二三四五六七八九十]+\s*、\s*", "", cleaned)
    cleaned = re.sub(r"^(附件|附录|表[0-9一二三四五六七八九十\-]*)[:：]?", "", cleaned)
    cleaned = cleaned.strip("：:，,。.;；/\\ ")
    return cleaned


def _looks_like_source_heading(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return True
    if compact.endswith(("）", ")", "】", "】", "、", "，", "。", "；", ":", "：")):
        return True
    parts = [part for part in re.split(r"[、,，]+", compact) if part]
    if len(parts) >= 3 and len(compact) <= 14 and all(len(part) <= 4 for part in parts):
        return True
    if any(marker in compact for marker in (
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
    )):
        return True
    if re.match(r"^第[一二三四五六七八九十0-9]+[章节篇部分]", compact):
        return True
    if re.match(r"^[0-9一二三四五六七八九十]+\s*[、.．)]", compact) and len(compact) > 10:
        return True
    if len(compact) > 16 and any(token in compact for token in ("预案", "方案", "流程", "处置", "措施", "职责")):
        return True
    return False


def _condense_statement(text: str, *, keywords: list[str] | None = None, limit: int = 22) -> str:
    cleaned = _strip_markers(text)
    cleaned = re.sub(r"^(绥中港集团有限公司|公司|本公司)?\s*生产安全事故应急预案.*", "", cleaned)
    cleaned = re.sub(r"^(综合应急预案|专项应急预案|现场处置方案|事故现场处置方案|应急预案执行部门签署页|应急预案目录|目录).*", "", cleaned)
    cleaned = re.sub(r"(绥中港集团有限公司生产安全事故应急预案|生产安全事故应急预案|应急预案版本号|预案编号|批准页|公司各部门、各单位).*", "", cleaned)
    cleaned = _clean_topic(cleaned)
    clauses = [clause.strip("：:，,。.;；/\\ ") for clause in re.split(r"[。！？!?；;\n，,、]+", cleaned) if clause.strip()]
    keywords = [kw for kw in (keywords or []) if kw]
    best = ""
    best_score = -1
    for clause in clauses:
        clause = _strip_markers(clause)
        if _sentence_is_boilerplate(clause):
            continue
        if _looks_like_source_heading(clause) and len(re.sub(r"\s+", "", clause)) > 6:
            continue
        score = 0
        compact = re.sub(r"\s+", "", clause)
        for kw in keywords:
            if kw in compact:
                score += 4
        for token in _ACTION_KEYWORDS + _CHECK_KEYWORDS + _RISK_KEYWORDS + _LEGAL_KEYWORDS:
            if token in compact:
                score += 1
        if 4 <= len(compact) <= limit:
            score += 2
        if len(compact) <= limit:
            score += 1
        if score > best_score or (score == best_score and len(compact) < len(best)):
            best = clause
            best_score = score

    if not best:
        best = _strip_markers(cleaned)
    if _looks_like_source_heading(best):
        return ""
    best = re.sub(r"^(应急响应流程|应急处置流程|响应流程|应急处置|处置措施|应急措施|应急工作组|应急专家组)[:：\-\s]*", "", best)
    best = re.sub(r"^(公司|本预案|本次培训|培训内容|培训对象)[:：\s]*", "", best)
    best = re.sub(r"^[\-–—\s]+", "", best)
    best = re.sub(r"^(从|在|由|将|至|向)\s*", "", best)
    if len(best) > limit:
        best = best[:limit].rstrip("，,。.;；/\\") + "…"
    return best or _normalize(text)[:limit]


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
    return "|".join(parts)


def _source_label(ref: SourceRef) -> str:
    for candidate in (ref.title, ref.page_name, ref.document_id, ref.upload_id, ref.kb_id, ref.source_id):
        if candidate:
            return str(candidate)
    return ref.source_type


def _dedupe_refs(refs: list[SourceRef], limit: int = 2) -> list[SourceRef]:
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


def _sentence_score(text: str, keywords: list[str]) -> int:
    score = 0
    compact = re.sub(r"\s+", "", text)
    if 8 <= len(compact) <= 40:
        score += 1
    if len(compact) > 16:
        score += 1
    for token in keywords:
        if token and token in compact:
            score += 2
    for token in (*_ACTION_KEYWORDS, *_CHECK_KEYWORDS, *_RISK_KEYWORDS, *_LEGAL_KEYWORDS, *_CONTRAST_KEYWORDS):
        if token in compact:
            score += 1
    return score


def _sentence_is_boilerplate(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return True
    if compact.startswith("请") or compact.startswith("面向") or compact.startswith("围绕"):
        return True
    if any(marker in compact for marker in ("培训对象为", "培训对象是", "培训名字为", "培训名称为", "培训名为", "标题为", "题目为", "名称为", "主题为")):
        return True
    if any(prefix in compact for prefix in ("这是我公司的", "这是我们公司的", "这是本公司的", "这是公司的", "我公司的", "我们公司的", "本公司的", "公司的")):
        return True
    if compact in _BOILERPLATE_PHRASES:
        return True
    if any(phrase in compact for phrase in _BOILERPLATE_PHRASES):
        return True
    if compact.startswith("开场介绍") or compact.startswith("参考签署页"):
        return True
    if compact.startswith("本页目标") or compact.startswith("请按页面要点讲解"):
        return True
    if compact.startswith("内容将根据来源"):
        return True
    if len(compact) <= 6 and not any(token in compact for token in _ACTION_KEYWORDS + _CHECK_KEYWORDS + _RISK_KEYWORDS + _LEGAL_KEYWORDS):
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    pieces = re.split(r"[。！？!?；;\n]+", str(text or ""))
    return [piece.strip() for piece in pieces if piece.strip()]


def _extract_pool(pack: ContentPack) -> list[_SentenceItem]:
    pool: list[_SentenceItem] = []
    seen: set[str] = set()
    for chunk in pack.chunks:
        chunk_text = _normalize(chunk.text)
        if not chunk_text:
            continue
        for sentence in _split_sentences(chunk_text):
            text = _normalize(sentence)
            compact = re.sub(r"\s+", "", text)
            if not compact or compact in seen:
                continue
            if _sentence_is_boilerplate(text):
                continue
            score = _sentence_score(text, list(chunk.keywords))
            if score <= 0:
                continue
            condensed = _condense_statement(text, keywords=list(chunk.keywords), limit=26)
            if _sentence_is_boilerplate(condensed):
                continue
            pool.append(_SentenceItem(text=condensed, refs=list(chunk.source_refs), keywords=list(chunk.keywords), score=score))
            seen.add(compact)
    pool.sort(key=lambda item: (-(item.score), len(item.text)))
    return pool[:18]


def _fallback_bullets(pack: ContentPack) -> list[_SentenceItem]:
    bullets = [
        _SentenceItem(
            text=f"围绕 {pack.audience} 的实际工作场景，聚焦 {pack.title or pack.topic} 的关键动作。",
            refs=[],
            keywords=[],
            score=2,
        ),
        _SentenceItem(
            text="页面将优先突出可执行步骤、现场提醒和复盘清单。",
            refs=[],
            keywords=[],
            score=1,
        ),
        _SentenceItem(
            text="来源信息保持在辅助位置，不抢占正文注意力。",
            refs=[],
            keywords=[],
            score=1,
        ),
    ]
    return bullets


def _focus_terms(pack: ContentPack, settings: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for item in settings.get("focus_areas") or []:
        text = _normalize(item)
        if text:
            terms.append(text)

    for source in (pack.title, pack.topic):
        for token in _topic_fragments(source):
            if token == pack.title or token == pack.topic:
                continue
            terms.append(token)

    keywords = [
        "应急处置",
        "现场处置",
        "报警流程",
        "初期火灾扑救",
        "风险识别",
        "岗位职责",
        "检查清单",
        "复盘闭环",
    ]
    joined = " ".join(item.text for item in _extract_pool(pack))
    for keyword in keywords:
        if keyword in joined or keyword in pack.topic or keyword in pack.title:
            terms.append(keyword)

    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.strip("：:，,。.;；/\\ ")
        if not key or key in seen:
            continue
        if key == _normalize(pack.title) or key == _normalize(pack.topic):
            continue
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
        for default_term in ["现场处置", "响应启动", "信息上报", "复盘闭环", "岗位职责", "风险识别"]:
            if len(unique) >= 4:
                break
            if default_term not in unique:
                unique.append(default_term)
    return unique[:6]


def _group_items(items: list[_SentenceItem], group_size: int) -> list[list[_SentenceItem]]:
    group_size = max(1, group_size)
    return [items[idx : idx + group_size] for idx in range(0, len(items), group_size)]


def _page_title(items: list[_SentenceItem], fallback: str) -> str:
    if not items:
        return fallback
    first = _condense_statement(items[0].text, keywords=items[0].keywords, limit=16)
    if first and 3 <= len(first) <= 14 and not _sentence_is_boilerplate(first) and not _looks_like_source_heading(first):
        return first
    tokens: list[str] = []
    seen: set[str] = set()
    for item in items[:2]:
        for token in item.keywords[:2]:
            token = _normalize(token)
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    joined = "、".join(tokens)
    if 3 <= len(joined) <= 14 and not _looks_like_source_heading(joined):
        return joined
    return fallback


def _page_summary(items: list[_SentenceItem], pack: ContentPack) -> str:
    if not items:
        return f"围绕 {pack.audience} 的场景展开，强调可执行的培训动作。"
    if len(items) == 1:
        summary = _condense_statement(items[0].text, keywords=items[0].keywords, limit=28)
        if summary:
            return summary
        return f"围绕 {pack.audience} 的关键动作展开。"
    if len(items) == 2:
        left = _condense_statement(items[0].text, keywords=items[0].keywords, limit=20)
        right = _condense_statement(items[1].text, keywords=items[1].keywords, limit=20)
        if left or right:
            return f"{left or '关键动作'}；{right or '执行提醒'}"
    left = _condense_statement(items[0].text, keywords=items[0].keywords, limit=18)
    right = _condense_statement(items[1].text, keywords=items[1].keywords, limit=18)
    if not left and not right:
        return f"围绕 {pack.audience} 的关键动作展开。"
    return f"{left or '关键动作'} · {right or '执行提醒'}"


def _page_notes(items: list[_SentenceItem], pack: ContentPack, settings: dict[str, Any]) -> str:
    terms = [term for term in _focus_terms(pack, settings)[:3] if term]
    if terms:
        return f"重点抓住 {terms[0]}、{terms[1] if len(terms) > 1 else '关键动作'} 和 {terms[2] if len(terms) > 2 else '执行闭环'}。"
    return "把可执行动作放在前面，来源保持辅助即可。"


def _pick_layout(group: list[_SentenceItem], group_index: int, total_groups: int, is_rhythm: bool = False, rhythm_kind: str = "section") -> str:
    joined = " ".join(item.text for item in group)
    if is_rhythm:
        return rhythm_kind
    if any(token in joined for token in _ACTION_KEYWORDS):
        return "workflow"
    if any(token in joined for token in _CHECK_KEYWORDS):
        return "checklist"
    if any(token in joined for token in _RISK_KEYWORDS):
        return "contrast" if "不要" in joined or "避免" in joined else "quote"
    if any(token in joined for token in _LEGAL_KEYWORDS):
        return "section" if group_index % 2 == 0 else "content"
    if group_index == 0:
        return "section"
    if group_index == total_groups - 1:
        return "summary"
    if group_index % 4 == 1:
        return "quote"
    if group_index % 4 == 2:
        return "content"
    return "content"


def _page_bullets(group: list[_SentenceItem]) -> list[str]:
    bullets: list[str] = []
    seen: set[str] = set()
    for item in group:
        text = _condense_statement(item.text, keywords=item.keywords, limit=28)
        key = re.sub(r"\s+", "", text)
        if not text or key in seen:
            continue
        seen.add(key)
        bullets.append(text)
    return bullets[:5]


def _page_refs(group: list[_SentenceItem]) -> list[SourceRef]:
    refs: list[SourceRef] = []
    for item in group:
        refs.extend(item.refs)
    return _dedupe_refs(refs, limit=2)


def _split_groups(items: list[_SentenceItem], target_groups: int) -> list[list[_SentenceItem]]:
    if not items:
        return []
    target_groups = max(1, target_groups)
    group_size = max(1, math.ceil(len(items) / target_groups))
    groups = _group_items(items, group_size)
    if len(groups) > target_groups:
        merged: list[list[_SentenceItem]] = []
        buffer: list[_SentenceItem] = []
        for group in groups:
            buffer.extend(group)
            if len(merged) + 1 >= target_groups:
                continue
            if len(buffer) >= group_size:
                merged.append(buffer)
                buffer = []
        if buffer:
            merged.append(buffer)
        groups = merged
    return groups


def _distribute_counts(total: int, slots: int) -> list[int]:
    slots = max(1, slots)
    total = max(0, total)
    base, remainder = divmod(total, slots)
    counts = [base] * slots
    for idx in range(remainder):
        counts[idx] += 1
    return counts


def _rhythm_pages(pack: ContentPack, settings: dict[str, Any], count: int) -> list[HtmlDeckPage]:
    if count <= 0:
        return []
    terms = [term for term in _focus_terms(pack, settings) if term and term != pack.title and not _looks_like_source_heading(term)]
    if not terms:
        terms = ["应急处置", "现场处置", "行动清单"]
    pages: list[HtmlDeckPage] = []
    rhythm_cycle = ["section", "quote", "contrast"]
    for idx in range(count):
        term = terms[idx % len(terms)] if terms else f"阶段 {idx + 1}"
        layout = rhythm_cycle[idx % len(rhythm_cycle)]
        bullets = [f"聚焦 {term}", f"面向 {pack.audience} 的现场动作", "把来源信息保留在辅助位置"]
        refs: list[SourceRef] = []
        pages.append(
            HtmlDeckPage(
                id=f"html-rhythm-{uuid.uuid4().hex[:8]}",
                page_no=0,
                layout=layout,
                title=term,
                subtitle=pack.audience,
                summary=f"围绕 {term} 形成节奏转换。",
                bullets=bullets,
                notes=f"围绕 {term} 形成节奏转换。",
                source_refs=refs,
                hero=False,
            )
        )
    return pages


def _cover_page(pack: ContentPack, settings: dict[str, Any]) -> HtmlDeckPage:
    terms = _focus_terms(pack, settings)
    lead_terms = [term for term in terms if term and term != pack.title][:2]
    if not lead_terms:
        lead_terms = terms[:2] if terms else []
    if lead_terms:
        subtitle = f"面向 {pack.audience}，围绕 {('、'.join(lead_terms))} 展开。"
    else:
        subtitle = f"面向 {pack.audience}，围绕可执行动作展开。"
    return HtmlDeckPage(
        id=f"html-cover-{uuid.uuid4().hex[:8]}",
        page_no=1,
        layout="hero",
        title=pack.title,
        subtitle=subtitle,
        summary=f"{pack.duration_minutes} 分钟 · {pack.audience}",
        bullets=[
            f"培训对象：{pack.audience}",
            f"培训时长：{pack.duration_minutes} 分钟",
            f"主题聚焦：{lead_terms[0] if lead_terms else '关键动作'}",
        ],
        notes=f"把 {lead_terms[0] if lead_terms else '关键动作'} 作为主线，围绕可执行动作展开。",
        source_refs=_dedupe_refs([ref for chunk in pack.chunks for ref in chunk.source_refs], limit=2),
        hero=True,
    )


def _agenda_page(pack: ContentPack, settings: dict[str, Any], items: list[_SentenceItem]) -> HtmlDeckPage:
    terms = _focus_terms(pack, settings)
    bullets: list[str] = []
    for idx, term in enumerate(terms[:5], start=1):
        bullets.append(f"{idx:02d}. {term}")
    if not bullets:
        bullets = ["01. 目标与对象", "02. 风险与场景", "03. 行动与复盘"]
    if terms:
        summary = f"围绕 {terms[0]}、{terms[1] if len(terms) > 1 else '关键动作'}、{terms[2] if len(terms) > 2 else '执行闭环'} 展开。"
    else:
        summary = f"围绕 {pack.audience} 排出可执行路线。"
    return HtmlDeckPage(
        id=f"html-agenda-{uuid.uuid4().hex[:8]}",
        page_no=2,
        layout="agenda",
        title="培训路线图",
        subtitle=pack.title,
        summary=summary,
        bullets=bullets,
        notes="先搭骨架，再进入具体动作。",
        source_refs=_dedupe_refs([ref for item in items[:4] for ref in item.refs], limit=2),
        hero=False,
    )


def _summary_page(pack: ContentPack, items: list[_SentenceItem], page_no: int) -> HtmlDeckPage:
    terms = [term for term in _focus_terms(pack, {}) if term]
    bullets = [
        f"面向 {pack.audience} 形成现场执行清单。",
        f"聚焦 {terms[0] if terms else '关键动作'}。",
        "来源保持辅助，内容优先可读、可扫、可执行。",
    ]
    return HtmlDeckPage(
        id=f"html-summary-{uuid.uuid4().hex[:8]}",
        page_no=page_no,
        layout="summary",
        title="收束与行动",
        subtitle=pack.title,
        summary=f"{pack.audience} 的关键动作与现场提醒。",
        bullets=bullets,
        notes="把最重要的动作收拢成一页可带走的清单。",
        source_refs=_page_refs(items),
        hero=False,
    )


def build_html_deck(content_pack: ContentPack, settings: Any) -> HtmlDeckSpec:
    settings_dict = _settings_dict(settings)
    title = content_pack.title or _clean_topic(settings_dict.get("topic") or content_pack.topic)
    theme = str(settings_dict.get("theme") or "ink")
    render_style = str(settings_dict.get("render_style") or settings_dict.get("deck_style") or "magazine")
    target_pages = max(5, int(settings_dict.get("slide_count") or 12))
    # Style A 锁定：本项目只允许 Style A 电子杂志风，禁止 Style B（swiss）。
    style = STYLE_A_ONLY
    theme = theme if theme in HTML_THEMES else "ink"
    focus_terms = [term for term in _focus_terms(content_pack, settings_dict) if term and term != content_pack.title]
    if not focus_terms:
        focus_terms = [term for term in _focus_terms(content_pack, settings_dict) if term]

    pool = _extract_pool(content_pack)
    if not pool:
        pool = _fallback_bullets(content_pack)

    page_budget = max(1, target_pages - 3)
    body_groups = _split_groups(pool, page_budget)
    if not body_groups:
        body_groups = [_fallback_bullets(content_pack)]

    # 用少量节奏页把页面推向 guizang 式的编辑感，而不是一连串重复卡片。
    extra_needed = max(0, page_budget - len(body_groups))
    rhythm_pages = _rhythm_pages(content_pack, settings_dict, extra_needed)
    rhythm_index = 0
    rhythm_slots = _distribute_counts(len(rhythm_pages), len(body_groups) + 1)

    pages: list[HtmlDeckPage] = []
    pages.append(_cover_page(content_pack, settings_dict))
    pages.append(_agenda_page(content_pack, settings_dict, pool))

    for slot_index in range(len(body_groups) + 1):
        for _ in range(rhythm_slots[slot_index]):
            if rhythm_index >= len(rhythm_pages):
                break
            page = rhythm_pages[rhythm_index]
            pages.append(
                HtmlDeckPage(
                    id=page.id,
                    page_no=len(pages) + 1,
                    layout=page.layout,
                    title=page.title,
                    subtitle=page.subtitle,
                    summary=page.summary,
                    bullets=page.bullets,
                    notes=page.notes,
                    source_refs=page.source_refs,
                    hero=page.hero,
                )
            )
            rhythm_index += 1
        if slot_index >= len(body_groups):
            continue
        group = body_groups[slot_index]
        bullets = _page_bullets(group)
        page_refs = _page_refs(group)
        layout = _pick_layout(group, slot_index, len(body_groups))
        page_title = _page_title(group, fallback="")
        if not page_title or page_title == content_pack.title or len(page_title) > 14:
            if focus_terms:
                page_title = focus_terms[slot_index % len(focus_terms)]
            else:
                page_title = {
                    "section": "主题展开",
                    "quote": "要点摘录",
                    "contrast": "对照提醒",
                    "workflow": "流程拆解",
                    "checklist": "检查清单",
                    "summary": "行动清单",
                }.get(layout, "内容展开")
        if layout == "section":
            summary = _page_summary(group[:2], content_pack)
        elif layout == "quote":
            summary = group[0].text if group else _page_summary(group, content_pack)
        else:
            summary = _page_summary(group, content_pack)

        notes = _page_notes(group, content_pack, settings_dict)
        if layout == "contrast" and len(bullets) >= 2:
            bullets = [bullets[0], f"避免：{bullets[1]}", *bullets[2:]]
        subtitle_map = {
            "section": "节奏页",
            "quote": "要点摘录",
            "workflow": "行动路径",
            "checklist": "核查动作",
            "contrast": "对比提醒",
            "summary": "收束清单",
            "content": "内容展开",
        }
        pages.append(
            HtmlDeckPage(
                id=f"html-page-{uuid.uuid4().hex[:8]}",
                page_no=len(pages) + 1,
                layout=layout,
                title=page_title,
                subtitle=subtitle_map.get(layout, "内容展开"),
                summary=summary,
                bullets=bullets,
                notes=notes,
                source_refs=page_refs,
                hero=False,
            )
        )

    pages.append(_summary_page(content_pack, pool[-3:], len(pages) + 1))

    for idx, page in enumerate(pages, start=1):
        object.__setattr__(page, "page_no", idx)

    warnings = list(content_pack.warnings)
    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
        warnings.append("该 HTML 内容主要由模型生成，未绑定企业原文来源")

    return HtmlDeckSpec(
        id=f"html-{content_pack.id}",
        title=title,
        topic=content_pack.topic,
        audience=content_pack.audience,
        duration_minutes=content_pack.duration_minutes,
        style=style,
        theme=theme,
        template_id=STYLE_A_ONLY,
        pages=pages,
        quality_warnings=warnings,
    )
