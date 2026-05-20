"""PPT 大纲生成测试。"""

from __future__ import annotations

import asyncio
import pytest

import backend.config as config_module
from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation import outline_builder
from backend.services.presentation.outline_builder import _build_llm_prompt, generate_outline


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30
    slide_count = 15
    style = "standard_training"
    focus_areas = ["应急处置", "报警流程"]
    include_quiz = True


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
    assert "subtitle" in prompt
    assert "body" in prompt
    assert "页面标题" in prompt
    assert "第一段正文" in prompt


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
    class MockLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return '{"slides":[{"title":"背景与目标","points":[{"title":"培训背景","description":"说明培训目的"}]},{"title":"关键流程","points":[{"title":"报警","description":"第一时间报警"}]},{"title":"总结行动","points":[{"title":"闭环","description":"形成清单跟踪"}]}]}'

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
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=MockLLM()))

    assert len(outline.slides) == 4
    assert outline.slides[0].slide_type == "cover"


def test_legacy_key_points_still_supported(isolated_training_env, monkeypatch):
    class LegacyLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return '{"slides":[{"title":"旧格式页","key_points":["要点A：说明A","要点B"]},{"title":"第二页","key_points":["要点C"]}]}'

    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com",
         "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash", "name": "DS", "type": "chat"}]}
    ])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    req = {"sources": [{"type": "prompt", "prompt": "旧格式兼容"}], "title": "旧格式兼容", "topic": "旧格式兼容", "slide_count": 3, "style": "standard_training"}
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=LegacyLLM()))
    assert len(outline.slides) == 3
    assert outline.slides[1].points[0].title == "要点A"


def test_knowledge_base_outline(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})
    monkeypatch.setitem(config_module.config["models"], "providers", [
        {"id": "test", "name": "Test", "base_url": "http://test", "api_key": "sk-test", "models": [{"id": "deepseek-v4-flash"}]}
    ])

    class MockLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return '{"slides":[{"title":"知识库要点","points":[{"title":"关键发现","description":"说明"}]},{"title":"分析","points":[{"title":"分析","description":"说明"}]},{"title":"建议","points":[{"title":"建议项","description":"说明"}]}]}'

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
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=MockLLM()))
    assert len(outline.slides) >= 4
    assert outline.style == "management_briefing"
