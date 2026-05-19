"""
配置管理模块
管理全局配置、模型配置、知识库路径等
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 配置目录
CONFIG_DIR = Path.home() / ".anniu"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 知识库根目录
KB_ROOT = Path(__file__).parent.parent / "knowledge-bases"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

DEFAULT_MODEL_ID = "deepseek-v4-flash"


# 默认配置
DEFAULT_CONFIG = {
    "version": "1.0.0",
    "app_name": "安牛",
    "current_kb_id": None,
    "current_model_id": DEFAULT_MODEL_ID,
    "models": {
        "providers": [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "api_key": "",
                "models": [
                    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "type": "chat"}
                ]
            },
            {
                "id": "silicon",
                "name": "SiliconFlow",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "",
                "models": [
                    {"id": "MiniMaxAI/MiniMax-M2.5", "name": "MiniMax M2.5", "type": "chat"},
                    {"id": "deepseek-ai/DeepSeek-V4-Flash", "name": "DeepSeek V4 Flash", "type": "chat"},
                    {"id": "deepseek-ai/DeepSeek-V4-Pro", "name": "DeepSeek V4 Pro", "type": "chat"},
                    {"id": "moonshotai/Kimi-K2.5", "name": "Kimi K2.5", "type": "chat"},
                    {"id": "zai-org/GLM-5.1", "name": "GLM 5.1", "type": "chat"}
                ]
            },
            {
                "id": "bailian",
                "name": "阿里云百炼",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "",
                "models": [
                    {"id": "qwen-plus", "name": "Qwen Plus", "type": "chat"},
                    {"id": "qwen-max", "name": "Qwen Max", "type": "chat"},
                    {"id": "qwen-turbo", "name": "Qwen Turbo", "type": "chat"}
                ]
            }
        ],
        "model_roles": {
            "doc_parse": DEFAULT_MODEL_ID,
            "qa_chat": DEFAULT_MODEL_ID,
            "ppt_gen": DEFAULT_MODEL_ID
        }
    },
    "knowledge_bases": {},
    "ui": {
        "theme": "light",
        "sidebar_collapsed": False,
        "last_opened_page": "chat"
    }
}


def _ensure_default_model_providers(config: dict) -> bool:
    """确保三个默认模型服务商存在，避免老配置缺少新预设。"""
    changed = False
    models = config.setdefault("models", {})
    providers = models.setdefault("providers", [])

    if not isinstance(providers, list):
        models["providers"] = deepcopy(DEFAULT_CONFIG["models"]["providers"])
        providers = models["providers"]
        changed = True

    existing_ids = {provider.get("id") for provider in providers if isinstance(provider, dict)}
    for default_provider in DEFAULT_CONFIG["models"]["providers"]:
        if default_provider["id"] not in existing_ids:
            providers.append(deepcopy(default_provider))
            changed = True

    default_providers = {provider["id"]: provider for provider in DEFAULT_CONFIG["models"]["providers"]}
    allowed_ids = set(default_providers)
    provider_by_id = {
        provider.get("id"): provider
        for provider in providers
        if isinstance(provider, dict) and provider.get("id") in allowed_ids
    }
    ordered_providers = [
        provider_by_id[default_provider["id"]]
        for default_provider in DEFAULT_CONFIG["models"]["providers"]
        if default_provider["id"] in provider_by_id
    ]
    if ordered_providers != providers:
        models["providers"] = ordered_providers
        providers = ordered_providers
        changed = True

    for provider in providers:
        default_provider = default_providers.get(provider.get("id"))
        if not default_provider:
            continue
        if not provider.get("name"):
            provider["name"] = default_provider["name"]
            changed = True
        if not provider.get("base_url"):
            provider["base_url"] = default_provider["base_url"]
            changed = True
        if not provider.get("models"):
            provider["models"] = deepcopy(default_provider["models"])
            changed = True

    return changed


def normalize_default_model_selection(config: dict) -> bool:
    """把全局默认和功能默认模型固定为 DeepSeek V4 Flash。"""
    changed = _ensure_default_model_providers(config)
    models = config.setdefault("models", {})
    normalized_roles = {
        "doc_parse": DEFAULT_MODEL_ID,
        "qa_chat": DEFAULT_MODEL_ID,
        "ppt_gen": DEFAULT_MODEL_ID,
    }
    if models.get("model_roles") != normalized_roles:
        models["model_roles"] = normalized_roles
        changed = True

    if config.get("current_model_id") != DEFAULT_MODEL_ID:
        config["current_model_id"] = DEFAULT_MODEL_ID
        changed = True

    return changed


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """加载配置"""
    ensure_config_dir()
    config = deepcopy(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for key, value in loaded.items():
            if key == "models" and isinstance(value, dict):
                models = config.setdefault("models", {})
                for model_key, model_value in value.items():
                    if model_key == "providers":
                        models["providers"] = model_value
                    else:
                        models[model_key] = model_value
            else:
                config[key] = value

    if normalize_default_model_selection(config):
        save_config(config)

    return config


def save_config(config: dict):
    """保存配置"""
    ensure_config_dir()
    normalize_default_model_selection(config)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_kb_path(kb_id: str) -> Path:
    """获取知识库路径"""
    return KB_ROOT / kb_id


def get_kb_meta_path(kb_id: str) -> Path:
    """获取知识库元信息文件路径"""
    return get_kb_path(kb_id) / "meta.json"


def get_kb_raw_path(kb_id: str) -> Path:
    """获取知识库raw目录路径"""
    return get_kb_path(kb_id) / "raw"


def get_kb_wiki_path(kb_id: str) -> Path:
    """获取知识库wiki目录路径"""
    return get_kb_path(kb_id) / "wiki"


def get_kb_index_path(kb_id: str) -> Path:
    """获取知识库索引文件路径"""
    return get_kb_wiki_path(kb_id) / "index.md"


def get_kb_log_path(kb_id: str) -> Path:
    """获取知识库日志文件路径"""
    return get_kb_wiki_path(kb_id) / "log.md"


def get_kb_doc_track_path(kb_id: str) -> Path:
    """获取知识库文档追踪文件路径"""
    return get_kb_raw_path(kb_id) / "文档追踪.json"


# 初始化配置
config = load_config()
