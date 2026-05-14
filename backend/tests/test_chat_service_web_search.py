from __future__ import annotations

import pytest
import httpx

from backend.models import ChatMessage
from backend.services.chat import ChatService
from backend.services.llm import llm_service


def _make_result(title: str, snippet: str) -> dict[str, str]:
    return {
        "title": title,
        "url": f"https://example.com/{title}",
        "snippet": snippet,
    }


def test_web_result_selection_scales_with_question_complexity():
    results = [
        _make_result("应急预案指南", "应急预案的编制、执行与检查要求。"),
        _make_result("培训要求清单", "培训要求和考核标准说明。"),
        _make_result("检查清单", "检查清单与复盘要点。"),
        _make_result("事故案例汇总", "事故案例分析与复盘。"),
        _make_result("适用场景说明", "适用场景和边界条件。"),
        _make_result("无关内容", "与问题无关的内容。"),
    ]

    simple = ChatService._select_web_results("应急预案是什么", results)
    complex_results = ChatService._select_web_results(
        "请对比应急预案、培训要求、检查清单和事故案例的区别、优缺点、适用场景，并分别列出要求和案例。",
        results,
    )

    assert len(simple) == 5
    assert len(complex_results) == 6
    assert simple[0]["title"] == "应急预案指南"
    assert complex_results[0]["title"] == "应急预案指南"


def test_web_result_format_keeps_continuous_numbering():
    results = [
        _make_result("应急预案指南", "应急预案的编制、执行与检查要求。"),
        _make_result("培训要求清单", "培训要求和考核标准说明。"),
        _make_result("检查清单", "检查清单与复盘要点。"),
    ]

    formatted = ChatService._format_web_results(results)

    assert "### 结果1:" in formatted
    assert "### 结果2:" in formatted
    assert "### 结果3:" in formatted


@pytest.mark.asyncio
async def test_web_search_retries_with_simplified_query_when_first_attempt_is_challenge(monkeypatch):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            return None

    async def fake_get(self, url, params=None):
        query = (params or {}).get("q", "")
        calls.append(query)
        if len(calls) == 1:
            return FakeResponse(202, "<html><body>challenge</body></html>")
        return FakeResponse(
            200,
            """
            <div class="result">
              <a class="result__a" href="https://example.com/legal">安全生产法第77条</a>
              <a class="result__snippet">第77条内容摘要。</a>
            </div>
            """,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    results = await ChatService._web_search("请问：安全生产法第77条是什么内容？")

    assert calls == ["请问：安全生产法第77条是什么内容？", "安全生产法第77条是什么内容"]
    assert len(results) == 1
    assert results[0]["title"] == "安全生产法第77条"
    assert results[0]["snippet"] == "第77条内容摘要。"


@pytest.mark.asyncio
async def test_build_web_results_ignores_history_context(monkeypatch):
    captured: list[str] = []

    async def fake_web_search(question: str, max_results: int = ChatService._WEB_SEARCH_MAX_CANDIDATES):
        captured.append(question)
        return [
            {
                "title": "安全生产法第77条",
                "url": "https://example.com/legal",
                "snippet": "第77条内容摘要。",
            }
        ]

    monkeypatch.setattr(ChatService, "_web_search", fake_web_search)

    history_messages = [
        {"role": "user", "content": "请帮我写一份安全生产法培训提纲，重点讲事故隐患排查治理。"},
        {"role": "assistant", "content": "好的。"},
        {"role": "user", "content": "另外，安全生产法第77条是什么内容？"},
    ]

    results = await ChatService._build_web_results("安全生产法第77条是什么内容？", history_messages)

    assert captured == ["安全生产法第77条是什么内容？"]
    assert len(results) == 1
    assert results[0]["title"] == "安全生产法第77条"


@pytest.mark.asyncio
async def test_ask_sync_uses_web_results_in_prompt(monkeypatch):
    captured_queries: list[str] = []
    captured_messages: list[list[dict[str, str]]] = []

    async def fake_web_search(question: str, max_results: int = ChatService._WEB_SEARCH_MAX_CANDIDATES):
        captured_queries.append(question)
        return [
            {
                "title": "中华人民共和国安全生产法",
                "url": "https://example.com/legal",
                "snippet": "第一百一十九条 本法自2002年11月1日起施行。",
            }
        ]

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        captured_messages.append(messages)
        yield {"type": "chunk", "content": "联网回答。"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(ChatService, "_web_search", fake_web_search)
    monkeypatch.setattr(llm_service, "chat_events", fake_chat_events)

    result = await ChatService.ask_sync(
        "安全生产法第77条是什么内容？",
        [],
        messages=[
            ChatMessage(role="user", content="请先说明安全生产法的修订背景。", timestamp="2026-05-14T17:18:00"),
            ChatMessage(role="assistant", content="好的。", timestamp="2026-05-14T17:18:01"),
        ],
        model_id="deepseek-v4-flash",
        use_web_search=True,
    )

    assert result == "联网回答。"
    assert captured_queries == ["安全生产法第77条是什么内容？"]
    assert captured_messages
    assert "## 联网检索结果" in captured_messages[0][-1]["content"]
    assert "中华人民共和国安全生产法" in captured_messages[0][-1]["content"]
