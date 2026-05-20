"""PPT 培训材料生成编排服务。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from backend.models import (
    PresentationSpec,
    QualityReport,
    TrainingGenerateResponse,
    TrainingOutline,
    TrainingOutlineResponse,
)
from backend.services.llm import llm_service
from backend.services.presentation.content_pack import build_content_pack, normalize_sources
from backend.services.presentation.outline_builder import generate_outline as build_outline
from backend.services.presentation.pptx_renderer import render_presentation
from backend.services.presentation.project_store import (
    PRESENTATIONS_DIR,
    get_job_paths,
    get_running_job_cancel_event,
    update_job_progress,
)
from backend.services.presentation.quality_check import check_presentation
from backend.services.presentation.quality_check import repair_presentation
from backend.services.presentation.safety_templates import get_template
from backend.services.presentation.slide_planner import plan_slides

logger = logging.getLogger(__name__)


def _raise_if_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()


def training_payload_to_request(payload: dict[str, Any]) -> dict[str, Any]:
    sources = payload.get("sources") or normalize_sources(payload)
    topic = payload.get("topic") or payload.get("title") or payload.get("prompt") or ""
    return {
        "sources": sources,
        "title": payload.get("title") or topic,
        "report_date": payload.get("report_date") or payload.get("reportDate"),
        "presenter": payload.get("presenter"),
        "requirements": payload.get("requirements") or payload.get("requirement"),
        "topic": topic,
        "audience": payload.get("audience", "一线员工"),
        "duration_minutes": payload.get("duration_minutes", 60),
        "slide_count": payload.get("slide_count", 12),
        "style": payload.get("style", "standard_training"),
        "focus_areas": payload.get("focus_areas", []),
        "include_quiz": payload.get("include_quiz", True),
        "template_id": payload.get("template_id") or payload.get("template") or payload.get("style", "standard_training"),
        "job_id": payload.get("job_id") or payload.get("jobId"),
    }


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class TrainingPptService:
    async def generate_outline(self, payload: dict[str, Any], *, job_id: str) -> TrainingOutlineResponse:
        started_at = time.perf_counter()
        request = training_payload_to_request(payload)
        model_id = payload.get("model_id") or payload.get("modelId")
        logger.info("outline generation started", extra={"event": "ppt_outline", "job_id": job_id})

        try:
            cancel_event = get_running_job_cancel_event(job_id)
            update_job_progress(job_id, "正在解析用户输入与文档...")
            await asyncio.sleep(0)
            _raise_if_cancelled(cancel_event)
            _t0 = time.perf_counter()
            content_pack = await asyncio.to_thread(build_content_pack, request, job_id, cancel_event)
            logger.info("content_pack_done", extra={
                "event": "ppt_outline", "job_id": job_id,
                "duration_ms": int((time.perf_counter() - _t0) * 1000),
                "source_count": len(content_pack.sources),
                "chunk_count": len(content_pack.chunks),
            })
            await asyncio.sleep(0)
            _raise_if_cancelled(cancel_event)
            slide_count = int(request.get("slide_count", 12))
            update_job_progress(job_id, f"正在生成PPT大纲（共{slide_count}页）...")
            await asyncio.sleep(0)
            outline = await build_outline(content_pack, request, llm_service, cancel_event, job_id=job_id)
            _raise_if_cancelled(cancel_event)
        except asyncio.CancelledError:
            update_job_progress(job_id, "已停止生成")
            raise
        except Exception as exc:
            logger.error("PPT大纲生成失败: %s", str(exc)[:300], extra={"event": "ppt_outline", "job_id": job_id})
            raise

        paths = get_job_paths(job_id)
        _save_json(paths.content_pack_path, content_pack.model_dump())
        _save_json(paths.outline_path, outline.model_dump())

        logger.info("outline generation completed", extra={
            "event": "ppt_outline", "job_id": job_id,
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        })

        return TrainingOutlineResponse(
            job_id=job_id,
            outline=outline,
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
        logger.info("ppt generation started", extra={"event": "ppt_generate", "job_id": job_id})

        try:
            cancel_event = get_running_job_cancel_event(job_id)
            update_job_progress(job_id, "正在解析用户输入与文档...")
            await asyncio.sleep(0)
            _raise_if_cancelled(cancel_event)
            _t1 = time.perf_counter()
            content_pack = await asyncio.to_thread(build_content_pack, request, job_id, cancel_event)
            logger.info("content_pack_done", extra={
                "event": "ppt_generate", "job_id": job_id,
                "duration_ms": int((time.perf_counter() - _t1) * 1000),
                "source_count": len(content_pack.sources),
                "chunk_count": len(content_pack.chunks),
            })
            await asyncio.sleep(0)
            _raise_if_cancelled(cancel_event)

            outline_payload = payload.get("outline")
            if outline_payload:
                outline = TrainingOutline(**outline_payload)
            else:
                slide_count = int(request.get("slide_count", 12))
                update_job_progress(job_id, f"正在生成PPT大纲（共{slide_count}页）...")
                outline = await build_outline(content_pack, request, llm_service, cancel_event, job_id=job_id)
            _raise_if_cancelled(cancel_event)

            update_job_progress(job_id, "正在根据PPT大纲逐页生成PPT...")
            await asyncio.sleep(0)
            spec = plan_slides(outline, content_pack, request, cancel_event)
            _raise_if_cancelled(cancel_event)

            update_job_progress(job_id, "正在检查幻灯片质量...")
            await asyncio.sleep(0)
            quality_report = check_presentation(spec, content_pack, request, cancel_event)
            _raise_if_cancelled(cancel_event)

            if not quality_report.passed or quality_report.issues:
                spec = repair_presentation(spec, content_pack, request)
                quality_report = check_presentation(spec, content_pack, request, cancel_event)

            template = get_template(request.get("template_id") or request.get("style"))
            await asyncio.sleep(0)
            render_info = await asyncio.to_thread(
                render_presentation,
                spec,
                template,
                job_id,
                None,
                request.get("title") or request.get("topic") or spec.title,
                cancel_event,
            )
        except asyncio.CancelledError:
            update_job_progress(job_id, "已停止生成")
            raise
        except Exception as exc:
            logger.error("PPT生成失败: %s", str(exc)[:300], extra={"event": "ppt_generate", "job_id": job_id})
            raise

        paths = get_job_paths(job_id)
        _save_json(paths.content_pack_path, content_pack.model_dump())
        _save_json(paths.outline_path, outline.model_dump())
        _save_json(paths.spec_path, spec.model_dump())
        _save_json(paths.quality_report_path, quality_report.model_dump())

        status = "completed" if quality_report.passed else "completed_with_warnings"
        logger.info("ppt generation completed", extra={
            "event": "ppt_generate", "job_id": job_id, "status": status,
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        })

        return TrainingGenerateResponse(
            job_id=job_id,
            status=status,
            presentation=PresentationSpec(**spec.model_dump()),
            quality_report=QualityReport(**quality_report.model_dump()),
            download_url=render_info["download_url"],
            filename=render_info["filename"],
        )


training_ppt_service = TrainingPptService()
