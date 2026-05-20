"""PPT 大纲生成测试。"""

from __future__ import annotations

import asyncio
import json
import re

import pytest

import backend.config as config_module
from backend.models import TrainingOutlinePoint, TrainingOutlineSlide
from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation import outline_builder
from backend.services.presentation.outline_builder import _build_llm_prompt, _build_section_body_prompt, generate_outline


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30
    slide_count = 15
    style = "standard_training"
    focus_areas = ["应急处置", "报警流程"]
    include_quiz = True


def _outline_stage1_response(slide_count: int) -> str:
    slides = []
    for index in range(1, slide_count + 1):
        slides.append({
            "title": f"页面{index}",
            "sections": [
                {"subtitle": f"第{index}页小节A"},
                {"subtitle": f"第{index}页小节B"},
            ],
        })
    return json.dumps({"slides": slides}, ensure_ascii=False)


class TwoStageMockLLM:
    def __init__(self, slide_count: int, *, body_delay: float = 0.0):
        self.slide_count = slide_count
        self.body_delay = body_delay
        self.active_body_calls = 0
        self.max_active_body_calls = 0
        self._lock: asyncio.Lock | None = None

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
        prompt = messages[-1]["content"]
        if "扩写成适合 PPT 展示的正文段落" in prompt:
            lock = self._ensure_lock()
            async with lock:
                self.active_body_calls += 1
                self.max_active_body_calls = max(self.max_active_body_calls, self.active_body_calls)
            try:
                if self.body_delay:
                    await asyncio.sleep(self.body_delay)
                title_match = re.search(r"页面标题：(.+)", prompt)
                title = title_match.group(1).strip() if title_match else "页面"
                section_match = re.search(r"小节标题：(.+)", prompt)
                subtitle = section_match.group(1).strip() if section_match else f"{title}小节"
                return json.dumps({
                    "subtitle": subtitle,
                    "paragraphs": [
                        f"{subtitle} 的第一段正文，说明背景、原因和重点动作。",
                        f"{subtitle} 的第二段正文，补充落实要求和注意事项。",
                    ],
                }, ensure_ascii=False)
            finally:
                lock = self._ensure_lock()
                async with lock:
                    self.active_body_calls -= 1
        return _outline_stage1_response(self.slide_count)


def test_prompt_only_outline_raises_without_llm(isolated_training_env):
    """没有配置 LLM 时，应当直接报错而不是回退到规则大纲。"""
    pack = build_content_pack(PromptReq())
    with pytest.raises(ValueError, match="LLM 模型不可用"):
        asyncio.run(generate_outline(pack, PromptReq()))


def test_outline_prompt_requests_subtitle_and_body(isolated_training_env):
    pack = build_content_pack(PromptReq())
    prompt = _build_llm_prompt(pack, {"title": "材料标题", "audience": "公司管理层", "slide_count": 6})

    assert "安全生产内容策划专家" in prompt
    assert "培训、汇报和分享" in prompt
    assert "正文骨架" in prompt
    assert "sections" in prompt
    assert "points" not in prompt


def test_outline_body_prompt_requests_paragraphs(isolated_training_env):
    pack = build_content_pack(PromptReq())
    slide = TrainingOutlineSlide(
        id="slide-1",
        slide_no=2,
        title="关键流程",
        subtitle="把流程说清楚",
        sections=[],
        slide_type="content",
        visual_type="text",
    )
    from backend.models import TrainingSlideSection
    slide.sections = [TrainingSlideSection(id="section-1", subtitle="报警与上报", paragraphs=[])]
    prompt = _build_section_body_prompt(pack, {"title": "材料标题", "audience": "公司管理层"}, slide, slide.sections[0], list(pack.chunks))

    assert "扩写成适合 PPT 展示的正文段落" in prompt
    assert "小节标题" in prompt
    assert "paragraphs" in prompt
    assert "页面标题" in prompt
    assert "1-3" in prompt
    assert "一行" in prompt
    assert "编号" in prompt


def test_outline_generation_times_out_raises_error(isolated_training_env, monkeypatch):
    class SlowLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            await asyncio.sleep(1)
            return '{"slides":[{"title":"不会用到","key_points":["A"]}]}'

    monkeypatch.setattr(outline_builder, "OUTLINE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com",
         "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash", "name": "DS", "type": "chat"}]}
    ])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    with pytest.raises(ValueError, match="LLM 调用超时"):
        asyncio.run(generate_outline(build_content_pack(PromptReq()), PromptReq(), llm_client=SlowLLM()))


