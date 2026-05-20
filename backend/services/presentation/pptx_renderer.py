"""使用 python-pptx 渲染 PPTX。"""

from __future__ import annotations

import asyncio
from threading import Event
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from backend.models import PresentationSpec, SlideSpec
from backend.services.presentation.project_store import get_job_paths, update_job_progress
from backend.services.presentation.safety_templates import SafetyTemplate


def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _run_font(run, *, cn: str, en: str, size: int, color: str, bold: bool = False):
    run.font.name = cn
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _textbox(slide, left, top, width, height, text, *, cn, en, size, color, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    run = p.add_run()
    run.text = text
    _run_font(run, cn=cn, en=en, size=size, color=color, bold=bold)
    return box


def _bg(slide, color: str):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def _render_cover(slide, spec: PresentationSpec, tmpl: SafetyTemplate, ss: SlideSpec):
    _bg(slide, tmpl.theme_colors["bg"])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.33), Inches(0.35))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(tmpl.theme_colors["primary"])
    bar.line.fill.background()
    _textbox(slide, Inches(0.7), Inches(1.1), Inches(11.5), Inches(1.0), spec.title,
             cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=tmpl.title_size + 6, color=tmpl.theme_colors["title"], bold=True)
    y = Inches(2.2)
    for b in ss.bullets[:4]:
        _textbox(slide, Inches(0.95), y, Inches(7.5), Inches(0.35), f"• {b}",
                 cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=16, color=tmpl.theme_colors["body"])
        y += Inches(0.45)
    _textbox(slide, Inches(0.75), Inches(6.2), Inches(10), Inches(0.35), tmpl.footer_style,
             cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=11, color=tmpl.theme_colors["accent"])


def _render_bullet(slide, tmpl: SafetyTemplate, ss: SlideSpec):
    _bg(slide, tmpl.theme_colors["bg"])
    _textbox(slide, Inches(0.7), Inches(0.45), Inches(11.6), Inches(0.6), ss.title,
             cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=tmpl.title_size, color=tmpl.theme_colors["title"], bold=True)
    y = Inches(1.65)
    for b in ss.bullets[:5]:
        _textbox(slide, Inches(0.95), y, Inches(12), Inches(0.45), f"• {b}",
                 cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=tmpl.body_size, color=tmpl.theme_colors["body"])
        y += Inches(0.75)
    if ss.slide_type == "quiz" and ss.notes:
        _textbox(slide, Inches(0.95), Inches(5.7), Inches(12), Inches(0.8), f"答案提示：{ss.notes}",
                 cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=12, color=tmpl.theme_colors["accent"])


def _footer(slide, tmpl: SafetyTemplate, slide_no: int):
    _textbox(slide, Inches(0.45), Inches(7.0), Inches(6), Inches(0.3), tmpl.footer_style,
             cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=10, color=tmpl.theme_colors["body"])
    _textbox(slide, Inches(12), Inches(7.0), Inches(0.7), Inches(0.3), str(slide_no),
             cn=tmpl.font_family_cn, en=tmpl.font_family_en, size=10, color=tmpl.theme_colors["body"], align=PP_ALIGN.RIGHT)


def render_presentation(
    spec: PresentationSpec,
    template: SafetyTemplate,
    job_id: str,
    kb_name: str | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    total = len(spec.slides)
    for idx, ss in enumerate(spec.slides, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()

        update_job_progress(job_id, f"正在生成第 {idx}/{total} 页 PPT...")

        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _bg(slide, template.theme_colors["bg"])

        if ss.slide_type == "cover":
            _render_cover(slide, spec, template, ss)
        elif ss.slide_type in ("quiz",):
            _render_bullet(slide, template, ss)
        else:
            _render_bullet(slide, template, ss)

        _footer(slide, template, ss.slide_no)

    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()

    paths = get_job_paths(job_id)
    paths.pptx_dir.mkdir(parents=True, exist_ok=True)
    filename = "training_deck.pptx"
    pptx_path = paths.pptx_dir / filename
    prs.save(str(pptx_path))
    return {
        "filename": filename,
        "pptx_path": str(pptx_path),
        "download_url": f"/api/training/download/{filename}",
    }
