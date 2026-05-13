from __future__ import annotations

import pytest

import backend.config as config_module
from backend.services.llm import llm_service


@pytest.fixture()
def deepseek_without_api_key(monkeypatch):
    monkeypatch.setitem(config_module.config, "current_model_id", "deepseek-v4-flash")
    monkeypatch.setitem(
        config_module.config["models"],
        "providers",
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key": "",
                "models": [
                    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "type": "chat"},
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
            "ppt_gen": "deepseek-v4-pro",
        },
    )


@pytest.mark.asyncio
async def test_chat_sync_returns_clear_message_when_api_key_missing(deepseek_without_api_key, monkeypatch):
    async def fail_post(*args, **kwargs):
        raise AssertionError("chat request should not be sent when API key is missing")

    monkeypatch.setattr(llm_service.client, "post", fail_post)

    result = await llm_service.chat_sync([{"role": "user", "content": "你好"}], model_id="deepseek-v4-flash")

    assert "API Key 未配置" in result
    assert "Bearer" not in result


@pytest.mark.asyncio
async def test_validate_returns_clear_message_when_api_key_missing(deepseek_without_api_key, monkeypatch):
    async def fail_get(*args, **kwargs):
        raise AssertionError("model validation request should not be sent when API key is missing")

    monkeypatch.setattr(llm_service.client, "get", fail_get)

    result = await llm_service.validate("deepseek", "", "https://api.deepseek.com")

    assert result == {
        "valid": False,
        "message": "API Key 为空，请先在「设置」页填写后再测试连接。",
        "available_models": [],
    }
