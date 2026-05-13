"""HTML deck 渲染 — Style A 电子杂志风（guizang-ppt-skill）。

本模块是 HTML 培训材料生成的唯一渲染层。
约束：
  - 只允许 Style A 电子杂志风（magazine），不支持 Style B（swiss）。
  - 禁止任何模型生成图片的流程；如无现成图片，保持结构可用即可。
  - 主题色只能从 HTML_THEMES 预设中选，不接受自定义 hex。
  - 标题使用衬线字体，正文使用非衬线字体，元数据使用等宽字体。
  - WebGL/Canvas 背景只在 hero 页透出，普通页极度克制。
  - 输出单文件 HTML，横向翻页，支持键盘 / 触屏 / 圆点 / ESC 索引。
"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .models import ContentPack, PresentationSpec, SlideSpec, SourceRef
from .project_store import get_job_paths

# --------------------------------------------------------------------------
# Style A 锁定 — 唯一允许的风格
# --------------------------------------------------------------------------

STYLE_A_ONLY = "magazine"  # 本项目只允许 Style A


# --------------------------------------------------------------------------
# 主题预设（5 个内置，不允许自定义 hex）
# --------------------------------------------------------------------------

HTML_THEMES: dict[str, dict[str, str]] = {
    "ink": {
        "paper": "#fafaf8",
        "paper_alt": "#f3f2ee",
        "ink": "#111110",
        "muted": "#6e6d68",
        "accent": "#1a1a19",
        "accent_soft": "rgba(26,26,25,.07)",
        "border": "rgba(17,17,16,.09)",
        "rule": "rgba(17,17,16,.14)",
    },
    "indigo": {
        "paper": "#f2f4f9",
        "paper_alt": "#e5eaf5",
        "ink": "#0f2040",
        "muted": "#4a5870",
        "accent": "#33508d",
        "accent_soft": "rgba(51,80,141,.09)",
        "border": "rgba(15,32,64,.10)",
        "rule": "rgba(15,32,64,.18)",
    },
    "forest": {
        "paper": "#f4f3ec",
        "paper_alt": "#e8ece0",
        "ink": "#1e3225",
        "muted": "#506352",
        "accent": "#2d7a4a",
        "accent_soft": "rgba(45,122,74,.10)",
        "border": "rgba(30,50,37,.10)",
        "rule": "rgba(30,50,37,.18)",
    },
    "kraft": {
        "paper": "#f5e6cc",
        "paper_alt": "#ead4b0",
        "ink": "#2f2114",
        "muted": "#6a5540",
        "accent": "#9c5822",
        "accent_soft": "rgba(156,88,34,.11)",
        "border": "rgba(47,33,20,.12)",
        "rule": "rgba(47,33,20,.20)",
    },
    "dune": {
        "paper": "#f0e9de",
        "paper_alt": "#e4d9c8",
        "ink": "#25201a",
        "muted": "#635b52",
        "accent": "#c87830",
        "accent_soft": "rgba(200,120,48,.11)",
        "border": "rgba(37,32,26,.11)",
        "rule": "rgba(37,32,26,.20)",
    },
}

# Style A 字体三件套（衬线 / 非衬线 / 等宽）
FONT_TITLE = "Georgia, 'Playfair Display', 'Noto Serif SC', 'Source Han Serif SC', serif"
FONT_BODY  = "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
FONT_MONO  = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

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
    style: str           # 恒为 "magazine"
    theme: str           # HTML_THEMES 中的 key
    template_id: str
    pages: list[HtmlDeckPage]
    quality_warnings: list[str]


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------

def _safe_text(value: Any) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _source_label(ref: SourceRef) -> str:
    for candidate in (ref.title, ref.page_name, ref.document_id, ref.upload_id, ref.kb_id):
        if candidate:
            return str(candidate)
    return ref.source_type


def _chunked(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[idx : idx + size] for idx in range(0, len(items), size)]




# --------------------------------------------------------------------------
# 来源标签渲染
# --------------------------------------------------------------------------

def _source_chips(refs: list[SourceRef]) -> str:
    if not refs:
        return ""
    chips: list[str] = []
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
    all_labels = {_source_label(ref).strip() for ref in refs if _source_label(ref).strip()}
    extra = max(0, len(all_labels) - len(chips))
    if extra:
        chips.append(f'<span class="chip">+{extra}</span>')
    return "".join(chips)


def _source_line(refs: list[SourceRef]) -> str:
    if not refs:
        return ""
    total_unique = {_source_label(ref).strip() for ref in refs if _source_label(ref).strip()}
    count = len(total_unique)
    if count <= 0:
        return ""
    return f"src · {count}" if count == 1 else f"src · {count} docs"


def _bullet_items(items: list[str]) -> str:
    if not items:
        return '<li class="ghost">内容将根据来源自动整理</li>'
    return "".join(f"<li>{_safe_text(item)}</li>" for item in items[:5])


def _card_blocks(items: list[str]) -> str:
    if not items:
        return '<div class="mini-card"><strong>资料已接入</strong><p>生成内容优先来自上传文档或知识库页面。</p></div>'
    blocks: list[str] = []
    for idx, item in enumerate(items[:4], start=1):
        blocks.append(
            f'<div class="mini-card"><span class="mini-idx">{idx:02d}</span><p>{_safe_text(item)}</p></div>'
        )
    return "".join(blocks)


# --------------------------------------------------------------------------
# 页面 HTML 片段生成
# --------------------------------------------------------------------------

def _page_html(page: HtmlDeckPage, tokens: dict[str, str], total: int) -> str:
    chip_html = _source_chips(page.source_refs)
    src_label = _source_line(page.source_refs)

    if page.layout == "hero":
        return f"""
        <section class="slide hero" data-layout="hero">
          <canvas class="hero-canvas" aria-hidden="true"></canvas>
          <div class="chrome"><span class="mono">电子杂志风</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="hero-grid">
            <div class="hero-copy">
              <div class="kicker">Training · {_safe_text(page.subtitle or "安全培训")}</div>
              <h1>{_safe_text(page.title)}</h1>
              <p class="lead">{_safe_text(page.summary or page.notes or "培训材料")}</p>
              <div class="meta-row">
                <span class="mono">{_safe_text(page.notes or page.summary or "HTML 网页")}</span>
                <span class="mono sep">·</span>
                <span class="mono">横向翻页</span>
              </div>
              <div class="chip-row">{chip_html or '<span class="chip mono">单文件 HTML</span><span class="chip mono">可离线</span>'}</div>
              {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
            </div>
            <div class="hero-aside">
              <div class="aside-label mono">本页目标</div>
              <p>{_safe_text(page.notes or page.summary or "强调主题、受众和本次培训主线。")}</p>
              <div class="mini-grid">{_card_blocks(page.bullets)}</div>
            </div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "HTML · 电子杂志风")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "agenda":
        agenda_items = page.bullets or [page.summary or "背景", "关键内容", "行动建议"]
        items_html = "".join(
            f'<div class="agenda-item"><span class="mono accent-text">{idx:02d}</span><strong>{_safe_text(item)}</strong></div>'
            for idx, item in enumerate(agenda_items[:6], start=1)
        )
        return f"""
        <section class="slide" data-layout="agenda">
          <div class="chrome"><span class="mono">目录</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap">
            <div class="page-head">
              <div class="kicker mono">Agenda</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "先搭框架，再落到可执行动作。")}</p>
            </div>
            <div class="agenda-grid">{items_html}</div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "AGENDA")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "section":
        return f"""
        <section class="slide" data-layout="section">
          <div class="chrome"><span class="mono">SECTION</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap section-wrap">
            <div class="section-rule"></div>
            <div class="kicker mono">Section</div>
            <h2 class="section-h2">{_safe_text(page.title)}</h2>
            <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "先把这部分的主线立住，再展开细节。")}</p>
            <div class="section-meta mono">{_safe_text(src_label or "·")}</div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "SECTION")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "quote":
        return f"""
        <section class="slide" data-layout="quote">
          <div class="chrome"><span class="mono">QUOTE</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap quote-wrap">
            <div class="kicker mono">Takeaway</div>
            <h2>{_safe_text(page.title)}</h2>
            <p class="quote-body">{_safe_text(page.summary or page.notes or "把关键动作提炼成一段可被记住的话。")}</p>
            <div class="quote-aside">
              <span class="mono aside-label">关键提示</span>
              <p>{_safe_text(page.notes or "让这一页更像杂志中的拔高段落。")}</p>
              {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
            </div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "QUOTE")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "contrast":
        left = page.bullets[:2] if page.bullets else [page.summary or "应该做什么", "避免什么"]
        while len(left) < 2:
            left.append("具体执行动作")
        return f"""
        <section class="slide" data-layout="contrast">
          <div class="chrome"><span class="mono">CONTRAST</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap">
            <div class="page-head">
              <div class="kicker mono">Contrast</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "用对照方式把动作边界讲清楚。")}</p>
            </div>
            <div class="contrast-grid">
              <div class="contrast-col">
                <span class="mono col-label">应该做</span>
                <ul>{''.join(f'<li>{_safe_text(item)}</li>' for item in left[:2])}</ul>
              </div>
              <div class="contrast-col accent-col">
                <span class="mono col-label">避免做</span>
                <p>{_safe_text(page.notes or "避免把来源说明写成正文。")}</p>
                {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
              </div>
            </div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "CONTRAST")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "workflow":
        steps = page.bullets or ["识别风险", "上报与处置", "复盘与闭环"]
        steps_html = "".join(
            f'<div class="step"><span class="mono step-no">{idx:02d}</span><strong>{_safe_text(item)}</strong></div>'
            for idx, item in enumerate(steps[:5], start=1)
        )
        return f"""
        <section class="slide" data-layout="workflow">
          <div class="chrome"><span class="mono">流程</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap">
            <div class="page-head">
              <div class="kicker mono">Workflow</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "把动作拆成顺序明确的步骤。")}</p>
            </div>
            <div class="workflow-grid">{steps_html}</div>
            {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "流程页")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "checklist":
        items = page.bullets or ["逐项确认", "执行留痕", "复核闭环"]
        check_html = "".join(f'<li>{_safe_text(item)}</li>' for item in items[:6])
        return f"""
        <section class="slide" data-layout="checklist">
          <div class="chrome"><span class="mono">清单</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap">
            <div class="page-head">
              <div class="kicker mono">Checklist</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "适合做现场核查和复盘。")}</p>
            </div>
            <div class="check-grid">
              <ol class="check-list">{check_html}</ol>
              <div class="check-aside">
                <span class="mono aside-label">关键提醒</span>
                <p>{_safe_text(page.notes or page.summary or "把检查动作落到岗位、班组、现场三个层级。")}</p>
                <div class="chip-row">{chip_html or '<span class="chip mono">可导出</span><span class="chip mono">可分享</span>'}</div>
                {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
              </div>
            </div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "清单页")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    if page.layout == "summary":
        blocks = _card_blocks(page.bullets)
        return f"""
        <section class="slide" data-layout="summary">
          <div class="chrome"><span class="mono">总结</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
          <div class="content-wrap">
            <div class="page-head">
              <div class="kicker mono">Takeaway</div>
              <h2>{_safe_text(page.title)}</h2>
              <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "收束到一页里，让用户带走关键动作。")}</p>
            </div>
            <div class="summary-grid">
              <p class="summary-quote">{_safe_text(page.notes or page.summary or "把重要动作变成重复得起的流程。")}</p>
              <div class="mini-grid">{blocks}</div>
            </div>
          </div>
          <div class="foot"><span class="mono">{_safe_text(src_label or "SUMMARY")}</span><span class="mono">{page.page_no:02d}</span></div>
        </section>"""

    # 通用内容页 (content / risk / legal / controls / discussion)
    bullets = page.bullets or [page.summary or "根据来源自动生成的重点内容。"]
    bullet_html = _bullet_items(bullets)
    return f"""
    <section class="slide" data-layout="{_safe_text(page.layout)}">
      <div class="chrome"><span class="mono">{_safe_text(page.layout.upper())}</span><span class="mono">{page.page_no:02d}&thinsp;/&thinsp;{total:02d}</span></div>
      <div class="content-wrap split-wrap">
        <div class="page-head">
          <div class="kicker mono">{_safe_text(page.layout.upper())}</div>
          <h2>{_safe_text(page.title)}</h2>
          <p class="lead-sm">{_safe_text(page.summary or page.subtitle or "把正文内容整理成可读、可扫、可分享的网页。")}</p>
        </div>
        <div class="split-grid">
          <ul class="bullet-list">{bullet_html}</ul>
          <div class="split-aside">
            <span class="mono aside-label">关键提示</span>
            <div class="chip-row">{chip_html or '<span class="chip mono">单文件 HTML</span>'}</div>
            <p>{_safe_text(page.notes or page.summary or "正文优先，来源只做辅助提示。")}</p>
            {f'<div class="src-line mono">{_safe_text(src_label)}</div>' if src_label else ''}
          </div>
        </div>
      </div>
      <div class="foot"><span class="mono">{_safe_text(src_label or page.layout.upper())}</span><span class="mono">{page.page_no:02d}</span></div>
    </section>"""