def test_llm_outline_adds_cover_and_points(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com",
         "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash", "name": "DS", "type": "chat"}]}
    ])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    req = {
        "sources": [{"type": "prompt", "prompt": "应急处置培训"}],
        "title": "红杉 AI 峰会解读", "topic": "红杉 AI 峰会解读",
        "report_date": "2026年5月21日", "presenter": "刘明超",
        "audience": "公司管理层", "duration_minutes": 30,
        "slide_count": 4, "style": "standard_training",
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=TwoStageMockLLM(3)))

    assert len(outline.slides) == 4
    assert outline.slides[0].slide_type == "cover"
    assert outline.slides[1].sections
    assert outline.slides[1].body_paragraphs
    assert outline.slides[1].sections[0].subtitle


def test_outline_body_generation_runs_concurrently(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com",
         "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash", "name": "DS", "type": "chat"}]}
    ])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    req = {
        "sources": [{"type": "prompt", "prompt": "并发测试"}],
        "title": "并发测试", "topic": "并发测试",
        "audience": "管理层", "duration_minutes": 30,
        "slide_count": 5, "style": "standard_training",
    }
    llm = TwoStageMockLLM(4, body_delay=0.05)
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=llm))

    assert len(outline.slides) == 5
    assert outline.slides[1].sections
    assert outline.slides[1].body_paragraphs
    assert 2 <= llm.max_active_body_calls <= 3


def test_legacy_key_points_still_supported(isolated_training_env, monkeypatch):
    class LegacyLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            prompt = messages[-1]["content"]
            if "扩写成适合 PPT 展示的正文段落" in prompt:
                title_match = re.search(r"页面标题：(.+)", prompt)
                title = title_match.group(1).strip() if title_match else "页面"
                section_match = re.search(r"小节标题：(.+)", prompt)
                subtitle = section_match.group(1).strip() if section_match else f"{title}小节"
                return json.dumps({
                    "subtitle": subtitle,
                    "paragraphs": [f"{subtitle} 的正文一。", f"{subtitle} 的正文二。"],
                }, ensure_ascii=False)
            return '{"slides":[{"title":"旧格式页","sections":[{"subtitle":"要点A"},{"subtitle":"要点B"}]},{"title":"第二页","sections":[{"subtitle":"要点C"}]}]}'

    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com",
         "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash", "name": "DS", "type": "chat"}]}
    ])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    req = {"sources": [{"type": "prompt", "prompt": "旧格式兼容"}], "title": "旧格式兼容", "topic": "旧格式兼容", "slide_count": 3, "style": "standard_training"}
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=LegacyLLM()))
    assert len(outline.slides) == 3
    assert outline.slides[1].sections[0].subtitle == "要点A"
    assert outline.slides[1].body_paragraphs


def test_knowledge_base_outline(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "test", "name": "Test", "base_url": "http://test", "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash"}]}
    ])

    from backend.config import get_kb_wiki_path, get_kb_raw_path
    from backend.services.document import doc_service

    kb_id = "kb-outline-test"
    wiki_path = get_kb_wiki_path(kb_id)
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "index.md").write_text("# 索引\n\n- [[fire]] 火灾应急", encoding="utf-8")
    (wiki_path / "fire.md").write_text("# 火灾应急\n\n发现火情立即报警。", encoding="utf-8")

    raw_path = get_kb_raw_path(kb_id)
    raw_path.mkdir(parents=True, exist_ok=True)
    doc = asyncio.run(doc_service.upload(kb_id, "raw.txt", "检查清单与职责".encode("utf-8")))

    req = {
        "sources": [
            {"type": "knowledge_base", "kb_id": kb_id},
            {"type": "kb_document", "kb_id": kb_id, "document_id": doc.id},
        ],
        "topic": "知识库测试", "audience": "管理层", "duration_minutes": 40,
        "slide_count": 12, "style": "management_briefing",
        "focus_areas": ["职责", "流程"], "include_quiz": True,
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=TwoStageMockLLM(3)))
    assert len(outline.slides) >= 4
    assert outline.style == "management_briefing"
    assert outline.slides[1].sections
    assert outline.slides[1].body_paragraphs
