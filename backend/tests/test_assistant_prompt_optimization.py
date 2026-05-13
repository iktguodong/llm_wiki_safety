from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
import backend.services.assistant_prompt as assistant_prompt_service


def test_optimize_prompt_calls_llm_and_strips_code_fence(monkeypatch):
    captured = {}

    async def fake_chat_sync(messages, model_id=None, temperature=0.7):
        captured["messages"] = messages
        captured["model_id"] = model_id
        captured["temperature"] = temperature
        return "```text\n你是一个翻译助手。\n请把输入内容翻译成英语。\n```"

    monkeypatch.setattr(assistant_prompt_service.llm_service, "chat_sync", fake_chat_sync)

    client = TestClient(app)
    response = client.post(
        "/api/assistants/optimize-prompt",
        json={
            "name": "翻译助手",
            "description": "很擅长中英文之间的翻译。",
            "system_prompt": "无论用户说什么，你都要把他说的内容翻译成英语。",
            "model_id": "deepseek-v4-flash",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["optimized_prompt"] == "你是一个翻译助手。\n请把输入内容翻译成英语。"
    assert captured["model_id"] == "deepseek-v4-flash"
    assert captured["temperature"] == 0.2
    assert "助手名称：翻译助手" in captured["messages"][1]["content"]
