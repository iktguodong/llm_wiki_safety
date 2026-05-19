from __future__ import annotations

import asyncio

import pytest

import backend.config as config_module
from backend.models import KnowledgeBaseCreate
from backend.services.document import doc_service
from backend.services.llm import llm_service
from backend.services.knowledge_base import kb_service
from backend.services.wiki import WikiService, wiki_service
from backend.config import get_kb_index_path, get_kb_log_path


def test_split_document_into_chunks_preserves_content():
    text = (
        "# 公司法\n\n"
        "## 第一章\n\n"
        + ("第1条 这是第一段内容，用来模拟较长的法律条文。 " * 120)
        + "\n\n## 第二章\n\n"
        + ("第2条 这是第二段内容，用来模拟另一段较长的法律条文。 " * 120)
    )

    chunks = WikiService._split_document_into_chunks(text, max_chars=5000)

    assert len(chunks) >= 2
    assert chunks[0].startswith("# 公司法")
    assert any("第一章" in chunk for chunk in chunks)
    assert any("第二章" in chunk for chunk in chunks)
    assert any("第1条" in chunk for chunk in chunks)
    assert any("第2条" in chunk for chunk in chunks)


def test_build_system_content_omits_conflicting_output_contract():
    system_content = WikiService._build_system_content()

    assert "Return only a valid JSON array" not in system_content
    assert "## Output contract" not in system_content
    assert "## Page selection" in system_content


@pytest.mark.asyncio
async def test_update_knowledge_base_renames_generated_files(isolated_training_env, monkeypatch):
    monkeypatch.setitem(config_module.config, "knowledge_bases", {})

    kb = await kb_service.create(KnowledgeBaseCreate(name="原始名称", description="原始描述"))

    updated = await kb_service.update(kb.id, KnowledgeBaseCreate(name="新名称"))

    assert updated is not None
    assert updated.name == "新名称"
    assert config_module.config["knowledge_bases"][kb.id]["name"] == "新名称"
    assert get_kb_index_path(kb.id).read_text(encoding="utf-8").splitlines()[0] == "# 新名称 知识库索引"
    assert get_kb_log_path(kb.id).read_text(encoding="utf-8").splitlines()[0] == "# 新名称 知识库操作日志"


@pytest.mark.asyncio
async def test_extract_chunk_card_accepts_json_array(monkeypatch):
    async def fake_chat_sync(messages, model_id=None, temperature=0.2):
        return (
            '[{"chunk_summary":"分块摘要","key_points":["关键点1"],'
            '"candidate_pages":[{"slug":"test-topic","title":"测试主题",'
            '"page_type":"concept","importance":3,"summary":"主题页摘要",'
            '"key_facts":["事实1"],"evidence":["证据1"],"related_pages":[]}]}]'
        )

    monkeypatch.setattr(llm_service, "chat_sync", fake_chat_sync)

    card = await WikiService._extract_chunk_card(
        system_content="system",
        doc_name="test.md",
        chunk_text="chunk",
        chunk_index=1,
        chunk_total=1,
        model_id="deepseek-v4-flash",
    )

    assert card["chunk_summary"] == "分块摘要"
    assert card["candidate_pages"][0]["title"] == "测试主题"