# --------------------------------------------------------------------------
# CSS 与主题 token
# --------------------------------------------------------------------------

def _css_vars(theme: str) -> str:
    t = HTML_THEMES.get(theme, HTML_THEMES["ink"])
    return f"""
    :root {{
      --paper:       {t["paper"]};
      --paper-alt:   {t["paper_alt"]};
      --ink:         {t["ink"]};
      --muted:       {t["muted"]};
      --accent:      {t["accent"]};
      --accent-soft: {t["accent_soft"]};
      --border:      {t["border"]};
      --rule:        {t["rule"]};
      --f-title: {FONT_TITLE};
      --f-body:  {FONT_BODY};
      --f-mono:  {FONT_MONO};
    }}"""


def _global_css(total: int) -> str:
    return f"""
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 100%; height: 100%; overflow: hidden;
      background: var(--paper);
      color: var(--ink);
      font-family: var(--f-body);
      -webkit-font-smoothing: antialiased;
    }}
    /* 极淡背景纹理 */
    body::before {{
      content: "";
      position: fixed; inset: 0; pointer-events: none; z-index: 0;
      background-image:
        repeating-linear-gradient(90deg, var(--rule) 0, var(--rule) 1px, transparent 1px, transparent 80px),
        repeating-linear-gradient(0deg,  var(--rule) 0, var(--rule) 1px, transparent 1px, transparent 80px);
      opacity: .18;
    }}
    /* 翻页容器 */
    #deck {{
      position: fixed; inset: 0;
      display: flex;
      width: {max(total, 1) * 100}vw; height: 100vh;
      transform: translateX(0);
      transition: transform .82s cubic-bezier(.77,0,.175,1);
      z-index: 1;
    }}
    /* 单页 */
    .slide {{
      position: relative;
      flex: 0 0 100vw; height: 100vh;
      padding: 4vh 4.5vw;
      display: flex; flex-direction: column;
      overflow: hidden;
      background: var(--paper);
    }}
    .slide.hero {{ background: var(--paper-alt); }}
    /* Hero Canvas 背景粒子 */
    .hero-canvas {{
      position: absolute; inset: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 0; opacity: .55;
    }}
    /* 字体三件套 */
    h1, h2 {{ font-family: var(--f-title); letter-spacing: -.025em; line-height: .94; color: var(--ink); }}
    h1 {{ font-size: clamp(54px, 7.5vw, 112px); max-width: 9ch; }}
    h2 {{ font-size: clamp(36px, 4.6vw, 72px); max-width: 11ch; }}
    .mono {{ font-family: var(--f-mono); letter-spacing: .04em; }}
    /* 顶部/底部导航条 */
    .chrome, .foot {{
      position: relative; z-index: 2;
      display: flex; justify-content: space-between; align-items: center;
      font-size: 10px; letter-spacing: .18em; text-transform: uppercase;
      color: var(--muted);
    }}
    .foot {{ margin-top: auto; opacity: .65; }}
    /* 内容区 */
    .hero-grid {{
      position: relative; z-index: 2;
      display: grid; grid-template-columns: 1.15fr .85fr;
      gap: 3vw; align-items: stretch;
      margin-top: 5vh; flex: 1;
    }}
    .hero-copy {{
      display: flex; flex-direction: column; justify-content: center;
      gap: 1.6vh;
      border-right: 1px solid var(--border);
      padding-right: 3vw;
    }}
    .hero-aside {{
      display: flex; flex-direction: column; gap: 1.2rem;
      padding-top: .5rem;
    }}
    .content-wrap {{
      position: relative; z-index: 2;
      display: flex; flex-direction: column; gap: 2.5vh;
      flex: 1; margin-top: 4.5vh;
    }}
    /* kicker 标签 */
    .kicker {{
      font-size: 11px; letter-spacing: .22em; text-transform: uppercase;
      color: var(--accent); font-weight: 700;
    }}
    /* lead 文本 */
    .lead {{
      font-family: var(--f-body);
      font-size: clamp(15px, 1.32vw, 22px);
      line-height: 1.65; color: var(--ink);
      max-width: 52ch;
    }}
    .lead-sm {{
      font-family: var(--f-body);
      font-size: clamp(13px, 1.05vw, 18px);
      line-height: 1.7; color: var(--muted);
      max-width: 58ch;
    }}
    /* meta 行 */
    .meta-row {{
      display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
      margin-top: .6vh; color: var(--muted); font-size: 11px;
    }}
    .sep {{ opacity: .4; }}
    /* chip 标签 */
    .chip-row {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; }}
    .chip {{
      display: inline-flex; align-items: center;
      padding: .3rem .7rem; border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--paper);
      color: var(--muted); font-size: 11px;
    }}
    /* 来源行 */
    .src-line {{
      font-size: 10px; color: var(--muted);
      letter-spacing: .12em; margin-top: .6rem;
    }}
    /* Hero 右侧小卡片 */
    .aside-label {{
      font-size: 10px; letter-spacing: .2em; text-transform: uppercase;
      color: var(--muted); display: block; margin-bottom: .6rem;
    }}
    .hero-aside > p {{
      font-size: clamp(13px, 1vw, 16px); line-height: 1.7; color: var(--muted);
    }}
    .mini-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin-top: .5rem;
    }}
    .mini-card {{
      padding: .9rem 1rem;
      border: 1px solid var(--border); border-radius: 12px;
      min-height: 80px;
    }}
    .mini-card strong {{ display: block; font-size: 13px; margin-bottom: .3rem; }}
    .mini-card p {{ margin: 0; color: var(--muted); line-height: 1.5; font-size: 12px; }}
    .mini-idx {{
      display: inline-block; font-family: var(--f-mono);
      font-size: 11px; letter-spacing: .2em;
      color: var(--accent); margin-bottom: .35rem;
    }}
    /* 页面通用区 */
    .page-head {{ display: flex; flex-direction: column; gap: .8rem; }}
    /* Agenda */
    .agenda-grid {{
      display: grid; grid-template-columns: repeat(2, minmax(0,1fr));
      gap: .85rem;
    }}
    .agenda-item {{
      display: flex; gap: 1rem; align-items: flex-start;
      padding: 1rem 1.1rem;
      border-top: 2px solid var(--border);
    }}
    .agenda-item .accent-text {{ color: var(--accent); font-weight: 700; min-width: 2ch; }}
    .agenda-item strong {{ font-size: 17px; line-height: 1.4; }}
    /* Section 过渡页 */
    .section-wrap {{ justify-content: center; }}
    .section-rule {{
      width: 56px; height: 3px;
      background: var(--accent); border-radius: 2px;
      margin-bottom: 2.5rem;
    }}
    .section-h2 {{ max-width: 8ch; margin-top: .8rem; }}
    .section-meta {{ font-size: 11px; color: var(--muted); margin-top: 2rem; }}
    /* Quote */
    .quote-wrap {{ justify-content: center; gap: 2rem; }}
    .quote-body {{
      font-family: var(--f-title);
      font-size: clamp(24px, 2.2vw, 38px);
      line-height: 1.52; color: var(--ink);
      max-width: 22ch; margin-top: .5rem;
    }}
    .quote-aside {{
      border-left: 2px solid var(--accent);
      padding-left: 1.4rem; max-width: 36ch;
    }}
    .quote-aside p {{ line-height: 1.7; color: var(--muted); font-size: clamp(13px,1vw,17px); }}
    /* Contrast */
    .contrast-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
    }}
    .contrast-col {{
      padding: 1.2rem 1.4rem;
      border-top: 2px solid var(--border);
    }}
    .accent-col {{ border-color: var(--accent); }}
    .col-label {{
      display: block; font-size: 10px; letter-spacing: .2em;
      text-transform: uppercase; color: var(--muted); margin-bottom: .8rem;
    }}
    .contrast-col ul {{ padding-left: 1rem; display: grid; gap: .6rem; line-height: 1.7; }}
    .contrast-col p {{ line-height: 1.7; color: var(--muted); font-size: clamp(13px,1vw,17px); }}
    /* Workflow */
    .workflow-grid {{
      display: grid; grid-template-columns: repeat(3, minmax(0,1fr));
      gap: .85rem;
    }}
    .step {{
      padding: 1.1rem 1.3rem;
      border-top: 2px solid var(--border);
      min-height: 110px;
      display: flex; flex-direction: column; justify-content: space-between;
    }}
    .step-no {{ color: var(--accent); font-size: 12px; letter-spacing: .2em; }}
    .step strong {{ display: block; font-size: 17px; line-height: 1.45; margin-top: .5rem; }}
    /* Checklist */
    .check-grid {{
      display: grid; grid-template-columns: 1.1fr .9fr; gap: 1.4rem;
    }}
    .check-list {{
      padding-left: 1.2rem; display: grid; gap: .8rem; line-height: 1.65;
      counter-reset: check;
    }}
    .check-list li {{ font-size: clamp(14px, 1.05vw, 18px); }}
    .check-aside {{
      padding: 1.2rem 1.4rem;
      border-left: 2px solid var(--border);
      display: flex; flex-direction: column; gap: .8rem;
    }}
    .check-aside p {{ line-height: 1.7; color: var(--muted); font-size: clamp(13px,1vw,17px); }}
    /* Summary */
    .summary-grid {{
      display: grid; grid-template-columns: 1.1fr .9fr; gap: 1.4rem;
      align-items: start;
    }}
    .summary-quote {{
      font-family: var(--f-title);
      font-size: clamp(20px, 1.8vw, 30px);
      line-height: 1.55; color: var(--ink);
      border-left: 2px solid var(--accent);
      padding-left: 1.4rem;
    }}
    /* Split（通用内容页）*/
    .split-grid {{
      display: grid; grid-template-columns: 1.1fr .9fr; gap: 1.4rem;
    }}
    .bullet-list {{ list-style: none; display: grid; gap: .7rem; }}
    .bullet-list li {{
      padding: .9rem 1rem .9rem 1.2rem;
      border-left: 2px solid var(--border);
      font-size: clamp(14px, 1.05vw, 18px); line-height: 1.6;
    }}
    .bullet-list li::marker {{ display: none; }}
    .bullet-list li.ghost {{ color: var(--muted); font-style: italic; }}
    .split-aside {{
      padding: 1rem 1.2rem;
      border-left: 2px solid var(--border);
      display: flex; flex-direction: column; gap: .7rem;
    }}
    .split-aside p {{ line-height: 1.7; color: var(--muted); font-size: clamp(13px,1vw,17px); }}
    /* 底部圆点导航 */
    #nav {{
      position: fixed; left: 50%; bottom: 2.2vh;
      transform: translateX(-50%); z-index: 5;
      display: flex; gap: 8px; align-items: center;
    }}
    #nav button {{
      width: 7px; height: 7px; border: 0; padding: 0; border-radius: 999px;
      background: var(--border); cursor: pointer; transition: all .25s;
    }}
    #nav button.active {{
      width: 20px; background: var(--accent);
    }}
    #hint {{
      position: fixed; right: 2.5vw; bottom: 2.5vh; z-index: 5;
      font-family: var(--f-mono); font-size: 10px;
      letter-spacing: .18em; text-transform: uppercase;
      color: var(--muted);
    }}
    /* 索引面板 */
    #overview {{
      position: fixed; inset: 0; z-index: 20;
      display: none; background: rgba(250,250,248,.97);
      backdrop-filter: blur(14px);
      padding: 4vh 4vw; overflow: auto;
    }}
    #overview.active {{ display: block; }}
    #overview h2 {{
      font-family: var(--f-mono); font-size: 12px;
      letter-spacing: .22em; text-transform: uppercase;
      color: var(--muted); margin-bottom: 1.5rem;
    }}
    .ov-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr));
      gap: .85rem;
    }}
    .ov-card {{
      padding: .9rem 1.1rem;
      border: 1px solid var(--border); border-radius: 12px;
      background: var(--paper); cursor: pointer; text-align: left;
      transition: border-color .15s;
    }}
    .ov-card:hover {{ border-color: var(--accent); }}
    .ov-card .ov-no {{
      font-family: var(--f-mono); font-size: 10px;
      letter-spacing: .2em; color: var(--muted);
    }}
    .ov-card strong {{ display: block; font-size: 14px; margin: .4rem 0 .3rem; line-height: 1.35; }}
    .ov-card span {{ font-family: var(--f-mono); font-size: 10px; color: var(--muted); }}
    /* 响应式降级 */
    @media (max-width: 960px) {{
      .hero-grid, .split-grid, .summary-grid, .check-grid, .contrast-grid {{ grid-template-columns: 1fr; }}
      .workflow-grid, .agenda-grid {{ grid-template-columns: 1fr; }}
      .mini-grid {{ grid-template-columns: 1fr; }}
      h1 {{ max-width: 11ch; }}
    }}
    """


