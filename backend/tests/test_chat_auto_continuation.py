from __future__ import annotations

import pytest

from backend.services.chat import ChatService
from backend.services.llm import llm_service


@pytest.mark.asyncio
async def test_chat_service_auto_continues_when_stream_hits_length(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        calls.append(messages)

        if len(calls) == 1:
            assert stream is True
            assert max_tokens == ChatService._AUTO_CONTINUATION_MAX_TOKENS
            yield {"type": "chunk", "content": "第一部分，"}
            yield {"type": "chunk", "content": "尚未结束。"}
            yield {"type": "done", "finish_reason": "length"}
            return

        assert len(calls) == 2
        assert stream is True
        assert max_tokens == ChatService._AUTO_CONTINUATION_MAX_TOKENS
        assert messages[-2]["role"] == "assistant"
        assert messages[-2]["content"] == "第一部分，尚未结束。"
        assert messages[-1]["role"] == "user"
        assert "请从已输出内容的末尾继续回答" in messages[-1]["content"]
        assert "已输出末尾：第一部分，尚未结束。" in messages[-1]["content"]
        yield {"type": "chunk", "content": "第二部分，完成。"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(llm_service, "chat_events", fake_chat_events)

    result = await ChatService().ask_sync("请完整回答这个问题", [], model_id="deepseek-v4-flash")

    assert result == "第一部分，尚未结束。第二部分，完成。"
    assert len(calls) == 2
