"""PPT 生成全链路测试。"""

from __future__ import annotations

import asyncio
from threading import Event

import pytest

import backend.config as config_module
from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation.outline_builder import generate_outline
from backend.services.presentation.slide_planner import plan_slides
from backend.services.presentation.quality_check import check_presentation
from backend.services.presentation.pptx_renderer import render_presentation
from backend.services.presentation.safety_templates import get_template
from backend.services.presentation.project_store import get_job_paths
from backend.models import PresentationSpec, SlideSpec, TrainingOutline


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30
    slide_count = 15
    style = "standard_training"
    focus_areas = ["应急处置", "报警流程"]
    include_quiz = True
    template_id = "standard_training"


def test_outline_to_pptx_full_chain(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "test", "name": "Test", "base_url": "http://test", "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash"}]}
    ])

    class MockLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return '{"slides":[{"title":"危化品仓库风险","points":[{"title":"主要风险","description":"识别关键风险点"}]},{"title":"应急处置流程","points":[{"title":"报警","description":"第一时间报警"}]},{"title":"总结","points":[{"title":"行动项","description":"落实整改"}]}]}'

    req = PromptReq()
    pack = build_content_pack(req)
    outline = asyncio.run(generate_outline(pack, req, llm_client=MockLLM()))
    spec = plan_slides(outline, pack, req)
    report = check_presentation(spec, pack, req)
    render_info = render_presentation(spec, get_template("standard_training"), "job-full-1")

    assert report.summary
    assert render_info["pptx_path"].endswith(".pptx")
    assert get_job_paths("job-full-1").pptx_dir.joinpath("training_deck.pptx").exists()


def test_render_presentation_honors_cancel_event(isolated_training_env):
    spec = PresentationSpec(
        id="spec-cancel", title="测试", topic="测试", audience="管理层",
        duration_minutes=30, style="standard_training", template_id="standard_training",
        slides=[], quality_warnings=[],
    )
    cancel_event = Event()
    cancel_event.set()

    with pytest.raises(asyncio.CancelledError):
        render_presentation(spec, get_template("standard_training"), "job-cancel-1", cancel_event=cancel_event)


def test_quality_check_flags_missing_source(isolated_training_env):
    spec = PresentationSpec(
        id="spec-test", title="测试", topic="测试", audience="管理层",
        duration_minutes=30, style="standard_training", template_id="standard_training",
        slides=[
            SlideSpec(id="slide-1", slide_no=1, slide_type="legal_requirement", title="制度职责要求",
                      subtitle="", key_message="", bullets=["岗位职责必须明确"], source_refs=[],
                      notes="", visual_type="table", safety_level="warning")
        ], quality_warnings=[],
    )
    pack = build_content_pack({"sources": [{"type": "prompt", "prompt": "制度职责"}], "topic": "测试", "audience": "管理层"})
    report = check_presentation(spec, pack, {"slide_count": 1})
    assert any(issue.code in {"missing_source", "legal_without_source"} for issue in report.issues)


def test_ppt_service_generate_cancels_properly(isolated_training_env, monkeypatch):
    from backend.services.training_ppt import training_ppt_service

    cancel_event = Event()
    cancel_event.set()

    monkeypatch.setattr(
        "backend.services.training_ppt.get_running_job_cancel_event",
        lambda job_id: cancel_event,
    )

    async def fake_build_outline(*args, **kwargs):
        return TrainingOutline(
            id="outline-cancel", title="测试取消", topic="测试取消",
            audience="一线员工", duration_minutes=30, style="standard_training",
            slides=[], sections=[], warnings=[],
        )

    async def fake_render(*args, **kwargs):
        raise AssertionError("render should not be reached after cancellation")

    monkeypatch.setattr("backend.services.training_ppt.render_presentation", fake_render)
    monkeypatch.setattr("backend.services.training_ppt.build_outline", fake_build_outline)

    async def run():
        payload = {
            "sources": [{"type": "prompt", "prompt": "应急处置培训"}],
            "title": "测试取消", "topic": "测试取消",
            "audience": "一线员工", "duration_minutes": 30,
            "slide_count": 6, "style": "standard_training",
            "template_id": "standard_training", "include_quiz": True,
        }
        with pytest.raises(asyncio.CancelledError):
            await training_ppt_service.generate_ppt(payload, job_id="job-cancel-render")

    asyncio.run(run())
