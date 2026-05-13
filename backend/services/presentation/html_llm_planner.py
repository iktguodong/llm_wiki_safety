"""HTML 链路 LLM 规划器（Style A 电子杂志风，guizang-ppt-skill）。

独立于 PPT 链路，不复用 outline_builder；只读 current_model_id。
LLM 失败或输出违反强约束 -> 直接抛 HtmlGenerationError -> app 层转 400。
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from backend.config import config
from backend.services.llm import llm_service

from .html_deck import HTML_THEMES, STYLE_A_ONLY, HtmlDeckPage, HtmlDeckSpec
from .html_text_utils import (
    BOILERPLATE_PATTERNS,
    BOILERPLATE_PHRASES,
    REGISTERED_LAYOUTS,
    _compact,
    _normalize,
    _settings_dict,
    chunk_sources_map,
    clean_topic,
    dedupe_refs,
    focus_terms,
    has_emoji,
    sentence_is_boilerplate,
)
from .models import ContentPack, SourceRef

# --------------------------------------------------------------------------
# 异常类
# --------------------------------------------------------------------------


class HtmlGenerationError(ValueError):
    """HTML 生成链路专用异常，app 层捕获后转 4xx。"""
    pass


# --------------------------------------------------------------------------
# 模型检查
# --------------------------------------------------------------------------


def _check_model_available() -> str | None:
    """返回当前可用 model_id；未配置返回 None。"""
    model_id = config.get("current_model_id")
    if not model_id:
        return None
    providers = config.get("models", {}).get("providers", [])
    for provider in providers:
        if not provider.get("api_key"):
            continue
        for model in provider.get("models", []):
            if model.get("id") == model_id:
                return model_id
    return None


# --------------------------------------------------------------------------
# 提取 JSON
# --------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取 JSON 对象。"""
    cleaned = text.strip()
    # 剥离 markdown fence
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    for start_char in ("{", "["):
        start = cleaned.find(start_char)
        if start == -1:
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


# --------------------------------------------------------------------------
# Prompt 构建
# --------------------------------------------------------------------------


def _raw_chunks_text(pack: ContentPack, max_chars: int = 12000) -> str:
    """把 ContentPack.chunks 格式化为 LLM 输入。"""
    parts: list[str] = []
    total_chars = 0
    for idx, chunk in enumerate(pack.chunks, start=1):
        ref_labels = ", ".join(
            (ref.title or ref.document_id or ref.page_name or ref.source_type)
            for ref in chunk.source_refs[:2]
        )
        header = f"### chunk-{idx} (id={chunk.id}"
        if ref_labels:
            header += f", 来源: {ref_labels}"
        header += ")"
        body = chunk.text[:1200]
        block = f"{header}\n{body}"
        if total_chars + len(block) > max_chars and total_chars > 0:
            parts.append(f"\n(后续 {len(pack.chunks) - idx + 1} 段已截断，共 {len(pack.chunks)} 段)")
            break
        parts.append(block)
        total_chars += len(block)
    return "\n\n".join(parts)


def _build_html_prompt(
    content_pack: ContentPack, settings: dict[str, Any]
) -> tuple[str, str]:
    """构建 system + user prompt。"""

    topic = content_pack.title or clean_topic(
        settings.get("topic") or content_pack.topic
    )
    audience = settings.get("audience") or content_pack.audience or "一线员工"
    duration = int(
        settings.get("duration_minutes") or content_pack.duration_minutes or 60
    )
    theme_name = settings.get("theme") or "ink"
    slide_count = int(settings.get("slide_count") or 12)

    terms = focus_terms(content_pack, settings)
    terms_str = ", ".join(terms) if terms else "应急处置, 现场响应, 行动清单"

    settings_json = json.dumps(
        {
            "title": topic,
            "audience": audience,
            "duration_minutes": duration,
            "slide_count": slide_count,
            "theme": theme_name,
            "focus_areas": terms,
        },
        ensure_ascii=False,
    )

    chunk_text = _raw_chunks_text(content_pack)

    system = f"""你是杂志风 (Style A) 网页 PPT 的内容架构师，严格遵守 op7418/guizang-ppt-skill 的规约。
- 只能输出 JSON 对象，不要 Markdown，不要代码块，不要解释。
- 只能从以下 9 个 layout 中选：
  hero, agenda, section, quote, contrast, workflow, checklist, summary, content
- 叙事弧顺序：第 1 页必须 hero（封面 Hook）；第 2 页建议 agenda；
  中段 3-5 个 core 页（content / workflow / checklist 等）；
  在 core 之间插入 1-2 个节奏页（section / quote / contrast）；
  最后一页必须 summary（Takeaway）。
- 全 deck 不允许 emoji；不允许「本页目标 / 请按页面要点讲解 / 内容将根据来源自动整理 / 围绕…形成节奏转换」这类模板话术。
- 每页 chrome（栏目标签）不能等于 kicker（本页钩子）；两者不能互相翻译。
- title ≤ 14 个汉字等价字符；每页 bullets ≤ 5 条且每条 ≤ 40 字。
- 不允许编造企业事实、法规条款、岗位职责、来源；只能基于「输入材料」提炼或合理重组。
- 当前主题色为 {theme_name}，调性是电子杂志 × 电子墨水，衬线标题 + 非衬线正文 + 等宽元数据。"""

    user = f"""【培训设置】
{settings_json}

【焦点关键词】
{terms_str}

【主题】
title: {topic}
audience: {audience}
duration: {duration} 分钟
theme: {theme_name}

【输入材料】（每段最多 1200 字，共最多 12000 字）
{chunk_text}

【输出 JSON 结构】
{{
  "pages": [
    {{
      "page_no": 1,
      "layout": "hero",
      "kicker": "私享会 · 2026.05",
      "chrome": "Training · Vol.01",
      "title": "…",
      "subtitle": "…",
      "summary": "…",
      "bullets": ["…", "…"],
      "notes": "…",
      "source_chunk_ids": ["chunk-1"]
    }}
  ]
}}"""

    return system, user


