"""HTML deck rendering for the training workflow."""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .models import ContentPack, PresentationSpec, SlideSpec, SourceRef
from .project_store import get_job_paths


HTML_THEMES: dict[str, dict[str, str]] = {
    "ink": {
        "paper": "#ffffff",
        "paper_alt": "#f5f7fa",
        "ink": "#111111",
        "muted": "#505050",
        "accent": "#202124",
        "accent_soft": "rgba(32,33,36,.05)",
        "card": "rgba(255,255,255,.96)",
        "border": "rgba(17,17,17,.07)",
        "shadow": "0 20px 44px rgba(17,17,17,.06)",
    },
    "indigo": {
        "paper": "#f2f4f8",
        "paper_alt": "#e3e9f4",
        "ink": "#10223f",
        "muted": "#4b5970",
        "accent": "#325dff",
        "accent_soft": "rgba(50,93,255,.10)",
        "card": "rgba(255,255,255,.82)",
        "border": "rgba(16,34,63,.10)",
        "shadow": "0 22px 50px rgba(16,34,63,.09)",
    },
    "forest": {
        "paper": "#f4f2e8",
        "paper_alt": "#e6eadc",
        "ink": "#1e3224",
        "muted": "#566356",
        "accent": "#2f8f54",
        "accent_soft": "rgba(47,143,84,.11)",
        "card": "rgba(255,255,255,.78)",
        "border": "rgba(30,50,36,.10)",
        "shadow": "0 22px 50px rgba(30,50,36,.08)",
    },
    "kraft": {
        "paper": "#f3e4cf",
        "paper_alt": "#e5d0b4",
        "ink": "#2f2114",
        "muted": "#6a5540",
        "accent": "#b46b2d",
        "accent_soft": "rgba(180,107,45,.12)",
        "card": "rgba(255,250,242,.82)",
        "border": "rgba(47,33,20,.10)",
        "shadow": "0 22px 50px rgba(47,33,20,.08)",
    },
    "dune": {
        "paper": "#f0e8d8",
        "paper_alt": "#e2d6c2",
        "ink": "#25201a",
        "muted": "#625a51",
        "accent": "#d07a2d",
        "accent_soft": "rgba(208,122,45,.12)",
        "card": "rgba(255,255,255,.78)",
        "border": "rgba(37,32,26,.10)",
        "shadow": "0 22px 50px rgba(37,32,26,.08)",
    },
}


