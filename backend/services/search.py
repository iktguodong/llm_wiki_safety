"""
原文检索服务
在原始文档中进行模糊搜索，返回高亮匹配片段
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import get_kb_raw_path, get_kb_doc_track_path
from backend.models import SearchRequest, SearchResult, SearchMatch
from backend.services.text_extraction import extract_document_pages


class SearchService:
    """检索服务"""
    
    @staticmethod
    def _fuzzy_search(text: str, keyword: str) -> List[Dict]:
        """模糊搜索：按关键字子串匹配，返回上下文片段。"""
        matches = []
        
        # 不区分大小写的子串匹配
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
        for match in pattern.finditer(text):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            
            snippet = text[start:end]
            
            # 计算高亮位置（相对于片段）
            highlight_start = match.start() - start
            highlight_end = highlight_start + len(match.group())
            
            matches.append({
                "start": match.start(),
                "end": match.end(),
                "snippet": snippet,
                "highlights": [(highlight_start, highlight_end)]
            })
        
        return matches
    
    @staticmethod
    async def search(request: SearchRequest) -> SearchResult:
        """
        搜索文档
        
        Args:
            request: 搜索请求
        
        Returns:
            搜索结果
        """
        results = []
        total_matches = 0
        
        # 确定搜索范围
        kb_ids = request.knowledge_base_ids if request.knowledge_base_ids else []
        
        # 如果没有指定知识库，不执行跨库搜索，直接返回空结果
        if not kb_ids:
            return SearchResult(
                query=request.keyword,
                total_matches=0,
                results=[],
                results_grouped={}
            )
        
        for kb_id in kb_ids:
            raw_path = get_kb_raw_path(kb_id)
            if not raw_path.exists():
                continue
            
            # 构建文件名 → doc_id 映射
            file_to_doc = {}
            track_path = get_kb_doc_track_path(kb_id)
            if track_path.exists():
                with open(track_path, "r", encoding="utf-8") as f:
                    tracker = json.load(f)
                for doc_id, info in tracker.get("documents", {}).items():
                    file_to_doc[info.get("file", "")] = doc_id

            # 遍历所有文档
            for file_path in raw_path.iterdir():
                if not file_path.is_file() or file_path.suffix == ".json":
                    continue
                
                doc_id = file_to_doc.get(file_path.name, "")
                
                # 提取文档内容
                pages = extract_document_pages(file_path)
                
                for page in pages:
                    text = page["text"]
                    matches = SearchService._fuzzy_search(text, request.keyword)
                    
                    for match in matches:
                        total_matches += 1
                        
                        # 计算相关度：词频 + 标题/页首加权
                        keyword_lower = request.keyword.lower()
                        text_lower = text.lower()
                        count = text_lower.count(keyword_lower)
                        score = min(1.0, count * 0.08 + 0.45)
                        if request.keyword.lower() in file_path.stem.lower():
                            score = min(1.0, score + 0.12)
                        if page["page"] == 1:
                            score = min(1.0, score + 0.05)
                        
                        # 生成高亮位置索引
                        highlights = []
                        for hl in match.get("highlights", []):
                            highlights.extend(range(hl[0], hl[1]))
                        
                        results.append(SearchMatch(
                            file=file_path.name,
                            doc_id=doc_id,
                            kb_id=kb_id,
                            page=page["page"],
                            snippet=match["snippet"],
                            score=round(score, 2),
                            highlights=highlights
                        ))
        
        # 按相关度排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        # 构建分组结果
        results_grouped: dict = {}
        for result in results:
            kid = result.kb_id
            if kid not in results_grouped:
                results_grouped[kid] = []
            results_grouped[kid].append(result)
        
        return SearchResult(
            query=request.keyword,
            total_matches=total_matches,
            results=results,
            results_grouped=results_grouped
        )


# 服务实例
search_service = SearchService()
