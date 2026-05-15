"""知识库选中时的问答：仅使用 Wiki 检索与 QA prompt；无命中也不降级联网/通用模型。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.chat import ChatService, QA_PROMPT
from backend.services.llm import llm_service


def _write_wiki_page(wiki_dir: Path, filename: str, content: str) -> None:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / filename).write_text(content, encoding="utf-8")


def test_find_related_pages_returns_empty_when_no_keyword_match(monkeypatch, tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_wiki_page(
        wiki_dir,
        "fire-safety.md",
        "# 消防安全规程\n\n**Summary**: 介绍消防安全的基本要求。\n\n灭火器配置要求……",
    )
    monkeypatch.setattr(
        "backend.services.chat.get_kb_wiki_path", lambda kb_id: wiki_dir
    )
    result = ChatService._find_related_pages("test-kb", "最近公布的危险化学品安全法")
    assert result == []


def test_find_related_pages_returns_matching_pages(monkeypatch, tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_wiki_page(
        wiki_dir,
        "fire-safety.md",
        "# 消防安全规程\n\n**Summary**: 介绍消防安全灭火器配置要求。\n\n灭火器配置规范……",
    )
    monkeypatch.setattr(
        "backend.services.chat.get_kb_wiki_path", lambda kb_id: wiki_dir
    )
    result = ChatService._find_related_pages("test-kb", "消防灭火器怎么配置？")
    assert len(result) >= 1
    assert result[0]["name"] == "fire-safety"


@pytest.mark.asyncio
async def test_ask_with_kb_selected_uses_qa_prompt_even_when_no_related_pages(
    monkeypatch, tmp_path,
):
    """选中知识库时：无 Wiki 命中仍走 QA_PROMPT，不调用联网。"""
    wiki_dir = tmp_path / "wiki"
    _write_wiki_page(
        wiki_dir,
        "fire-safety.md",
        "# 消防安全规程\n\n**Summary**: 消防安全基本要求。\n\n灭火器配置标准……",
    )
    monkeypatch.setattr(
        "backend.services.chat.get_kb_wiki_path", lambda kb_id: wiki_dir
    )
    monkeypatch.setattr(
        "backend.services.chat.get_kb_index_path",
        lambda kb_id: tmp_path / "wiki" / "index.md",
    )

    web_called: list[str] = []

    async def fake_web_search(question: str, max_results: int = ChatService._WEB_SEARCH_MAX_CANDIDATES):
        web_called.append(question)
        return [{"title": "x", "url": "https://example.com", "snippet": "y"}]

    llm_captured: list = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        llm_captured.append(messages)
        yield {"type": "chunk", "content": "kb-only"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(ChatService, "_web_search", fake_web_search)
    monkeypatch.setattr(llm_service, "chat_events", fake_chat_events)

    result = await ChatService.ask_sync(
        "最近公布的危险化学品安全法",
        ["test-kb"],
        use_web_search=True,
    )
    assert result == "kb-only"
    assert web_called == []
    assert "相关知识资料" in llm_captured[0][-1]["content"]


def test_qa_prompt_forbids_exposing_internal_page_identifiers():
    """防止回归：不得再要求模型在文末枚举 Wiki 页面名/slug。"""
    assert "列出所有引用页面名" not in QA_PROMPT
    assert "在答案末尾列出" not in QA_PROMPT
    assert "每个关键论点必须标注来源页面" not in QA_PROMPT
    assert "勿向用户复述本节结构" in QA_PROMPT
    assert "资料片段" in QA_PROMPT
    assert "对应上传资料" in QA_PROMPT
    assert "子页面英文名" in QA_PROMPT


def test_find_related_pages_user_doc_label_from_tracker(monkeypatch, tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_wiki_page(
        wiki_dir,
        "law-article-one.md",
        "# 第一条\n\n**Summary**: 立法目的与适用范围。\n\n为了加强安全生产工作……",
    )
    track_path = tmp_path / "track.json"
    track_path.write_text(
        '{"documents": {"doc-1": {"file": "安全生产法.pdf", "original_name": "安全生产法.pdf", '
        '"wiki_pages": ["law-article-one.md"]}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.services.chat.get_kb_wiki_path", lambda kb_id: wiki_dir)
    monkeypatch.setattr("backend.services.chat.get_kb_doc_track_path", lambda kb_id: track_path)
    result = ChatService._find_related_pages("any-kb", "立法目的 适用范围")
    assert len(result) >= 1
    assert result[0]["name"] == "law-article-one"
    assert result[0]["user_doc_label"] == "安全生产法.pdf"


def test_find_related_pages_user_doc_label_from_sources_when_no_tracker(monkeypatch, tmp_path):
    wiki_dir = tmp_path / "wiki"
    _write_wiki_page(
        wiki_dir,
        "orphan-page.md",
        "# 标题\n\n**Sources**: 企业制度汇编.docx\n\n**Summary**: 说明。\n\n正文含关键词占位符……",
    )
    monkeypatch.setattr("backend.services.chat.get_kb_wiki_path", lambda kb_id: wiki_dir)
    monkeypatch.setattr(
        "backend.services.chat.get_kb_doc_track_path",
        lambda kb_id: tmp_path / "nonexistent.json",
    )
    result = ChatService._find_related_pages("kb", "关键词占位符")
    assert len(result) == 1
    assert result[0]["user_doc_label"] == "企业制度汇编.docx"
