"""PPT 生成工作流内部模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SourceInput(BaseModel):
    type: Literal["knowledge_base", "wiki_page", "kb_document", "temporary_upload", "prompt"]
    kb_id: Optional[str] = None
    page_name: Optional[str] = None
    document_id: Optional[str] = None
    upload_id: Optional[str] = None
    prompt: Optional[str] = None
    title: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRef(BaseModel):
    source_type: str
    source_id: Optional[str] = None
    kb_id: Optional[str] = None
    document_id: Optional[str] = None
    page_name: Optional[str] = None
    upload_id: Optional[str] = None
    title: Optional[str] = None
    locator: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: float = 0.0


class ContentChunk(BaseModel):
    id: str
    title: str
    text: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    chunk_type: Literal["wiki", "raw_document", "temporary_upload", "prompt_generated"]


class ContentPack(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    sources: list[SourceInput] = Field(default_factory=list)
    chunks: list[ContentChunk] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    job_id: str = ""


class TrainingOutlineSection(BaseModel):
    id: str
    title: str
    goal: str
    key_points: list[str] = Field(default_factory=list)
    estimated_minutes: int = 0
    source_refs: list[SourceRef] = Field(default_factory=list)


class TrainingOutlinePoint(BaseModel):
    title: str
    description: str = ""


class TrainingOutlineSlide(BaseModel):
    id: str
    slide_no: int
    title: str
    subtitle: Optional[str] = None
    points: list[TrainingOutlinePoint] = Field(default_factory=list)
    body_paragraphs: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    layout_hint: Optional[str] = None
    slide_type: Literal[
        "cover",
        "agenda",
        "content",
        "workflow",
        "risk_scene",
        "legal_requirement",
        "control_measures",
        "case_discussion",
        "checklist",
        "quiz",
        "summary",
    ] = "content"
    source_refs: list[SourceRef] = Field(default_factory=list)
    visual_type: Optional[Literal["none", "cards", "text", "two_column", "risk_matrix", "process_flow", "checklist", "qa", "table"]] = None
    safety_level: Optional[Literal["normal", "attention", "warning", "critical"]] = None


class TrainingOutline(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"]
    slides: list[TrainingOutlineSlide] = Field(default_factory=list)
    sections: list[TrainingOutlineSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SlideSpec(BaseModel):
    id: str
    slide_no: int
    slide_type: Literal[
        "cover",
        "agenda",
        "toc",
        "section_divider",
        "content",
        "risk_scene",
        "legal_requirement",
        "workflow",
        "control_measures",
        "case_discussion",
        "checklist",
        "quiz",
        "summary",
    ]
    title: str
    subtitle: Optional[str] = None
    key_message: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    body_paragraphs: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    visual_type: Optional[Literal["none", "cards", "text", "two_column", "risk_matrix", "process_flow", "checklist", "qa", "table"]] = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    safety_level: Optional[Literal["normal", "attention", "warning", "critical"]] = None


class PresentationSpec(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"]
    template_id: str
    slides: list[SlideSpec] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


class QualityIssue(BaseModel):
    level: Literal["info", "warning", "error"]
    code: str
    message: str
    slide_id: Optional[str] = None
    suggestion: Optional[str] = None


class QualityReport(BaseModel):
    passed: bool
    issues: list[QualityIssue] = Field(default_factory=list)
    summary: str


class PresentationJob(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    source_mode: str
    content_pack_path: Optional[str] = None
    outline_path: Optional[str] = None
    spec_path: Optional[str] = None
    pptx_path: Optional[str] = None
    html_path: Optional[str] = None
    quality_report_path: Optional[str] = None
    download_url: Optional[str] = None


def utc_now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
