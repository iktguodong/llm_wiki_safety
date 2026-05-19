"""PPT training material orchestration service."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.models import (
    PresentationSpec,
    QualityReport,
    TrainingConfig,
    TrainingGenerateResponse,
    TrainingOutlineResponse,
    TrainingOutlineV2,
)
from backend.services.llm import llm_service
from backend.services.presentation.content_pack import build_content_pack, normalize_sources
from backend.services.presentation.outline_builder import generate_outline as build_outline
from backend.services.presentation.pptx_renderer import render_presentation
from backend.services.presentation.project_store import save_content_pack, save_outline, save_quality_report, save_spec
from backend.services.presentation.quality_check import check_presentation
from backend.services.presentation.safety_templates import get_template
from backend.services.presentation.slide_planner import plan_slides


logger = logging.getLogger(__name__)


def training_payload_to_request(payload: dict[str, Any]) -> dict[str, Any]:
    config_data = payload.get("config") or {}
    config = TrainingConfig(**config_data) if config_data else None
    sources = payload.get("sources") or normalize_sources(payload)
    topic = payload.get("topic") or (config.topic if config else "") or payload.get("prompt") or ""
    audience = payload.get("audience") if "audience" in payload else (config.audience if config else "一线员工")
    duration_minutes = payload.get("duration_minutes") or (config.duration if config else 60)
    slide_count = payload.get("slide_count") or (config.slide_count if config else 12)
    style = payload.get("style") or "standard_training"
    focus_areas = payload.get("focus_areas") or (config.focus_areas if config else [])
    include_quiz = payload.get("include_quiz", True)
    include_speaker_notes = payload.get("include_speaker_notes", True)
    template_id = payload.get("template_id") or payload.get("template") or (config.template if config else style)
    return {
        "sources": sources,
        "topic": topic,
        "audience": audience,
        "duration_minutes": duration_minutes,
        "slide_count": slide_count,
        "style": style,
        "focus_areas": focus_areas,
        "include_quiz": include_quiz,
        "include_speaker_notes": include_speaker_notes,
        "template_id": template_id,
        "job_id": payload.get("job_id") or payload.get("jobId"),
    }


class TrainingPptService:
    async def generate_outline(self, payload: dict[str, Any], *, job_id: str) -> TrainingOutlineResponse:
        started_at = time.perf_counter()
        request = training_payload_to_request(payload)
        model_id = payload.get("model_id") or payload.get("modelId")
        logger.info(
            "training outline generation started",
            extra={"event": "training_outline_generation", "job_id": job_id, "model_id": model_id, "status": "started"},
        )
        try:
            content_pack = await asyncio.to_thread(build_content_pack, request, job_id)
            outline = await build_outline(content_pack, request, llm_service)
        except Exception as exc:
            logger.exception(
                "training outline generation failed",
                extra={
                    "event": "training_outline_generation",
                    "job_id": job_id,
                    "model_id": model_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "failed",
                    "error": type(exc).__name__,
                },
            )
            raise

        save_content_pack(job_id, content_pack.model_dump())
        save_outline(job_id, outline.model_dump())
        logger.info(
            "training outline generation completed",
            extra={
                "event": "training_outline_generation",
                "job_id": job_id,
                "model_id": model_id,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "status": "completed",
            },
        )

        return TrainingOutlineResponse(
            job_id=job_id,
            outline=TrainingOutlineV2(**outline.model_dump()),
            content_pack_summary={
                "id": content_pack.id,
                "title": content_pack.title,
                "topic": content_pack.topic,
                "source_count": len(content_pack.sources),
                "chunk_count": len(content_pack.chunks),
                "warnings": content_pack.warnings,
            },
            warnings=list(content_pack.warnings) + list(outline.warnings),
        )

    async def generate_ppt(self, payload: dict[str, Any], *, job_id: str) -> TrainingGenerateResponse:
        started_at = time.perf_counter()
        request = training_payload_to_request(payload)
        model_id = payload.get("model_id") or payload.get("modelId")
        logger.info(
            "training ppt generation started",
            extra={"event": "training_ppt_generation", "job_id": job_id, "model_id": model_id, "status": "started"},
        )
        try:
            content_pack = await asyncio.to_thread(build_content_pack, request, job_id)
            outline_payload = payload.get("outline")
            if outline_payload:
                outline = TrainingOutlineV2(**outline_payload)
            else:
                outline = await build_outline(content_pack, request, llm_service)
            spec = await plan_slides(outline, content_pack, request, llm_service)
            quality_report = check_presentation(spec, content_pack, request)
            template = get_template(request.get("template_id") or request.get("style"))
            render_info = render_presentation(
                spec,
                template,
                job_id,
                include_speaker_notes=request.get("include_speaker_notes", True),
            )
        except Exception as exc:
            logger.exception(
                "training ppt generation failed",
                extra={
                    "event": "training_ppt_generation",
                    "job_id": job_id,
                    "model_id": model_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "failed",
                    "error": type(exc).__name__,
                },
            )
            raise

        save_content_pack(job_id, content_pack.model_dump())
        save_outline(job_id, outline.model_dump())
        save_spec(job_id, spec.model_dump())
        save_quality_report(job_id, quality_report.model_dump())
        logger.info(
            "training ppt generation completed",
            extra={
                "event": "training_ppt_generation",
                "job_id": job_id,
                "model_id": model_id,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "status": "completed" if quality_report.passed else "completed_with_warnings",
            },
        )

        return TrainingGenerateResponse(
            job_id=job_id,
            status="completed" if quality_report.passed else "completed_with_warnings",
            presentation=PresentationSpec(**spec.model_dump()),
            quality_report=QualityReport(**quality_report.model_dump()),
            download_url=render_info["download_url"],
            filename=render_info["filename"],
            notes_download_url=render_info.get("notes_download_url"),
            notes_filename=render_info.get("notes_filename"),
        )


training_ppt_service = TrainingPptService()