# --------------------------------------------------------------------------
# 最终渲染
# --------------------------------------------------------------------------

def render_html_deck(deck: HtmlDeckSpec, job_id: str) -> dict[str, Any]:
    """把 HtmlDeckSpec 渲染成单文件 HTML 并写入磁盘。"""
    total = len(deck.pages)
    pages_html = "\n".join(_page_html(page, {}, total) for page in deck.pages)
    slides_data = json.dumps(
        [{"id": p.id, "title": p.title, "layout": p.layout, "page_no": p.page_no} for p in deck.pages],
        ensure_ascii=False,
    )
    css_vars = _css_vars(deck.theme)
    global_css = _global_css(total)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_safe_text(deck.title)} · 电子杂志风</title>
  <style>
    {css_vars}
    {global_css}
  </style>
</head>
<body>
  <div id="deck">{pages_html}</div>
  <div id="nav" aria-label="页面导航"></div>
  <div id="hint" aria-hidden="true">← → 翻页 · ESC 索引 · B 低动效</div>
  <div id="overview" role="dialog" aria-modal="true" aria-hidden="true">
    <h2>索引</h2>
    <div class="ov-grid" id="ov-grid"></div>
  </div>
  <script>
    /* ── Hero Canvas 粒子背景 ────────────────────────────────── */
    (function initHeroCanvas() {{
      const canvases = document.querySelectorAll('.hero-canvas');
      canvases.forEach(function(canvas) {{
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        const W = canvas.offsetWidth || canvas.parentElement.offsetWidth || window.innerWidth;
        const H = canvas.offsetHeight || canvas.parentElement.offsetHeight || window.innerHeight;
        canvas.width = W; canvas.height = H;
        const pts = Array.from({{ length: 52 }}, function() {{
          return {{ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .38, vy: (Math.random() - .5) * .38 }};
        }});
        const ink = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#111';
        function frame() {{
          ctx.clearRect(0, 0, W, H);
          pts.forEach(function(p) {{
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0 || p.x > W) p.vx *= -1;
            if (p.y < 0 || p.y > H) p.vy *= -1;
            ctx.beginPath(); ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
            ctx.fillStyle = ink; ctx.globalAlpha = .18; ctx.fill();
          }});
          pts.forEach(function(a, i) {{
            pts.slice(i + 1).forEach(function(b) {{
              const d = Math.hypot(a.x - b.x, a.y - b.y);
              if (d < 110) {{
                ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = ink; ctx.globalAlpha = (1 - d / 110) * .06;
                ctx.lineWidth = .8; ctx.stroke();
              }}
            }});
          }});
          requestAnimationFrame(frame);
        }}
        frame();
      }});
    }})();

    /* ── 翻页逻辑 ────────────────────────────────────────────── */
    var slides = {slides_data};
    var deck   = document.getElementById('deck');
    var nav    = document.getElementById('nav');
    var ov     = document.getElementById('overview');
    var ovGrid = document.getElementById('ov-grid');
    var idx    = 0;

    function buildNav() {{
      nav.innerHTML = '';
      slides.forEach(function(s, i) {{
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.title = s.page_no + '. ' + s.title;
        if (i === idx) btn.classList.add('active');
        btn.addEventListener('click', function() {{ go(i); }});
        nav.appendChild(btn);
      }});
    }}

    function buildOverview() {{
      ovGrid.innerHTML = slides.map(function(s, i) {{
        return '<button class="ov-card" type="button" data-i="' + i + '">' +
          '<span class="ov-no mono">PAGE ' + String(s.page_no).padStart(2,'0') + '</span>' +
          '<strong>' + s.title + '</strong>' +
          '<span>' + s.layout + '</span>' +
          '</button>';
      }}).join('');
      ovGrid.querySelectorAll('[data-i]').forEach(function(el) {{
        el.addEventListener('click', function() {{
          go(Number(el.getAttribute('data-i') || 0));
          toggleOv(false);
        }});
      }});
    }}

    function toggleOv(force) {{
      var next = typeof force === 'boolean' ? force : !ov.classList.contains('active');
      ov.classList.toggle('active', next);
      ov.setAttribute('aria-hidden', next ? 'false' : 'true');
    }}

    function go(n) {{
      idx = Math.max(0, Math.min(slides.length - 1, n));
      deck.style.transform = 'translateX(' + (-idx * 100) + 'vw)';
      nav.querySelectorAll('button').forEach(function(btn, i) {{
        btn.classList.toggle('active', i === idx);
      }});
      document.title = slides[idx].title + ' · 电子杂志风';
    }}

    function step(d) {{
      if (ov.classList.contains('active')) return;
      go(idx + d);
    }}

    document.addEventListener('keydown', function(e) {{
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {{ e.preventDefault(); step(1); }}
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{ e.preventDefault(); step(-1); }}
      else if (e.key === 'Home') {{ e.preventDefault(); go(0); }}
      else if (e.key === 'End')  {{ e.preventDefault(); go(slides.length - 1); }}
      else if (e.key === 'Escape') {{ toggleOv(); }}
      else if (e.key.toLowerCase() === 'b') {{
        document.body.classList.toggle('low-motion');
      }}
    }});

    var wAcc = 0, wTO = null;
    window.addEventListener('wheel', function(e) {{
      if (ov.classList.contains('active')) return;
      wAcc += e.deltaX + e.deltaY;
      if (Math.abs(wAcc) > 60) {{ step(wAcc > 0 ? 1 : -1); wAcc = 0; }}
      clearTimeout(wTO); wTO = setTimeout(function() {{ wAcc = 0; }}, 150);
    }}, {{ passive: true }});

    var tX = 0, tY = 0;
    window.addEventListener('touchstart', function(e) {{ tX = e.touches[0].clientX; tY = e.touches[0].clientY; }}, {{ passive: true }});
    window.addEventListener('touchend', function(e) {{
      var dx = e.changedTouches[0].clientX - tX;
      var dy = e.changedTouches[0].clientY - tY;
      if (Math.abs(dx) > 42 && Math.abs(dx) > Math.abs(dy)) step(dx < 0 ? 1 : -1);
    }}, {{ passive: true }});

    buildNav();
    buildOverview();
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


# --------------------------------------------------------------------------
# 序列化工具
# --------------------------------------------------------------------------

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
                "id": p.id,
                "page_no": p.page_no,
                "layout": p.layout,
                "title": p.title,
                "subtitle": p.subtitle,
                "summary": p.summary,
                "bullets": list(p.bullets),
                "notes": p.notes,
                "source_refs": [
                    ref.model_dump() if hasattr(ref, "model_dump") else ref.__dict__
                    for ref in p.source_refs
                ],
                "hero": p.hero,
            }
            for p in deck.pages
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