STYLE_META = {
    "magazine": {
        "label": "电子杂志风",
        "subtitle": "适合叙事型、分享型、内容驱动的 HTML 网页",
        "font_title": "Georgia, 'Times New Roman', serif",
        "font_body": "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    },
    "swiss": {
        "label": "结构清晰风",
        "subtitle": "适合数据驱动、工程感、结构清晰的 HTML 网页",
        "font_title": "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
        "font_body": "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    },
}


@dataclass(frozen=True)
class HtmlDeckPage:
    id: str
    page_no: int
    layout: str
    title: str
    subtitle: str = ""
    summary: str = ""
    bullets: list[str] = None  # type: ignore[assignment]
    notes: str = ""
    source_refs: list[SourceRef] = None  # type: ignore[assignment]
    hero: bool = False

    def __post_init__(self):
        object.__setattr__(self, "bullets", list(self.bullets or []))
        object.__setattr__(self, "source_refs", list(self.source_refs or []))


@dataclass(frozen=True)
class HtmlDeckSpec:
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    style: str
    theme: str
    template_id: str
    pages: list[HtmlDeckPage]
    quality_warnings: list[str]


def _safe_text(value: Any) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _source_label(ref: SourceRef) -> str:
    if ref.title:
        return ref.title
    if ref.page_name:
        return ref.page_name
    if ref.document_id:
        return ref.document_id
    if ref.upload_id:
        return ref.upload_id
    if ref.kb_id:
        return ref.kb_id
    return ref.source_type


def _chunked(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _page_layout(slide: SlideSpec) -> str:
    mapping = {
        "cover": "hero",
        "agenda": "agenda",
        "toc": "agenda",
        "section_divider": "section",
        "workflow": "workflow",
        "checklist": "checklist",
        "quiz": "quiz",
        "summary": "summary",
        "risk_scene": "risk",
        "legal_requirement": "legal",
        "control_measures": "controls",
        "case_discussion": "discussion",
        "content": "content",
    }
    return mapping.get(slide.slide_type, "content")


def build_html_deck(spec: PresentationSpec, content_pack: ContentPack, settings: dict[str, Any]) -> HtmlDeckSpec:
    style = str(settings.get("render_style") or "magazine")
    theme = str(settings.get("theme") or "ink")
    pages: list[HtmlDeckPage] = []
    for slide in spec.slides:
        layout = _page_layout(slide)
        summary = slide.key_message or slide.subtitle or slide.notes or slide.title
        pages.append(
            HtmlDeckPage(
                id=slide.id,
                page_no=slide.slide_no,
                layout=layout,
                title=slide.title,
                subtitle=slide.subtitle or "",
                summary=summary or "",
                bullets=[_normalize_text(item) for item in slide.bullets if _normalize_text(item)],
                notes=slide.notes or "",
                source_refs=list(slide.source_refs),
                hero=slide.slide_type == "cover" or slide.slide_no == 1,
            )
        )

    if not pages:
        pages.append(
            HtmlDeckPage(
                id="page-1",
                page_no=1,
                layout="hero",
                title=spec.title,
                subtitle=spec.topic,
                summary=spec.audience,
                bullets=[],
                notes="",
                source_refs=[],
                hero=True,
            )
        )

    warnings = list(spec.quality_warnings)
    if not any(page.source_refs for page in pages):
        warnings.append("该 HTML 内容主要由模型生成，未绑定企业原文来源")

    return HtmlDeckSpec(
        id=f"html-{spec.id}",
        title=spec.title,
        topic=spec.topic,
        audience=spec.audience,
        duration_minutes=spec.duration_minutes,
        style=style if style in STYLE_META else "magazine",
        theme=theme if theme in HTML_THEMES else "ink",
        template_id=str(settings.get("template_id") or style),
        pages=pages,
        quality_warnings=warnings,
    )


def _theme_tokens(theme: str, style: str) -> dict[str, str]:
    tokens = dict(HTML_THEMES.get(theme, HTML_THEMES["ink"]))
    meta = STYLE_META.get(style, STYLE_META["magazine"])
    tokens["title_font"] = meta["font_title"]
    tokens["body_font"] = meta["font_body"]
    tokens["style_label"] = meta["label"]
    tokens["style_subtitle"] = meta["subtitle"]
    return tokens


def _source_chips(refs: list[SourceRef]) -> str:
    if not refs:
        return ""
    chips = []
    seen: set[str] = set()
    for ref in refs:
        label = _source_label(ref)
        key = label.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        chips.append(f'<span class="chip">{_safe_text(label)}</span>')
        if len(chips) >= 2:
            break
    extra = max(0, len({ _source_label(ref).strip() for ref in refs if _source_label(ref).strip() }) - len(chips))
    if extra:
        chips.append(f'<span class="chip">+{extra}</span>')
    return "".join(chips)


def _source_line(refs: list[SourceRef]) -> str:
    if not refs:
        return ""
    total_unique = { _source_label(ref).strip() for ref in refs if _source_label(ref).strip() }
    count = len(total_unique)
    if count <= 0:
        return ""
    return f"来源 · {count} 份资料"


def _bullet_items(items: list[str]) -> str:
    if not items:
        return '<li class="ghost">内容将根据来源自动整理</li>'
    return "".join(f"<li>{_safe_text(item)}</li>" for item in items[:5])


def _card_blocks(items: list[str]) -> str:
    if not items:
        return '<div class="mini-card"><strong>资料已接入</strong><p>生成内容会优先来自你上传的文档或知识库页面。</p></div>'
    blocks = []
    for idx, item in enumerate(items[:4], start=1):
        blocks.append(
            f'<div class="mini-card"><span class="mini-index">{idx:02d}</span><p>{_safe_text(item)}</p></div>'
        )
    return "".join(blocks)


def _page_html(page: HtmlDeckPage, tokens: dict[str, str], total: int) -> str:
    chip_html = _source_chips(page.source_refs)
    source_line = _source_line(page.source_refs)
    if page.layout == "hero":
        return f"""
        <section class="slide hero" data-layout="hero">
          <div class="chrome"><span>{_safe_text(tokens["style_label"])}</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="hero-grid">
            <div class="hero-copy">
              <div class="kicker">训练材料生成</div>
              <h1>{_safe_text(page.title)}</h1>
              <p class="lead">{_safe_text(page.subtitle or page.summary or page.notes)}</p>
              <div class="meta">
                <span>{_safe_text(page.summary or page.subtitle or "HTML 网页")}</span>
                <span>·</span>
                <span>{_safe_text(tokens["style_subtitle"])}</span>
              </div>
              <div class="chip-row">{chip_html or '<span class="chip">单文件 HTML</span><span class="chip">横向翻页</span>'}</div>
              {f'<div class="source-line">{_safe_text(source_line)}</div>' if source_line else ''}
            </div>
            <div class="hero-panel">
              <div class="panel-title">本页目标</div>
              <div class="panel-body">
                <p>{_safe_text(page.notes or page.summary or "强调主题、受众和本次培训的主要方向。")}</p>
                <div class="panel-grid">{_card_blocks(page.bullets)}</div>
              </div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "HTML")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "agenda":
        agenda_items = page.bullets or [page.summary or "背景", "关键内容", "行动建议"]
        agenda_html = "".join(
            f'<div class="agenda-item"><span>{idx:02d}</span><strong>{_safe_text(item)}</strong></div>'
            for idx, item in enumerate(agenda_items[:6], start=1)
        )
        return f"""
        <section class="slide" data-layout="agenda">
          <div class="chrome"><span>目录</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell agenda-shell">
            <div class="section-head">
              <div class="kicker">Agenda</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "先搭框架，再落到可执行动作。")}</p>
            </div>
            <div class="agenda-grid">{agenda_html}</div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "AGENDA")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "section":
        return f"""
        <section class="slide" data-layout="section">
          <div class="chrome"><span>SECTION</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell section-shell">
            <div class="section-head section-head--hero">
              <div class="kicker">Section</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "先把这部分的主线立住，再展开细节。")}</p>
            </div>
            <div class="section-grid">
              <div class="section-panel">
                <strong>培训对象</strong>
                <p>{_safe_text(page.summary or page.notes or "聚焦可执行动作。")}</p>
              </div>
              <div class="section-panel accent">
                <strong>来源</strong>
                <p>{_safe_text(source_line or "来源仅作辅助提示，不抢占正文。")}</p>
              </div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "SECTION")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "quote":
        return f"""
        <section class="slide" data-layout="quote">
          <div class="chrome"><span>QUOTE</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell quote-shell">
            <div class="quote-copy">
              <div class="kicker">Takeaway</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="quote-text">{_safe_text(page.summary or page.notes or "把关键动作提炼成一段可被记住的话。")}</p>
            </div>
            <div class="quote-side">
              <div class="panel-title">关键提示</div>
              <div class="panel-body">
                <p>{_safe_text(page.notes or "让这一页更像杂志中的拔高段落。")}</p>
                <div class="source-line">{_safe_text(source_line or "来源保留在辅助位置")}</div>
              </div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "QUOTE")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "contrast":
        left = page.bullets[:2] if page.bullets else [page.summary or "应该做什么", "避免什么"]
        while len(left) < 2:
            left.append("避免重复说明文字")
        return f"""
        <section class="slide" data-layout="contrast">
          <div class="chrome"><span>CONTRAST</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell contrast-shell">
            <div class="section-head">
              <div class="kicker">Contrast</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "用对照方式把动作边界讲清楚。")}</p>
            </div>
            <div class="contrast-grid">
              <div class="contrast-card">
                <strong>应该做</strong>
                <ul>{''.join(f'<li>{_safe_text(item)}</li>' for item in left[:2])}</ul>
              </div>
              <div class="contrast-card accent">
                <strong>避免做</strong>
                <p>{_safe_text(page.notes or "避免把来源说明写成正文。")}</p>
                <div class="source-line">{_safe_text(source_line or "来源保留在角落")}</div>
              </div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "CONTRAST")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "workflow":
        steps = page.bullets or ["识别风险", "上报与处置", "复盘与闭环"]
        step_html = "".join(
            f'<div class="step"><span>{idx:02d}</span><strong>{_safe_text(item)}</strong></div>'
            for idx, item in enumerate(steps[:5], start=1)
        )
        return f"""
        <section class="slide" data-layout="workflow">
          <div class="chrome"><span>流程</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell">
            <div class="section-head">
              <div class="kicker">Workflow</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "把动作拆成顺序明确的步骤。")}</p>
            </div>
            <div class="workflow-grid">{step_html}</div>
            {f'<div class="source-line">{_safe_text(source_line)}</div>' if source_line else ''}
          </div>
          <div class="foot"><span>{_safe_text(source_line or "流程页")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "checklist":
        items = page.bullets or ["逐项确认", "执行留痕", "复核闭环"]
        check_html = "".join(f'<li>{_safe_text(item)}</li>' for item in items[:6])
        return f"""
        <section class="slide" data-layout="checklist">
          <div class="chrome"><span>清单</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell">
            <div class="section-head">
              <div class="kicker">Checklist</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "适合做现场核查和复盘。")}</p>
            </div>
            <div class="check-grid">
              <div class="check-card">
                <ol>{check_html}</ol>
              </div>
              <div class="check-card accent">
                <strong>关键提醒</strong>
                <p>{_safe_text(page.notes or page.summary or "把检查动作落到岗位、班组、现场三个层级。")}</p>
                <div class="chip-row">{chip_html or '<span class="chip">可导出</span><span class="chip">可分享</span>'}</div>
                {f'<div class="source-line">{_safe_text(source_line)}</div>' if source_line else ''}
              </div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "清单页")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """
    if page.layout == "summary":
        blocks = _card_blocks(page.bullets)
        return f"""
        <section class="slide" data-layout="summary">
          <div class="chrome"><span>总结</span><span>{page.page_no:02d} / {total:02d}</span></div>
          <div class="content-shell summary-shell">
            <div class="section-head">
              <div class="kicker">Takeaway</div>
              <h2>{_safe_text(page.title)}</h2>
              <p>{_safe_text(page.summary or page.subtitle or "收束到一页里，让用户带走关键动作。")}</p>
            </div>
            <div class="summary-grid">
              <div class="summary-quote">
                <p>{_safe_text(page.notes or page.summary or "把重要动作变成重复得起的流程。")}</p>
              </div>
              <div class="panel-grid">{blocks}</div>
            </div>
          </div>
          <div class="foot"><span>{_safe_text(source_line or "SUMMARY")}</span><span>{page.page_no:02d}</span></div>
        </section>
        """

    bullets = page.bullets or [page.summary or "根据来源自动生成的重点内容。"]
    bullet_html = _bullet_items(bullets)
    return f"""
    <section class="slide" data-layout="{_safe_text(page.layout)}">
      <div class="chrome"><span>{_safe_text(page.layout)}</span><span>{page.page_no:02d} / {total:02d}</span></div>
      <div class="content-shell split-shell">
        <div class="section-head">
          <div class="kicker">{_safe_text(page.layout.upper())}</div>
          <h2>{_safe_text(page.title)}</h2>
          <p>{_safe_text(page.summary or page.subtitle or "把正文内容整理成可读、可扫、可分享的网页。")}</p>
        </div>
        <div class="split-grid">
          <div class="text-col">
            <ul class="bullet-list">{bullet_html}</ul>
            {f'<div class="source-line">{_safe_text(source_line)}</div>' if source_line else ''}
          </div>
          <div class="side-col">
            <div class="panel-title">关键提示</div>
            <div class="panel-body">
              <div class="chip-row">{chip_html or '<span class="chip">单文件 HTML</span><span class="chip">横向翻页</span>'}</div>
              <p>{_safe_text(page.notes or page.summary or "正文优先，来源只做辅助提示。")}</p>
              {f'<div class="source-line">{_safe_text(source_line)}</div>' if source_line else ''}
            </div>
          </div>
        </div>
      </div>
      <div class="foot"><span>{_safe_text(source_line or page.layout.upper())}</span><span>{page.page_no:02d}</span></div>
    </section>
    """


def _style_block(tokens: dict[str, str]) -> str:
    if tokens["style_label"] == "结构清晰风":
        background = "linear-gradient(180deg, rgba(255,255,255,.98), rgba(244,246,248,.98))"
        accent_grid = "repeating-linear-gradient(90deg, rgba(16,34,63,.04) 0, rgba(16,34,63,.04) 1px, transparent 1px, transparent 64px)"
    else:
        background = f"linear-gradient(180deg, {tokens['paper']}, {tokens['paper_alt']})"
        accent_grid = "repeating-linear-gradient(90deg, rgba(17,17,17,.025) 0, rgba(17,17,17,.025) 1px, transparent 1px, transparent 72px)"
    return f"""
    :root {{
      --paper: {tokens["paper"]};
      --paper-alt: {tokens["paper_alt"]};
      --ink: {tokens["ink"]};
      --muted: {tokens["muted"]};
      --accent: {tokens["accent"]};
      --accent-soft: {tokens["accent_soft"]};
      --card: {tokens["card"]};
      --border: {tokens["border"]};
      --shadow: {tokens["shadow"]};
      --title-font: {tokens["title_font"]};
      --body-font: {tokens["body_font"]};
      --page-bg: {background};
      --grid-bg: {accent_grid};
    }}
    """


def render_html_deck(deck: HtmlDeckSpec, job_id: str) -> dict[str, Any]:
    tokens = _theme_tokens(deck.theme, deck.style)
    total = len(deck.pages)
    pages_html = "\n".join(_page_html(page, tokens, total) for page in deck.pages)
    slides_data = json.dumps(
        [{"id": page.id, "title": page.title, "layout": page.layout, "page_no": page.page_no} for page in deck.pages],
        ensure_ascii=False,
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_safe_text(deck.title)} · HTML 网页</title>
  <style>
    {_style_block(tokens)}
    * {{ box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; margin: 0; overflow: hidden; background: var(--page-bg); color: var(--ink); }}
    body {{ font-family: var(--body-font); }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background-image: var(--grid-bg);
      opacity: .7;
      pointer-events: none;
      z-index: 0;
    }}
    #deck {{ position: fixed; inset: 0; display: flex; width: {max(total, 1) * 100}vw; height: 100vh; transform: translateX(0); transition: transform .85s cubic-bezier(.77,0,.175,1); z-index: 1; }}
    .slide {{ position: relative; flex: 0 0 100vw; height: 100vh; padding: 4.2vh 4vw 4.2vh; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; }}
    .slide::after {{ content: ""; position: absolute; inset: 0; background: rgba(255,255,255,.22); pointer-events: none; }}
    .slide.hero::after {{ background: rgba(255,255,255,.08); }}
    .chrome, .foot {{ position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); }}
    .foot {{ opacity: .7; }}
    .content-shell, .hero-grid {{ position: relative; z-index: 2; }}
    .hero-grid {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 3vw; align-items: stretch; margin-top: 6vh; }}
    .hero-copy, .hero-panel, .check-card, .summary-quote, .agenda-item, .step {{ background: var(--card); border: 1px solid var(--border); border-radius: 24px; box-shadow: var(--shadow); }}
    .hero-copy {{ padding: 5vh 4vw; display: flex; flex-direction: column; justify-content: center; min-height: 58vh; }}
    .hero-panel {{ padding: 3vh 3vw; display: flex; flex-direction: column; gap: 1.5vh; }}
    .kicker {{ text-transform: uppercase; letter-spacing: .22em; font-size: 12px; color: var(--accent); font-weight: 700; }}
    h1, h2 {{ margin: 0; line-height: .95; font-family: var(--title-font); letter-spacing: -.03em; }}
    h1 {{ font-size: clamp(52px, 7vw, 104px); max-width: 9ch; }}
    h2 {{ font-size: clamp(34px, 4.8vw, 68px); max-width: 10ch; }}
    .lead {{ margin: 1.8vh 0 0; font-size: clamp(16px, 1.45vw, 24px); line-height: 1.6; color: var(--ink); max-width: 54ch; }}
    .meta, .chip-row {{ display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }}
    .meta {{ margin-top: 2vh; color: var(--muted); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }}
    .chip {{ display: inline-flex; align-items: center; min-height: 32px; padding: .42rem .7rem; border-radius: 999px; background: var(--accent-soft); color: var(--ink); border: 1px solid rgba(0,0,0,.05); font-size: 12px; }}
    .source-line {{ margin-top: .7rem; color: var(--muted); font-size: 11px; line-height: 1.45; letter-spacing: .06em; }}
    .panel-title {{ font-size: 12px; text-transform: uppercase; letter-spacing: .2em; color: var(--muted); }}
    .panel-body {{ display: grid; gap: 1rem; color: var(--ink); line-height: 1.7; }}
    .panel-grid {{ display: grid; gap: .8rem; grid-template-columns: repeat(2, minmax(0,1fr)); }}
    .mini-card {{ padding: 1rem; border-radius: 18px; background: rgba(255,255,255,.56); border: 1px solid rgba(0,0,0,.05); min-height: 98px; }}
    .mini-card strong {{ display: block; margin-bottom: .4rem; font-size: 14px; }}
    .mini-card p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .mini-index {{ display: inline-flex; font-size: 12px; letter-spacing: .2em; color: var(--accent); margin-bottom: .4rem; }}
    .content-shell {{ margin-top: 7vh; display: grid; gap: 2.8vh; }}
    .section-head p, .summary-quote p {{ margin: .9rem 0 0; color: var(--muted); font-size: clamp(15px, 1.1vw, 19px); line-height: 1.65; max-width: 58ch; }}
    .agenda-shell {{ grid-template-columns: 1fr; }}
    .agenda-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 1rem; }}
    .agenda-item {{ padding: 1rem 1.1rem; display: flex; gap: 1rem; align-items: flex-start; }}
    .agenda-item span {{ color: var(--accent); font-weight: 700; font-size: 13px; letter-spacing: .2em; min-width: 2.2ch; }}
    .agenda-item strong {{ font-size: 18px; line-height: 1.4; }}
    .split-grid, .summary-grid, .check-grid {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 1.2rem; align-items: start; }}
    .text-col, .side-col {{ min-width: 0; }}
    .bullet-list {{ margin: 0; padding: 0; list-style: none; display: grid; gap: .9rem; }}
    .bullet-list li {{ padding: 1rem 1.1rem 1rem 1.3rem; border-radius: 18px; background: var(--card); border: 1px solid var(--border); box-shadow: var(--shadow); line-height: 1.55; }}
    .bullet-list li::before {{ content: "•"; color: var(--accent); font-weight: 700; margin-right: .55rem; }}
    .bullet-list li.ghost {{ color: var(--muted); font-style: italic; }}
    .side-col .panel-body, .check-card, .summary-quote {{ padding: 1.2rem 1.2rem; }}
    .section-shell {{ gap: 2rem; }}
    .section-head--hero h2 {{ max-width: 9ch; }}
    .section-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 1rem; }}
    .section-panel {{ padding: 1.1rem 1.2rem; border-radius: 20px; background: var(--card); border: 1px solid var(--border); box-shadow: var(--shadow); min-height: 150px; }}
    .section-panel.accent {{ background: color-mix(in srgb, var(--accent-soft) 72%, white); }}
    .section-panel strong {{ display: block; margin-bottom: .4rem; text-transform: uppercase; letter-spacing: .16em; font-size: 12px; color: var(--muted); }}
    .section-panel p {{ margin: 0; line-height: 1.8; font-size: clamp(16px, 1.2vw, 20px); }}
    .quote-shell {{ grid-template-columns: 1.2fr .8fr; gap: 1.4rem; align-items: end; }}
    .quote-copy {{ min-height: 58vh; display: flex; flex-direction: column; justify-content: center; }}
    .quote-copy h2 {{ max-width: 9ch; }}
    .quote-text {{ margin: 1rem 0 0; font-size: clamp(22px, 2vw, 34px); line-height: 1.55; max-width: 20ch; color: var(--ink); }}
    .quote-side {{ padding: 1.2rem 1.2rem; border-radius: 24px; background: rgba(255,255,255,.58); border: 1px solid var(--border); box-shadow: var(--shadow); }}
    .contrast-shell {{ gap: 1.4rem; }}
    .contrast-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 1rem; }}
    .contrast-card {{ padding: 1.2rem 1.2rem; border-radius: 24px; background: var(--card); border: 1px solid var(--border); box-shadow: var(--shadow); }}
    .contrast-card.accent {{ background: color-mix(in srgb, var(--accent-soft) 74%, white); }}
    .contrast-card strong {{ display: block; margin-bottom: .75rem; text-transform: uppercase; letter-spacing: .16em; font-size: 12px; color: var(--muted); }}
    .contrast-card ul {{ margin: 0; padding-left: 1.1rem; display: grid; gap: .7rem; line-height: 1.7; }}
    .check-grid {{ grid-template-columns: 1fr .95fr; }}
    .check-card ol {{ margin: 0; padding-left: 1.25rem; display: grid; gap: .75rem; line-height: 1.6; }}
    .check-card.accent {{ background: color-mix(in srgb, var(--accent-soft) 72%, white); }}
    .workflow-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; }}
    .step {{ padding: 1rem; min-height: 120px; display: flex; flex-direction: column; justify-content: space-between; }}
    .step span {{ color: var(--accent); font-size: 12px; letter-spacing: .2em; }}
    .step strong {{ display: block; font-size: 18px; line-height: 1.45; }}
    .summary-quote {{ min-height: 220px; display: flex; flex-direction: column; justify-content: center; }}
    .summary-quote p {{ font-size: clamp(18px, 1.5vw, 24px); color: var(--ink); }}
    .hidden {{ display: none !important; }}
    #nav {{ position: fixed; left: 50%; bottom: 2.2vh; transform: translateX(-50%); z-index: 5; display: flex; gap: 10px; }}
    #nav button {{ width: 8px; height: 8px; border: 0; padding: 0; border-radius: 999px; background: rgba(0,0,0,.22); cursor: pointer; }}
    #nav button.active {{ width: 22px; background: var(--accent); }}
    #hint {{ position: fixed; right: 2.5vw; bottom: 2.5vh; z-index: 5; font-size: 10px; letter-spacing: .2em; text-transform: uppercase; color: var(--muted); }}
    #overview {{ position: fixed; inset: 0; z-index: 20; display: none; background: rgba(255,255,255,.96); backdrop-filter: blur(12px); padding: 4vh 4vw; overflow: auto; }}
    #overview.active {{ display: block; }}
    .overview-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
    .overview-card {{ padding: 1rem; border-radius: 20px; background: white; border: 1px solid rgba(0,0,0,.08); box-shadow: 0 10px 24px rgba(0,0,0,.05); cursor: pointer; text-align: left; }}
    .overview-card strong {{ display: block; margin: .5rem 0 .4rem; }}
    .overview-card span {{ color: var(--muted); font-size: 12px; }}
    @media (max-width: 1100px) {{
      .hero-grid, .split-grid, .summary-grid, .check-grid, .section-grid, .quote-shell, .contrast-grid {{ grid-template-columns: 1fr; }}
      .workflow-grid, .agenda-grid {{ grid-template-columns: 1fr; }}
      .panel-grid {{ grid-template-columns: 1fr; }}
      .hero-copy {{ min-height: auto; }}
      h1 {{ max-width: 11ch; }}
    }}
  </style>
