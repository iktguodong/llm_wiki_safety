"""
知识库管理服务
实现知识库的CRUD、文档管理、Wiki页面管理
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import (
    get_kb_path, get_kb_meta_path, get_kb_raw_path,
    get_kb_wiki_path, get_kb_index_path, get_kb_log_path,
    get_kb_doc_track_path, KB_ROOT, config, save_config
)
from backend.models import KnowledgeBase, KnowledgeBaseCreate


def generate_kb_id(name: str) -> str:
    """生成知识库ID"""
    prefix = "kb-" + datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{suffix}"


def get_kb_meta(kb_id: str) -> Optional[Dict]:
    """读取知识库元信息"""
    meta_path = get_kb_meta_path(kb_id)
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_kb_meta(kb_id: str, meta: Dict):
    """保存知识库元信息"""
    meta_path = get_kb_meta_path(kb_id)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def init_kb_directories(kb_id: str):
    """初始化知识库目录结构"""
    get_kb_raw_path(kb_id).mkdir(parents=True, exist_ok=True)
    get_kb_wiki_path(kb_id).mkdir(parents=True, exist_ok=True)


def init_kb_index(kb_id: str, name: str):
    """初始化知识库索引文件"""
    index_path = get_kb_index_path(kb_id)
    index_content = f"""# {name} 知识库索引

**Last updated**: {datetime.now().strftime('%Y-%m-%d')}

---

## 源文档

| 页面 | 描述 |
|------|------|

## 概念页面

| 页面 | 描述 |
|------|------|

## 相关页面

"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_content)


def init_kb_log(kb_id: str, name: str):
    """初始化知识库日志文件"""
    log_path = get_kb_log_path(kb_id)
    log_content = f"""# {name} 知识库操作日志

## {datetime.now().strftime('%Y-%m-%d')}

- 创建知识库「{name}」
"""
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)


def init_doc_track(kb_id: str):
    """初始化文档追踪文件"""
    track_path = get_kb_doc_track_path(kb_id)
    with open(track_path, "w", encoding="utf-8") as f:
        json.dump({"documents": {}}, f, ensure_ascii=False, indent=2)


def get_kb_size(kb_id: str) -> float:
    """计算知识库占用空间（MB）"""
    kb_path = get_kb_path(kb_id)
    if not kb_path.exists():
        return 0.0
    
    total_size = 0
    for path in kb_path.rglob("*"):
        if path.is_file():
            total_size += path.stat().st_size
    
    return round(total_size / (1024 * 1024), 2)


def count_wiki_pages(kb_id: str) -> int:
    """统计Wiki页面数量"""
    wiki_path = get_kb_wiki_path(kb_id)
    if not wiki_path.exists():
        return 0
    return len([f for f in wiki_path.glob("*.md") if f.name not in ["index.md", "log.md"]])


def count_documents(kb_id: str) -> int:
    """统计文档数量"""
    raw_path = get_kb_raw_path(kb_id)
    if not raw_path.exists():
        return 0
    return len([f for f in raw_path.iterdir() if f.is_file() and not f.name.endswith(".json")])


class KnowledgeBaseService:
    """知识库服务"""
    
    @staticmethod
    async def create(data: KnowledgeBaseCreate) -> KnowledgeBase:
        """创建知识库"""
        kb_id = generate_kb_id(data.name)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 初始化目录
        init_kb_directories(kb_id)
        
        # 创建元信息
        meta = {
            "id": kb_id,
            "name": data.name,
            "description": data.description or "",
            "created_at": now,
            "updated_at": now,
            "statistics": {
                "document_count": 0,
                "wiki_page_count": 0,
                "total_size_mb": 0.0
            },
            "documents": {},
            "settings": {
                "auto_parse_on_upload": True,
                "wiki_link_style": "double-bracket"
            }
        }
        save_kb_meta(kb_id, meta)
        
        # 初始化索引和日志
        init_kb_index(kb_id, data.name)
        init_kb_log(kb_id, data.name)
        init_doc_track(kb_id)
        
        # 更新全局配置
        config["knowledge_bases"][kb_id] = {
            "path": str(get_kb_path(kb_id)),
            "name": data.name
        }
        save_config(config)
        
        return KnowledgeBase(
            id=kb_id,
            name=data.name,
            description=data.description or "",
            created_at=now,
            updated_at=now,
            document_count=0,
            wiki_page_count=0,
            total_size_mb=0.0
        )
    
    @staticmethod
    async def list_all() -> List[KnowledgeBase]:
        """列出所有知识库"""
        result = []
        if not KB_ROOT.exists():
            return result
        
        for kb_dir in KB_ROOT.iterdir():
            if kb_dir.is_dir():
                meta = get_kb_meta(kb_dir.name)
                if meta:
                    result.append(KnowledgeBase(
                        id=meta["id"],
                        name=meta["name"],
                        description=meta.get("description", ""),
                        created_at=meta["created_at"],
                        updated_at=meta["updated_at"],
                        document_count=count_documents(kb_dir.name),
                        wiki_page_count=count_wiki_pages(kb_dir.name),
                        total_size_mb=get_kb_size(kb_dir.name)
                    ))
        
        return sorted(result, key=lambda x: x.created_at, reverse=True)
    
    @staticmethod
    async def get(kb_id: str) -> Optional[KnowledgeBase]:
        """获取单个知识库"""
        meta = get_kb_meta(kb_id)
        if not meta:
            return None
        
        return KnowledgeBase(
            id=meta["id"],
            name=meta["name"],
            description=meta.get("description", ""),
            created_at=meta["created_at"],
            updated_at=meta["updated_at"],
            document_count=count_documents(kb_id),
            wiki_page_count=count_wiki_pages(kb_id),
            total_size_mb=get_kb_size(kb_id)
        )
    
    @staticmethod
    async def delete(kb_id: str) -> bool:
        """删除知识库"""
        kb_path = get_kb_path(kb_id)
        if not kb_path.exists():
            return False
        
        # 删除目录
        shutil.rmtree(kb_path)
        
        # 更新全局配置
        if kb_id in config.get("knowledge_bases", {}):
            del config["knowledge_bases"][kb_id]
            save_config(config)
        
        return True
    
    @staticmethod
    async def update_stats(kb_id: str):
        """更新知识库统计信息"""
        meta = get_kb_meta(kb_id)
        if meta:
            meta["statistics"]["document_count"] = count_documents(kb_id)
            meta["statistics"]["wiki_page_count"] = count_wiki_pages(kb_id)
            meta["statistics"]["total_size_mb"] = get_kb_size(kb_id)
            meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_kb_meta(kb_id, meta)


# 服务实例
kb_service = KnowledgeBaseService()
