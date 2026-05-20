"""培训生成服务的薄封装。"""

from __future__ import annotations

from typing import Any, Optional

from backend.services.llm import llm_service
from backend.services.presentation.content_pack import build_content_pack, normalize_sources
from backend.services.presentation.outline_builder import generate_outline as build_outline
from backend.services.presentation.project_store import create_job, save_content_pack, save_outline, save_quality_report, save_spec
from backend.services.presentation.pptx_renderer import render_presentation
from backend.services.presentation.quality_check import check_presentation
from backend.services.presentation.slide_planner import plan_slides
from backend.services.presentation.safety_templates import get_template

def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _legacy_payload(
    *,
    source_type: Optional[str] = None,
    source_ids: Optional[list[str]] = None,
    topic: str = "",
    audience: str = "",
    duration_minutes: int = 60,
    slide_count: int = 12,
    focus_areas: Optional[list[str]] = None,
    style: str = "standard_training",
    include_quiz: bool = True,
    job_id: Optional[str] = None,
    template_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "sources": normalize_sources({
            "source_type": source_type,
            "source_ids": source_ids or [],
            "topic": topic,
        }),
        "topic": topic,
        "audience": audience,
        "duration_minutes": duration_minutes,
        "slide_count": slide_count,
        "focus_areas": focus_areas or [],
        "style": style,
        "include_quiz": include_quiz,
        "job_id": job_id,
        "template_id": template_id or style,
    }


class TrainingService:
    async def generate_outline(
        self,
        source_type: Optional[str] = None,
        source_ids: Optional[list[str]] = None,
        topic: str = "",
        audience: str = "一线员工",
        duration: int = 60,
        slide_count: int = 12,
        focus_areas: Optional[list[str]] = None,
        model_id: Optional[str] = None,
        *,
        sources: Optional[list[dict[str, Any]]] = None,
        style: str = "standard_training",
        include_quiz: bool = True,
        job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload = _legacy_payload(
            source_type=source_type,
            source_ids=source_ids,
            topic=topic,
            audience=audience,
            duration_minutes=duration,
            slide_count=slide_count,
            focus_areas=focus_areas,
            style=style,
            include_quiz=include_quiz,
            job_id=job_id,
            template_id=style,
        )
        if sources is not None:
            payload["sources"] = sources
        payload["model_id"] = model_id
        job = create_job("outline", job_id=job_id)
        pack = build_content_pack(payload, job.job_id)
        outline = await build_outline(pack, payload, llm_service)
        save_content_pack(job.job_id, pack.model_dump())
        save_outline(job.job_id, outline.model_dump())
        return outline.model_dump()

    async def generate_ppt(
        self,
        outline: dict[str, Any],
        topic: str,
        audience: str,
        template: str = "standard_training",
        model_id: Optional[str] = None,
        *,
        source_type: Optional[str] = None,
        source_ids: Optional[list[str]] = None,
        duration_minutes: int = 60,
        slide_count: int = 12,
        focus_areas: Optional[list[str]] = None,
        style: str = "standard_training",
        include_quiz: bool = True,
        job_id: Optional[str] = None,
        sources: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        payload = _legacy_payload(
            source_type=source_type,
            source_ids=source_ids,
            topic=topic,
            audience=audience,
            duration_minutes=duration_minutes,
            slide_count=slide_count,
            focus_areas=focus_areas,
            style=style,
            include_quiz=include_quiz,
            job_id=job_id,
            template_id=template,
        )
        if sources is not None:
            payload["sources"] = sources
        job = create_job("generate", job_id=job_id)
        pack = build_content_pack(payload, job.job_id)
        outline_model = outline if hasattr(outline, "model_dump") else outline
        if not isinstance(outline_model, dict):
            outline_model = _as_dict(outline)
        # 保证生成阶段拿到的是结构化大纲
        if outline_model and "sections" in outline_model:
            outline_struct = outline_model
        else:
            outline_struct = (await build_outline(pack, payload, llm_service)).model_dump()
        spec = await plan_slides(outline_struct, pack, {**payload, "template_id": template}, llm_service)
        report = check_presentation(spec, pack, payload)
        render_info = render_presentation(spec, get_template(template), job.job_id)
        save_content_pack(job.job_id, pack.model_dump())
        save_outline(job.job_id, outline_struct)
        save_spec(job.job_id, spec.model_dump())
        save_quality_report(job.job_id, report.model_dump())
        return {
            "job_id": job.job_id,
            "status": "completed" if report.passed else "completed_with_warnings",
            "presentation": spec.model_dump(),
            "quality_report": report.model_dump(),
            "download_url": render_info["download_url"],
            "filename": render_info["filename"],
        }

training_service = TrainingService()
