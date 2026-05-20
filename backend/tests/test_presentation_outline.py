from __future__ import annotations

import asyncio
import pytest

import backend.config as config_module
from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation import outline_builder
from backend.services.presentation.outline_builder import generate_outline
from backend.services.document import doc_service
from backend.config import get_kb_wiki_path, get_kb_raw_path


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30
    slide_count = 15
    style = "standard_training"
    focus_areas = ["应急处置", "报警流程"]
    include_quiz = True


def test_prompt_only_outline_falls_back_to_default_sections(isolated_training_env):
    pack = build_content_pack(PromptReq())
    outline = asyncio.run(generate_outline(pack, PromptReq()))
    assert len(outline.slides) >= 3
    assert len(outline.sections) >= 1
    assert any("未绑定企业原文来源" in warning for warning in outline.warnings)


def test_outline_generation_times_out_and_falls_back(isolated_training_env, monkeypatch):
    class SlowLLM:
        def __init__(self):
            self.calls = []

        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            self.calls.append({
                "model_id": model_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
            })
            await asyncio.sleep(1)
            return '{"slides":[{"title":"应该不会被用到","key_points":["A"],"notes":"B","layout_hint":"C","slide_type":"content"}]}'

    monkeypatch.setattr(outline_builder, "OUTLINE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setitem(
        config_module.config["models"],
        "providers",
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-test",
                "models": [
                    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                ],
            }
        ],
    )
    monkeypatch.setitem(
        config_module.config["models"],
        "model_roles",
        {
            "doc_parse": "deepseek-v4-flash",
            "qa_chat": "deepseek-v4-flash",
            "ppt_gen": "deepseek-v4-flash",
        },
    )

    llm = SlowLLM()
    req = PromptReq()
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=llm))

    assert len(outline.slides) >= 3
    assert any("超时" in warning for warning in outline.warnings)
    assert llm.calls and llm.calls[0]["max_tokens"] == outline_builder.OUTLINE_MAX_TOKENS


def test_compact_llm_outline_adds_cover_and_points(isolated_training_env, monkeypatch):
    class CompactLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return """
            {
              "slides": [
                {"title": "背景与目标", "points": [{"title": "培训背景", "description": "说明本次培训来源和目的"}]},
                {"title": "关键流程", "points": [{"title": "先报警", "description": "发现异常后立即报告"}]},
                {"title": "总结行动", "points": [{"title": "闭环整改", "description": "形成清单并跟踪"}]}
              ]
            }
            """

    monkeypatch.setitem(
        config_module.config["models"],
        "providers",
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-test",
                "models": [
                    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                ],
            }
        ],
    )
    monkeypatch.setitem(
        config_module.config["models"],
        "model_roles",
        {"ppt_gen": "deepseek-v4-flash"},
    )

    req = {
        "sources": [{"type": "prompt", "prompt": "应急处置培训"}],
        "title": "红杉2026 AI 闭门峰会解读",
        "topic": "红杉2026 AI 闭门峰会解读",
        "report_date": "2026年5月21日",
        "presenter": "刘明超",
        "audience": "公司管理层",
        "duration_minutes": 30,
        "slide_count": 4,
        "style": "standard_training",
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=CompactLLM()))

    assert len(outline.slides) == 4
    assert outline.slides[0].slide_type == "cover"
    assert outline.slides[0].title == "红杉2026 AI 闭门峰会解读"
    assert outline.slides[1].points[0].title == "培训背景"
    assert outline.slides[1].points[0].description == "说明本次培训来源和目的"


def test_legacy_key_points_output_still_supported(isolated_training_env, monkeypatch):
    class LegacyLLM:
        async def chat_sync(self, messages, model_id=None, temperature=0.7, max_tokens=None):
            return '{"slides":[{"title":"旧格式页","key_points":["要点A：说明A","要点B"]},{"title":"第二页","key_points":["要点C"]}]}'

    monkeypatch.setitem(
        config_module.config["models"],
        "providers",
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-test",
                "models": [
                    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                ],
            }
        ],
    )
    monkeypatch.setitem(config_module.config["models"], "model_roles", {"ppt_gen": "deepseek-v4-flash"})

    req = {
        "sources": [{"type": "prompt", "prompt": "旧格式兼容"}],
        "title": "旧格式兼容",
        "topic": "旧格式兼容",
        "slide_count": 3,
        "style": "standard_training",
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req, llm_client=LegacyLLM()))

    assert len(outline.slides) == 3
    assert outline.slides[1].points[0].title == "要点A"
    assert outline.slides[1].points[0].description == "说明A"


def test_missing_explicit_document_source_raises(isolated_training_env):
    req = {
        "sources": [{"type": "kb_document", "kb_id": "kb-missing", "document_id": "doc-missing"}],
        "title": "缺失文档",
        "topic": "缺失文档",
    }

    with pytest.raises(ValueError, match="未找到文档"):
        build_content_pack(req)


def test_temporary_upload_outline(isolated_training_env):
    from backend.services.presentation.project_store import get_upload_dir, save_upload_metadata

    upload_id = "upload-outline-1"
    upload_dir = get_upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_file = upload_dir / "guide.md"
    source_file.write_text("# 现场处置\n\n发现异常后立即上报。", encoding="utf-8")
    save_upload_metadata(upload_id, {
        "upload_id": upload_id,
        "filename": source_file.name,
        "path": str(source_file),
        "size": source_file.stat().st_size,
        "detected_type": "md",
    })

    req = {
        "sources": [{"type": "temporary_upload", "upload_id": upload_id}],
        "topic": "临时上传培训",
        "audience": "班组",
        "duration_minutes": 20,
        "slide_count": 10,
        "style": "frontline_shift_training",
        "focus_areas": ["异常上报"],
        "include_quiz": False,
    }
    outline = asyncio.run(generate_outline(build_content_pack(req, job_id="job-outline"), req))
    assert outline.slides
    assert outline.style == "frontline_shift_training"


def test_knowledge_base_outline(isolated_training_env):
    kb_id = "kb-outline-1"
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
        "topic": "知识库生成测试",
        "audience": "管理层",
        "duration_minutes": 40,
        "slide_count": 12,
        "style": "management_briefing",
        "focus_areas": ["职责", "流程"],
        "include_quiz": True,
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req))
    assert len(outline.slides) >= 4
    assert outline.style == "management_briefing"