</head>
<body>
  <div id="deck">{pages_html}</div>
  <div id="nav"></div>
  <div id="hint">← → 翻页 · ESC 索引 · B 低动态</div>
  <div id="overview" aria-hidden="true">
    <div class="overview-grid" id="overview-grid"></div>
  </div>
  <script>
    const slides = {slides_data};
    const deck = document.getElementById('deck');
    const nav = document.getElementById('nav');
    const overview = document.getElementById('overview');
    const overviewGrid = document.getElementById('overview-grid');
    let idx = 0;
    let lowMotion = false;
    function renderNav() {{
      nav.innerHTML = '';
      slides.forEach((slide, i) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.title = `${{slide.page_no}}. ${{slide.title}}`;
        button.className = i === idx ? 'active' : '';
        button.addEventListener('click', () => go(i));
        nav.appendChild(button);
      }});
    }}
    function renderOverview() {{
      overviewGrid.innerHTML = slides.map((slide, i) => `
        <button class="overview-card" type="button" data-idx="${{i}}">
          <div class="kicker">Page ${{String(slide.page_no).padStart(2, '0')}}</div>
          <strong>${{slide.title}}</strong>
          <span>${{slide.layout}}</span>
        </button>
      `).join('');
      overviewGrid.querySelectorAll('[data-idx]').forEach((el) => {{
        el.addEventListener('click', () => {{
          go(Number(el.getAttribute('data-idx') || 0));
          toggleOverview(false);
        }});
      }});
    }}
    function toggleOverview(force) {{
      const next = typeof force === 'boolean' ? force : !overview.classList.contains('active');
      overview.classList.toggle('active', next);
      overview.setAttribute('aria-hidden', next ? 'false' : 'true');
    }}
    function go(next) {{
      idx = Math.max(0, Math.min(slides.length - 1, next));
        deck.style.transform = `translateX(${{-idx * 100}}vw)`;
      nav.querySelectorAll('button').forEach((button, i) => button.classList.toggle('active', i === idx));
      document.title = `${{slides[idx].title}} · HTML 网页`;
    }}
    function step(delta) {{
      if (overview.classList.contains('active')) return;
      go(idx + delta);
    }}
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {{
        event.preventDefault();
        step(1);
      }} else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {{
        event.preventDefault();
        step(-1);
      }} else if (event.key === 'Home') {{
        event.preventDefault();
        go(0);
      }} else if (event.key === 'End') {{
        event.preventDefault();
        go(slides.length - 1);
      }} else if (event.key === 'Escape') {{
        toggleOverview();
      }} else if (event.key.toLowerCase() === 'b') {{
        lowMotion = !lowMotion;
        document.body.classList.toggle('low-motion', lowMotion);
      }}
    }});
    let wheelAcc = 0;
    let wheelTO = null;
    window.addEventListener('wheel', (event) => {{
      if (overview.classList.contains('active')) return;
      wheelAcc += event.deltaX + event.deltaY;
      if (Math.abs(wheelAcc) > 70) {{
        step(wheelAcc > 0 ? 1 : -1);
        wheelAcc = 0;
      }}
      clearTimeout(wheelTO);
      wheelTO = setTimeout(() => wheelAcc = 0, 140);
    }}, {{ passive: true }});
    let startX = 0;
    let startY = 0;
    window.addEventListener('touchstart', (event) => {{
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
    }}, {{ passive: true }});
    window.addEventListener('touchend', (event) => {{
      const dx = event.changedTouches[0].clientX - startX;
      const dy = event.changedTouches[0].clientY - startY;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {{
        step(dx < 0 ? 1 : -1);
      }}
    }}, {{ passive: true }});
    renderNav();
    renderOverview();
    go(0);
  </script>
