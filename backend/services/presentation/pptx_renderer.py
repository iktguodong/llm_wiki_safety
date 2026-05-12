"""使用 python-pptx 渲染 PPTX。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from docx import Document

from .models import PresentationSpec, SlideSpec
from .project_store import get_job_paths, save_speaker_notes, save_speaker_notes_docx
from .safety_templates import SafetyTemplate


def _rgb(hex_color: str) -> RGBColor:
    hex_color = hex_color.lstrip("#")
    return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _set_run_font(run, *, cn: str, en: str, size: int, color: str, bold: bool = False):
    run.font.name = cn
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _add_textbox(slide, left, top, width, height, text, *, font_cn, font_en, size, color, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    if p.runs:
        for run in p.runs:
            _set_run_font(run, cn=font_cn, en=font_en, size=size, color=color, bold=bold)
    else:
        run = p.add_run()
        run.text = text
        _set_run_font(run, cn=font_cn, en=font_en, size=size, color=color, bold=bold)
    return box


def _apply_footer(slide, template: SafetyTemplate, slide_no: int, footer_text: str):
    _add_textbox(
        slide,
        Inches(0.45),
        Inches(7.0),
        Inches(6.0),
        Inches(0.3),
        footer_text,
        font_cn=template.font_family_cn,
        font_en=template.font_family_en,
        size=10,
        color=template.theme_colors["body"],
    )
    _add_textbox(
        slide,
        Inches(12.0),
        Inches(7.0),
        Inches(0.7),
        Inches(0.3),
        str(slide_no),
        font_cn=template.font_family_cn,
        font_en=template.font_family_en,
        size=10,
        color=template.theme_colors["body"],
        align=PP_ALIGN.RIGHT,
    )


def _base_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _set_bg(slide, color: str):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def _render_cover(slide, spec: PresentationSpec, template: SafetyTemplate, slide_spec: SlideSpec):
    _set_bg(slide, template.theme_colors["bg"])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(0.0), Inches(13.33), Inches(0.35))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(template.theme_colors["primary"])
    bar.line.fill.background()
    _add_textbox(slide, Inches(0.7), Inches(1.1), Inches(11.5), Inches(1.0), spec.title, font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.title_size + 6, color=template.theme_colors["title"], bold=True)
    _add_textbox(slide, Inches(0.75), Inches(2.2), Inches(10.6), Inches(0.6), slide_spec.subtitle or "", font_cn=template.font_family_cn, font_en=template.font_family_en, size=18, color=template.theme_colors["body"])
    bullets = slide_spec.bullets[:4]
    top = Inches(3.2)
    for idx, bullet in enumerate(bullets):
        _add_textbox(slide, Inches(0.95), top + Inches(idx * 0.45), Inches(7.5), Inches(0.35), f"• {bullet}", font_cn=template.font_family_cn, font_en=template.font_family_en, size=16, color=template.theme_colors["body"])
    _add_textbox(slide, Inches(0.75), Inches(6.2), Inches(10), Inches(0.35), template.footer_style, font_cn=template.font_family_cn, font_en=template.font_family_en, size=11, color=template.theme_colors["accent"])


def _render_toc(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _set_bg(slide, template.theme_colors["bg"])
    _add_textbox(slide, Inches(0.7), Inches(0.5), Inches(6), Inches(0.5), slide_spec.title, font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.title_size, color=template.theme_colors["title"], bold=True)
    for idx, bullet in enumerate(slide_spec.bullets[:6], start=1):
        _add_textbox(slide, Inches(1.0), Inches(1.5 + (idx - 1) * 0.65), Inches(10.8), Inches(0.45), f"{idx}. {bullet}", font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.body_size, color=template.theme_colors["body"])


def _render_divider(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _set_bg(slide, template.theme_colors["bg"])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(0.0), Inches(0.45), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(template.theme_colors["accent"])
    bar.line.fill.background()
    _add_textbox(slide, Inches(1.1), Inches(2.0), Inches(10.5), Inches(0.8), slide_spec.title, font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.title_size + 6, color=template.theme_colors["title"], bold=True)
    _add_textbox(slide, Inches(1.1), Inches(3.0), Inches(10.0), Inches(0.6), slide_spec.subtitle or "", font_cn=template.font_family_cn, font_en=template.font_family_en, size=18, color=template.theme_colors["body"])


def _render_bullet_slide(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _set_bg(slide, template.theme_colors["bg"])
    _add_textbox(slide, Inches(0.7), Inches(0.45), Inches(11.6), Inches(0.6), slide_spec.title, font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.title_size, color=template.theme_colors["title"], bold=True)
    if slide_spec.subtitle:
        _add_textbox(slide, Inches(0.75), Inches(1.1), Inches(11), Inches(0.35), slide_spec.subtitle, font_cn=template.font_family_cn, font_en=template.font_family_en, size=13, color=template.theme_colors["accent"])
    left = Inches(0.95)
    top = Inches(1.65)
    box_w = Inches(12.0)
    box_h = Inches(4.9)
    for idx, bullet in enumerate(slide_spec.bullets[:5]):
        _add_textbox(slide, left, top + Inches(idx * 0.75), box_w, Inches(0.45), f"• {bullet}", font_cn=template.font_family_cn, font_en=template.font_family_en, size=template.body_size, color=template.theme_colors["body"])


def _render_process_slide(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _render_bullet_slide(slide, template, slide_spec)


def _render_checklist_slide(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _render_bullet_slide(slide, template, slide_spec)


def _render_quiz_slide(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _render_bullet_slide(slide, template, slide_spec)
    if slide_spec.notes:
        _add_textbox(slide, Inches(0.75), Inches(5.7), Inches(12), Inches(0.8), f"答案提示：{slide_spec.notes}", font_cn=template.font_family_cn, font_en=template.font_family_en, size=12, color=template.theme_colors["accent"])


def _render_summary_slide(slide, template: SafetyTemplate, slide_spec: SlideSpec):
    _render_bullet_slide(slide, template, slide_spec)
    if slide_spec.key_message:
        _add_textbox(slide, Inches(0.95), Inches(6.1), Inches(11.5), Inches(0.45), slide_spec.key_message, font_cn=template.font_family_cn, font_en=template.font_family_en, size=14, color=template.theme_colors["success"], bold=True)


def _save_notes_docx(title: str, entries: list[tuple[int, str, str]], job_id: str) -> Path:
    document = Document()
    document.add_heading(title, level=0)
    for slide_no, slide_title, notes in entries:
        # keep the notes file readable in Word for users reviewing speaker notes
        document.add_heading(f"第 {slide_no} 页：{slide_title}", level=1)
        for paragraph in notes.splitlines() or [notes]:
            text = paragraph.strip()
            if text:
                document.add_paragraph(text)
    return save_speaker_notes_docx(job_id, document)


def render_presentation(
    spec: PresentationSpec,
    template: SafetyTemplate,
    job_id: str,
    kb_name: str | None = None,
    *,
    include_speaker_notes: bool = True,
) -> dict[str, Any]:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    speaker_notes_lines = [f"# {spec.title}", ""]
    speaker_notes_entries: list[tuple[int, str, str]] = []
    for slide_spec in spec.slides:
        slide = _base_slide(prs)
        _set_bg(slide, template.theme_colors["bg"])
        speaker_notes_lines.append(f"## Slide {slide_spec.slide_no}: {slide_spec.title}")
        note_text = slide_spec.notes or slide_spec.subtitle or slide_spec.key_message or slide_spec.title
        if note_text:
            speaker_notes_lines.append(note_text)
            speaker_notes_entries.append((slide_spec.slide_no, slide_spec.title, note_text))
        speaker_notes_lines.append("")

        if slide_spec.slide_type == "cover":
            _render_cover(slide, spec, template, slide_spec)
        elif slide_spec.slide_type in {"toc", "agenda"}:
            _render_toc(slide, template, slide_spec)
        elif slide_spec.slide_type == "section_divider":
            _render_divider(slide, template, slide_spec)
        elif slide_spec.slide_type in {"workflow"}:
            _render_process_slide(slide, template, slide_spec)
        elif slide_spec.slide_type in {"checklist"}:
            _render_checklist_slide(slide, template, slide_spec)
        elif slide_spec.slide_type in {"quiz"}:
            _render_quiz_slide(slide, template, slide_spec)
        elif slide_spec.slide_type in {"summary"}:
            _render_summary_slide(slide, template, slide_spec)
        elif slide_spec.slide_type in {"risk_scene", "legal_requirement", "control_measures", "case_discussion", "content"}:
            _render_bullet_slide(slide, template, slide_spec)
        else:
            _render_bullet_slide(slide, template, slide_spec)

        footer_text = f"{template.footer_style}" if not kb_name else f"{kb_name} · {template.footer_style}"
        _apply_footer(slide, template, slide_spec.slide_no, footer_text)

    paths = get_job_paths(job_id)
    paths.pptx_dir.mkdir(parents=True, exist_ok=True)
    filename = "training_deck.pptx"
    pptx_path = paths.pptx_dir / filename
    prs.save(str(pptx_path))
    save_speaker_notes(job_id, "\n".join(speaker_notes_lines).strip() + "\n")
    notes_filename = None
    notes_download_url = None
    if include_speaker_notes and speaker_notes_entries:
        notes_path = _save_notes_docx(spec.title, speaker_notes_entries, job_id)
        notes_filename = notes_path.name
        notes_download_url = f"/api/training/download-notes/{notes_filename}"
    return {
        "filename": filename,
        "pptx_path": str(pptx_path),
        "download_url": f"/api/training/download/{filename}",
        "speaker_notes_path": str(paths.speaker_notes_path),
        "notes_filename": notes_filename,
        "notes_download_url": notes_download_url,
    }
