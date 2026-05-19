from __future__ import annotations

import json

import backend.config as config_module


def test_load_config_appends_default_silicon_provider(monkeypatch, tmp_path):
    config_dir = tmp_path / ".anniu"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "app_name": "安牛",
                "current_kb_id": None,
                "current_model_id": "deepseek-v4-flash",
                "models": {
                    "providers": [
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
                    "model_roles": {
                        "doc_parse": "deepseek-v4-flash",
                        "qa_chat": "deepseek-v4-flash",
                        "ppt_gen": "deepseek-v4-flash",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_file)

    loaded = config_module.load_config()
    provider_ids = [provider["id"] for provider in loaded["models"]["providers"]]

    assert provider_ids == ["deepseek", "silicon", "bailian"]
    assert loaded["models"]["providers"][1]["name"] == "SiliconFlow"
    assert loaded["models"]["providers"][1]["base_url"] == "https://api.siliconflow.cn/v1"
    assert [model["id"] for model in loaded["models"]["providers"][1]["models"]] == [
        "MiniMaxAI/MiniMax-M2.5",
        "deepseek-ai/DeepSeek-V4-Flash",
        "deepseek-ai/DeepSeek-V4-Pro",
        "moonshotai/Kimi-K2.5",
        "zai-org/GLM-5.1",
    ]
    assert loaded["models"]["providers"][2]["name"] == "阿里云百炼"
    assert loaded["models"]["providers"][2]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_load_config_does_not_overwrite_existing_provider_models(monkeypatch, tmp_path):
    config_dir = tmp_path / ".anniu"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "app_name": "安牛",
                "current_kb_id": None,
                "current_model_id": "deepseek-v4-flash",
                "models": {
                    "providers": [
                        {
                            "id": "silicon",
                            "name": "My Silicon",
                            "base_url": "https://custom.invalid",
                            "api_key": "",
                            "models": [
                                {"id": "custom-model", "name": "Custom Model", "type": "chat"},
                            ],
                        }
                    ],
                    "model_roles": {
                        "doc_parse": "deepseek-v4-flash",
                        "qa_chat": "deepseek-v4-flash",
                        "ppt_gen": "deepseek-v4-flash",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_file)

    loaded = config_module.load_config()
    silicon = next(provider for provider in loaded["models"]["providers"] if provider["id"] == "silicon")

    assert silicon["name"] == "My Silicon"
    assert silicon["base_url"] == "https://custom.invalid"
    assert [model["id"] for model in silicon["models"]] == ["custom-model"]