</body>
</html>
"""

    html_path = get_job_paths(job_id).html_dir / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return {
        "filename": "index.html",
        "html_path": str(html_path),
        "download_url": f"/api/training/download-html/{job_id}/index.html",
        "preview_url": f"/api/training/preview-html/{job_id}/index.html",
    }


def deck_to_dict(deck: HtmlDeckSpec) -> dict[str, Any]:
    return {
        "id": deck.id,
        "title": deck.title,
        "topic": deck.topic,
        "audience": deck.audience,
        "duration_minutes": deck.duration_minutes,
        "style": deck.style,
        "theme": deck.theme,
        "template_id": deck.template_id,
        "pages": [
            {
                "id": page.id,
                "page_no": page.page_no,
                "layout": page.layout,
                "title": page.title,
                "subtitle": page.subtitle,
                "summary": page.summary,
                "bullets": list(page.bullets),
                "notes": page.notes,
                "source_refs": [ref.model_dump() if hasattr(ref, "model_dump") else ref.__dict__ for ref in page.source_refs],
                "hero": page.hero,
            }
            for page in deck.pages
        ],
        "quality_warnings": list(deck.quality_warnings),
    }


def resolve_html_path(job_id: str, filename: str) -> Path:
    if not filename or filename != Path(filename).name or Path(filename).suffix.lower() != ".html":
        raise ValueError("文件名无效，只允许下载 .html 文件")
    path = get_job_paths(job_id).html_dir / filename
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError("文件不存在")
    return resolved