@pytest.mark.asyncio
async def test_parallel_parse_document_generates_pages(isolated_training_env, monkeypatch):
    config_module.config["models"]["providers"] = [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "models": [
                {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
            ],
        }
    ]
    config_module.config["models"]["model_roles"] = {
        "doc_parse": "deepseek-v4-flash",
        "qa_chat": "deepseek-v4-flash",
        "ppt_gen": "deepseek-v4-flash",
    }
    config_module.config["current_model_id"] = "deepseek-v4-flash"

    kb = await kb_service.create(KnowledgeBaseCreate(name="并行解析测试"))

    source_text = (
        "# 公司法\n\n"
        "## 第一章 总则\n\n"
        + ("第1条 公司设立、组织、运营与治理相关内容。 " * 250)
        + "\n\n## 第二章 组织机构\n\n"
        + ("第2条 股东会、董事会、监事会与经理职责。 " * 250)
    )
    doc = await doc_service.upload(kb.id, "company-law.md", source_text.encode("utf-8"))

    active_calls = 0
    max_concurrent_calls = 0
    call_count = 0
    lock = asyncio.Lock()

    async def fake_extract_chunk_card(
        *,
        system_content,
        doc_name,
        chunk_text,
        chunk_index,
        chunk_total,
        model_id,
    ):
        nonlocal active_calls, max_concurrent_calls, call_count
        async with lock:
            active_calls += 1
            call_count += 1
            max_concurrent_calls = max(max_concurrent_calls, active_calls)

        try:
            await asyncio.sleep(0.05)
            return {
                "chunk_summary": f"第{chunk_index}块摘要",
                "key_points": [f"第{chunk_index}块关键点"],
                "candidate_pages": [
                    {
                        "slug": f"company-law-topic-{chunk_index}",
                        "title": f"公司法主题 {chunk_index}",
                        "page_type": "concept",
                        "importance": 5,
                        "summary": f"围绕第{chunk_index}块内容形成的主题页。",
                        "key_facts": [f"第{chunk_index}块事实"],
                        "evidence": [f"第{chunk_index}块证据"],
                        "related_pages": [],
                    }
                ],
            }
        finally:
            async with lock:
                active_calls -= 1

    async def fake_render_page_markdown(
        *,
        system_content,
        page_plan,
        source_file,
        model_id,
    ):
        nonlocal active_calls, max_concurrent_calls, call_count
        async with lock:
            active_calls += 1
            call_count += 1
            max_concurrent_calls = max(max_concurrent_calls, active_calls)

        try:
            await asyncio.sleep(0.05)
            if page_plan.get("page_type") == "summary":
                return (
                    "# 公司法\n\n"
                    "**Summary**: 公司法文档概览\n\n"
                    "**Sources**: company-law.md\n\n"
                    "**Last updated**: 2026-05-13\n\n"
                    "---\n\n"
                    "## 核心内容\n\n"
                    "- 公司设立与组织治理\n"
                    "- 股东会、董事会、监事会职责\n"
                )

            return (
                f"# {page_plan.get('title')}\n\n"
                "**Summary**: 主题页摘要\n\n"
                "**Sources**: company-law.md\n\n"
                "**Last updated**: 2026-05-13\n\n"
                "---\n\n"
                "## 关键事实\n\n"
                "- 这是测试页\n"
            )
        finally:
            async with lock:
                active_calls -= 1

    monkeypatch.setattr(WikiService, "_extract_chunk_card", staticmethod(fake_extract_chunk_card))
    monkeypatch.setattr(WikiService, "_render_page_markdown", staticmethod(fake_render_page_markdown))

    await wiki_service.parse_document(kb.id, doc.id, model_id="deepseek-v4-flash")

    docs = await doc_service.list_documents(kb.id)
    assert docs[0].parse_status == "completed"
    assert docs[0].page_count >= 3
    assert max_concurrent_calls >= 2
    assert call_count >= 5

    wiki_path = isolated_training_env["kb_root"] / kb.id / "wiki"
    wiki_files = sorted(p.name for p in wiki_path.glob("*.md") if p.name not in {"index.md", "log.md"})
    assert len(wiki_files) >= 3
    assert any(name.endswith("-summary.md") for name in wiki_files)
    assert any(name.startswith("company-law-topic-") for name in wiki_files)


@pytest.mark.asyncio
async def test_parse_document_falls_back_to_source_excerpt(isolated_training_env, monkeypatch):
    config_module.config["models"]["providers"] = [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "models": [
                {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
            ],
        }
    ]
    config_module.config["models"]["model_roles"] = {
        "doc_parse": "deepseek-v4-flash",
        "qa_chat": "deepseek-v4-flash",
        "ppt_gen": "deepseek-v4-flash",
    }
    config_module.config["current_model_id"] = "deepseek-v4-flash"

    kb = await kb_service.create(KnowledgeBaseCreate(name="兜底摘要测试"))
    source_text = (
        "# 相关方安全管理规范\n\n"
        "第一段内容说明现场作业审批和培训要求。\n\n"
        "第二段内容说明检查、监督与记录保存要求。"
    )
    doc = await doc_service.upload(kb.id, "related-party-safety.md", source_text.encode("utf-8"))

    async def fake_extract_chunk_card(
        *,
        system_content,
        doc_name,
        chunk_text,
        chunk_index,
        chunk_total,
        model_id,
    ):
        return {}

    async def fake_render_page_markdown(
        *,
        system_content,
        page_plan,
        source_file,
        model_id,
    ):
        return ""

    monkeypatch.setattr(WikiService, "_extract_chunk_card", staticmethod(fake_extract_chunk_card))
    monkeypatch.setattr(WikiService, "_render_page_markdown", staticmethod(fake_render_page_markdown))

    await wiki_service.parse_document(kb.id, doc.id, model_id="deepseek-v4-flash")

    docs = await doc_service.list_documents(kb.id)
    assert docs[0].parse_status == "completed"
    assert docs[0].page_count == 1

    wiki_path = isolated_training_env["kb_root"] / kb.id / "wiki"
    summary_page = wiki_path / "related-party-safety-summary.md"
    content = summary_page.read_text(encoding="utf-8")

    assert "第一段内容说明现场作业审批和培训要求。" in content
    assert "第二段内容说明检查、监督与记录保存要求。" in content


@pytest.mark.asyncio
async def test_reset_stale_parse_statuses_resets_parsing_docs(isolated_training_env):
    kb = await kb_service.create(KnowledgeBaseCreate(name="解析状态重置测试"))
    doc = await doc_service.upload(kb.id, "stale.txt", "测试".encode("utf-8"))
    await doc_service.update_parse_status(kb.id, doc.id, "parsing")

    reset_count = await doc_service.reset_stale_parse_statuses()
    docs = await doc_service.list_documents(kb.id)

    assert reset_count == 1
    assert docs[0].parse_status == "pending"
