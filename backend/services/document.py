"""
文档管理服务
实现文档上传、解析、删除、追踪
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import (
    get_kb_raw_path, get_kb_wiki_path, get_kb_doc_track_path,
    get_kb_meta_path
)
from backend.models import DocumentInfo, DocumentDeletePreview


class DocumentService:
    """文档服务"""
    
    @staticmethod
    def _load_doc_track(kb_id: str) -> Dict:
        """加载文档追踪信息"""
        track_path = get_kb_doc_track_path(kb_id)
        if track_path.exists():
            with open(track_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"documents": {}}
    
    @staticmethod
    def _save_doc_track(kb_id: str, track: Dict):
        """保存文档追踪信息"""
        track_path = get_kb_doc_track_path(kb_id)
        with open(track_path, "w", encoding="utf-8") as f:
            json.dump(track, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _load_kb_meta(kb_id: str) -> Optional[Dict]:
        """加载知识库元信息"""
        meta_path = get_kb_meta_path(kb_id)
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    @staticmethod
    def _save_kb_meta(kb_id: str, meta: Dict):
        """保存知识库元信息"""
        meta_path = get_kb_meta_path(kb_id)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _get_file_size_mb(file_path: Path) -> float:
        """获取文件大小（MB）"""
        return round(file_path.stat().st_size / (1024 * 1024), 2)
    
    @staticmethod
    def _generate_doc_id() -> str:
        """生成文档ID"""
        return f"doc-{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    async def upload(kb_id: str, file_name: str, file_content: bytes) -> DocumentInfo:
        """
        上传文档
        
        Args:
            kb_id: 知识库ID
            file_name: 文件名
            file_content: 文件内容（bytes）
        
        Returns:
            文档信息
        """
        raw_path = get_kb_raw_path(kb_id)
        raw_path.mkdir(parents=True, exist_ok=True)
        
        # 生成文档ID
        doc_id = DocumentService._generate_doc_id()
        
        # 保存文件
        file_path = raw_path / file_name
        # 如果文件已存在，添加序号
        counter = 1
        original_name = file_path.stem
        while file_path.exists():
            file_path = raw_path / f"{original_name}_{counter}{file_path.suffix}"
            counter += 1
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 更新追踪信息
        track = DocumentService._load_doc_track(kb_id)
        track["documents"][doc_id] = {
            "file": file_path.name,
            "original_name": file_name,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_size_mb": DocumentService._get_file_size_mb(file_path),
            "page_count": 0,  # 解析后更新
            "wiki_pages": [],
            "parse_status": "pending"
        }
        DocumentService._save_doc_track(kb_id, track)
        
        # 更新知识库元信息
        meta = DocumentService._load_kb_meta(kb_id)
        if meta:
            meta["documents"][doc_id] = track["documents"][doc_id]
            meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            DocumentService._save_kb_meta(kb_id, meta)
        
        doc_info = track["documents"][doc_id]
        return DocumentInfo(
            id=doc_id,
            file=doc_info["file"],
            uploaded_at=doc_info["uploaded_at"],
            file_size_mb=doc_info["file_size_mb"],
            page_count=doc_info["page_count"],
            wiki_pages=doc_info["wiki_pages"],
            parse_status=doc_info["parse_status"],
            error_message=doc_info.get("error_message"),
        )
    
    @staticmethod
    async def list_documents(kb_id: str) -> List[DocumentInfo]:
        """列出知识库中的所有文档"""
        track = DocumentService._load_doc_track(kb_id)
        result = []
        
        for doc_id, doc_info in track.get("documents", {}).items():
            result.append(DocumentInfo(
                id=doc_id,
                file=doc_info["file"],
                uploaded_at=doc_info["uploaded_at"],
                file_size_mb=doc_info["file_size_mb"],
                page_count=doc_info.get("page_count", 0),
                wiki_pages=doc_info.get("wiki_pages", []),
                parse_status=doc_info.get("parse_status", "pending"),
                error_message=doc_info.get("error_message"),
            ))
        
        return sorted(result, key=lambda x: x.uploaded_at, reverse=True)
    
    @staticmethod
    async def get_delete_preview(kb_id: str, doc_id: str) -> Optional[DocumentDeletePreview]:
        """
        获取删除文档预览信息
        
        Returns:
            删除预览信息，包含关联的Wiki页面和引用情况
        """
        track = DocumentService._load_doc_track(kb_id)
        doc_info = track.get("documents", {}).get(doc_id)
        
        if not doc_info:
            return None
        
        # 检查Wiki页面是否被其他文档引用
        wiki_pages = doc_info.get("wiki_pages", [])
        referenced_pages = []
        
        # 扫描其他文档的引用
        for other_doc_id, other_doc in track.get("documents", {}).items():
            if other_doc_id != doc_id:
                for wiki_page in other_doc.get("wiki_pages", []):
                    if wiki_page in wiki_pages:
                        referenced_pages.append(wiki_page)
        
        return DocumentDeletePreview(
            doc_id=doc_id,
            file=doc_info["file"],
            wiki_pages_count=len(wiki_pages),
            referenced_pages=list(set(referenced_pages)),
            options=["仅删除文档", "删除文档及所有关联Wiki页面"] if wiki_pages else ["删除文档"]
        )
    
    @staticmethod
    async def delete(kb_id: str, doc_id: str, delete_wiki_pages: bool = False) -> bool:
        """
        删除文档
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            delete_wiki_pages: 是否同时删除关联的Wiki页面
        
        Returns:
            是否成功
        """
        track = DocumentService._load_doc_track(kb_id)
        doc_info = track.get("documents", {}).get(doc_id)
        
        if not doc_info:
            return False
        
        # 删除文件
        raw_path = get_kb_raw_path(kb_id)
        file_path = raw_path / doc_info["file"]
        if file_path.exists():
            file_path.unlink()
        
        # 删除关联的Wiki页面
        if delete_wiki_pages:
            wiki_path = get_kb_wiki_path(kb_id)
            for wiki_page in doc_info.get("wiki_pages", []):
                wiki_file = wiki_path / wiki_page
                if wiki_file.exists():
                    wiki_file.unlink()
        
        # 更新追踪信息
        del track["documents"][doc_id]
        DocumentService._save_doc_track(kb_id, track)
        
        # 更新知识库元信息
        meta = DocumentService._load_kb_meta(kb_id)
        if meta and doc_id in meta.get("documents", {}):
            del meta["documents"][doc_id]
            meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            DocumentService._save_kb_meta(kb_id, meta)
        
        return True
    
    @staticmethod
    async def update_parse_status(kb_id: str, doc_id: str, status: str, wiki_pages: List[str] = None, page_count: int = None, error_message: Optional[str] = None):
        """更新文档解析状态"""
        track = DocumentService._load_doc_track(kb_id)
        if doc_id in track.get("documents", {}):
            track["documents"][doc_id]["parse_status"] = status
            if wiki_pages:
                track["documents"][doc_id]["wiki_pages"] = wiki_pages
            if page_count:
                track["documents"][doc_id]["page_count"] = page_count
            if error_message is not None:
                track["documents"][doc_id]["error_message"] = error_message
            elif status == "parsing" or status == "completed":
                # 成功或重新开始解析时清理之前的错误
                track["documents"][doc_id].pop("error_message", None)
            DocumentService._save_doc_track(kb_id, track)
            
            # 同步更新元信息
            meta = DocumentService._load_kb_meta(kb_id)
            if meta and doc_id in meta.get("documents", {}):
                meta["documents"][doc_id] = track["documents"][doc_id]
                DocumentService._save_kb_meta(kb_id, meta)


# 服务实例
doc_service = DocumentService()
