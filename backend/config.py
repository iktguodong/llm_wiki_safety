"""
配置管理模块
管理全局配置、模型配置、知识库路径等
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 配置目录
CONFIG_DIR = Path.home() / ".anniu"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 知识库根目录
KB_ROOT = Path(__file__).parent.parent / "knowledge-bases"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# 默认配置
DEFAULT_CONFIG = {
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
                    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "type": "chat"}
                ]
            }
        ],
        "model_roles": {
            "doc_parse": "deepseek-v4-flash",
            "qa_chat": "deepseek-v4-flash",
            "ppt_gen": "deepseek-v4-pro"
        }
    },
    "knowledge_bases": {},
    "ui": {
        "theme": "light",
        "sidebar_collapsed": False,
        "last_opened_page": "chat"
    }
}


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """加载配置"""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置"""
    ensure_config_dir()
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