# --------------------------------------------------------------------------
# LLM 输出强校验
# --------------------------------------------------------------------------


def _has_boilerplate(text: str) -> bool:
    """检测是否包含模板化话术。"""
    if sentence_is_boilerplate(text):
        return True
    for phrase in BOILERPLATE_PHRASES:
        if phrase in text:
            return True
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, text):
            return True
    # 额外检测 "围绕…形成节奏转换"
    if re.search(r"围绕\s*[\u4e00-\u9fff]+[\u4e00-\u9fff\s]*形成", text):
        return True
    return False


def _validate_pages(
    raw_pages: list[dict[str, Any]],
    content_pack: ContentPack,
    settings: dict[str, Any],
) -> list[HtmlDeckPage]:
    """强校验 LLM 输出的 pages 列表。任一项不通过抛 HtmlGenerationError。"""

    slide_count = int(settings.get("slide_count") or 12)

    if not raw_pages:
        raise HtmlGenerationError("LLM 未返回任何页面")

    if len(raw_pages) < 5:
        raise HtmlGenerationError(
            f"LLM 页面数 {len(raw_pages)} 少于最小 5 页"
        )
    if len(raw_pages) > slide_count + 4:
        raise HtmlGenerationError(
            f"LLM 页面数 {len(raw_pages)} 超过上限 {slide_count + 4}"
        )

    # 首页必须 hero
    first_layout = str(raw_pages[0].get("layout", "")).strip()
    if first_layout != "hero":
        raise HtmlGenerationError(
            f"第 1 页 layout 为 '{first_layout}'，必须为 'hero'"
        )

    # 末页必须 summary
    last_layout = str(raw_pages[-1].get("layout", "")).strip()
    if last_layout != "summary":
        raise HtmlGenerationError(
            f"最后一页 layout 为 '{last_layout}'，必须为 'summary'"
        )

    # chunk 映射
    chunk_map = chunk_sources_map(content_pack)

    pages: list[HtmlDeckPage] = []
    prev_layouts: list[str] = []

    for idx, raw in enumerate(raw_pages):
        page_no = idx + 1
        layout = str(raw.get("layout", "")).strip()

        # layout 合法性
        if layout not in REGISTERED_LAYOUTS:
            raise HtmlGenerationError(
                f"第 {page_no} 页 layout '{layout}' 不在登记名单中；"
                f"只允许：{', '.join(sorted(REGISTERED_LAYOUTS))}"
            )

        title = str(raw.get("title", "")).strip()
        if not title:
            raise HtmlGenerationError(f"第 {page_no} 页标题为空")

        # 标题长度
        title_compact = _compact(title)
        if len(title_compact) > 16:
            raise HtmlGenerationError(
                f"第 {page_no} 页标题 '{title[:20]}…' 过长（{len(title_compact)} 字，上限 16）"
            )

        subtitle = str(raw.get("subtitle", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        notes = str(raw.get("notes", "")).strip()
        kicker = str(raw.get("kicker", "")).strip()
        chrome = str(raw.get("chrome", "")).strip()

        raw_bullets = raw.get("bullets") or []
        if not isinstance(raw_bullets, list):
            raise HtmlGenerationError(
                f"第 {page_no} 页 bullets 不是数组"
            )
        bullets = [str(b).strip() for b in raw_bullets if str(b).strip()]

        # emoji 检查
        for field_label, field_val in [
            ("title", title),
            ("subtitle", subtitle),
            ("summary", summary),
            ("notes", notes),
            ("kicker", kicker),
            ("chrome", chrome),
        ]:
            if field_val and has_emoji(field_val):
                raise HtmlGenerationError(
                    f"第 {page_no} 页 {field_label} 含 emoji：'{field_val[:30]}'"
                )
        for bi, bullet in enumerate(bullets):
            if has_emoji(bullet):
                raise HtmlGenerationError(
                    f"第 {page_no} 页 bullet[{bi}] 含 emoji：'{bullet[:30]}'"
                )

        # boilerplate 检查
        text_blob = " ".join(
            x for x in [title, subtitle, summary, notes, kicker, *bullets] if x
        )
        if _has_boilerplate(text_blob):
            # 找到具体哪个字段
            for field_label, field_val in [
                ("title", title),
                ("subtitle", subtitle),
                ("summary", summary),
                ("notes", notes),
                ("kicker", kicker),
            ]:
                if field_val and _has_boilerplate(field_val):
                    raise HtmlGenerationError(
                        f"第 {page_no} 页 {field_label} 含模板话术：'{field_val[:40]}'"
                    )
            raise HtmlGenerationError(
                f"第 {page_no} 页内容含模板化话术"
            )

        # chrome ≠ kicker
        if kicker and chrome and _compact(kicker) == _compact(chrome):
            raise HtmlGenerationError(
                f"第 {page_no} 页 chrome 与 kicker 相同：'{kicker}'"
            )

        # bullet 数量 & 长度
        if len(bullets) > 5:
            raise HtmlGenerationError(
                f"第 {page_no} 页 bullet 数量 {len(bullets)} 超过 5"
            )
        for bi, bullet in enumerate(bullets):
            if _compact(bullet) and len(_compact(bullet)) > 40:
                raise HtmlGenerationError(
                    f"第 {page_no} 页 bullet[{bi}] 过长（{len(_compact(bullet))} 字）：'{bullet[:30]}…'"
                )

        # 节奏规则：不能连续 3 页相同 layout
        prev_layouts.append(layout)
        if len(prev_layouts) >= 3 and len(set(prev_layouts[-3:])) == 1:
            raise HtmlGenerationError(
                f"第 {page_no} 页：连续 3 页 layout 均为 '{layout}'，违反节奏规则"
            )

        # source_chunk_ids 映射到 source_refs
        source_chunk_ids = raw.get("source_chunk_ids") or []
        if isinstance(source_chunk_ids, list):
            refs: list[SourceRef] = []
            for cid in source_chunk_ids:
                cid_str = str(cid).strip()
                if cid_str in chunk_map:
                    refs.extend(chunk_map[cid_str])
            refs = dedupe_refs(refs, limit=2)
        else:
            refs = []

        pages.append(
            HtmlDeckPage(
                id=f"html-llm-{uuid.uuid4().hex[:8]}",
                page_no=page_no,
                layout=layout,
                title=title,
                subtitle=subtitle,
                summary=summary,
                bullets=bullets,
                notes=notes,
                source_refs=refs,
                hero=(layout == "hero"),
                kicker=kicker,
                chrome=chrome,
            )
        )

    return pages


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------


async def build_html_deck_llm(
    content_pack: ContentPack, settings: Any
) -> HtmlDeckSpec:
    """LLM 主导的 HTML Deck 生成。

    返回值仅限成功路径；任何失败抛 HtmlGenerationError。
    """
    settings_dict = _settings_dict(settings)

    # 1. 模型可用性
    model_id = _check_model_available()
    if not model_id:
        raise HtmlGenerationError(
            "未配置当前模型或缺少 API Key，HTML 生成需要 LLM。"
            "请在设置中配置模型并填入有效的 API Key。"
        )

    # 2. 基本字段
    title_text = content_pack.title or clean_topic(
        settings_dict.get("topic") or content_pack.topic
    )
    theme_name = str(
        settings_dict.get("theme")
        or settings_dict.get("render_style")
        or "ink"
    )
    if theme_name not in HTML_THEMES:
        theme_name = "ink"

    # 3. 构建 prompt + 调用 LLM
    system_prompt, user_prompt = _build_html_prompt(content_pack, settings_dict)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw_response = await llm_service.chat_sync(
            messages, model_id=model_id, temperature=0.3
        )
    except Exception as exc:
        raise HtmlGenerationError(
            f"LLM 调用失败：{exc}"
        ) from exc

    if not raw_response or not raw_response.strip():
        raise HtmlGenerationError("LLM 返回空内容")

    # 4. 提取 JSON
    data = _extract_json(raw_response)
    if not data:
        snippet = raw_response[:300].replace("\n", "\\n")
        raise HtmlGenerationError(
            f"LLM 返回内容不是合法 JSON。"
            f"前 300 字符：{snippet}"
        )

    raw_pages = data.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise HtmlGenerationError("LLM 返回 JSON 缺少 pages 数组")

    # 5. 强校验 + 规范化
    pages = _validate_pages(raw_pages, content_pack, settings_dict)

    # 6. 组装返回
    warnings: list[str] = list(content_pack.warnings)
    if not any(
        ref.source_type != "prompt"
        for chunk in content_pack.chunks
        for ref in chunk.source_refs
    ):
        warnings.append(
            "该 HTML 内容主要由模型生成，未绑定企业原文来源"
        )

    return HtmlDeckSpec(
        id=f"html-{content_pack.id}",
        title=title_text,
        topic=content_pack.topic,
        audience=settings_dict.get("audience") or content_pack.audience,
        duration_minutes=int(
            settings_dict.get("duration_minutes")
            or content_pack.duration_minutes
            or 60
        ),
        style=STYLE_A_ONLY,
        theme=theme_name,
        template_id=STYLE_A_ONLY,
        pages=pages,
        quality_warnings=warnings,
    )
