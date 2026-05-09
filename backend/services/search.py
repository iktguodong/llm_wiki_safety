"""
原文检索服务
在原始文档中进行模糊搜索，返回高亮匹配片段
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import get_kb_raw_path
from backend.models import SearchRequest, SearchResult, SearchMatch


class SearchService:
    """检索服务"""
    
    @staticmethod
    def _extract_text_from_pdf(file_path: Path) -> List[Dict]:
        """从PDF提取按页分的文本"""
        try:
            import fitz
            pages = []
            with fitz.open(file_path) as doc:
                for i, page in enumerate(doc):
                    text = page.get_text()
                    if text.strip():
                        pages.append({
                            "page": i + 1,
                            "text": text
                        })
            return pages
        except Exception as e:
            return [{"page": 1, "text": f"[PDF解析错误: {str(e)}]"}]
    
    @staticmethod
    def _extract_text_from_docx(file_path: Path) -> List[Dict]:
        """从Word提取文本（按段落分）"""
        try:
            from docx import Document
            doc = Document(file_path)
            # 将所有段落合并为一个"页面"
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return [{"page": 1, "text": text}]
        except Exception as e:
            return [{"page": 1, "text": f"[Word解析错误: {str(e)}]"}]
    
    @staticmethod
    def _extract_text_from_markdown(file_path: Path) -> List[Dict]:
        """从Markdown读取文本"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return [{"page": 1, "text": text}]
        except Exception as e:
            return [{"page": 1, "text": f"[Markdown读取错误: {str(e)}]"}]
    
    @staticmethod
    def _get_document_pages(file_path: Path) -> List[Dict]:
        """获取文档的分页文本"""
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return SearchService._extract_text_from_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            return SearchService._extract_text_from_docx(file_path)
        elif suffix in [".md", ".markdown"]:
            return SearchService._extract_text_from_markdown(file_path)
        else:
            return [{"page": 1, "text": f"[不支持的格式: {suffix}]"}]
    
    @staticmethod
    def _fuzzy_search(text: str, keyword: str) -> List[Dict]:
        """
        模糊搜索
        
        策略：
        1. 先尝试精确匹配
        2. 如果没有，尝试分词匹配
        3. 返回匹配位置和上下文
        """
        matches = []
        
        # 精确匹配（不区分大小写）
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
    def _exact_search(text: str, keyword: str) -> List[Dict]:
        """精确匹配搜索"""
        matches = []
        
        # 完全精确匹配（区分大小写）
        pattern = re.compile(re.escape(keyword))
        
        for match in pattern.finditer(text):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            
            snippet = text[start:end]
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
    def _regex_search(text: str, pattern: str) -> List[Dict]:
        """正则表达式搜索"""
        matches = []
        
        try:
            regex = re.compile(pattern)
            
            for match in regex.finditer(text):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                
                snippet = text[start:end]
                highlight_start = match.start() - start
                highlight_end = highlight_start + len(match.group())
                
                matches.append({
                    "start": match.start(),
                    "end": match.end(),
                    "snippet": snippet,
                    "highlights": [(highlight_start, highlight_end)]
                })
        except re.error as e:
            matches.append({
                "start": 0,
                "end": 0,
                "snippet": f"[正则表达式错误: {str(e)}]",
                "highlights": []
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
        
        # 如果没有指定知识库，搜索所有知识库
        if not kb_ids:
            from backend.config import KB_ROOT
            if KB_ROOT.exists():
                kb_ids = [d.name for d in KB_ROOT.iterdir() if d.is_dir()]
        
        for kb_id in kb_ids:
            raw_path = get_kb_raw_path(kb_id)
            if not raw_path.exists():
                continue
            
            # 遍历所有文档
            for file_path in raw_path.iterdir():
                if not file_path.is_file() or file_path.suffix == ".json":
                    continue
                
                # 提取文档内容
                pages = SearchService._get_document_pages(file_path)
                
                for page in pages:
                    text = page["text"]
                    
                    # 根据模式搜索
                    if request.mode == "exact":
                        matches = SearchService._exact_search(text, request.keyword)
                    elif request.mode == "regex":
                        matches = SearchService._regex_search(text, request.keyword)
                    else:  # fuzzy
                        matches = SearchService._fuzzy_search(text, request.keyword)
                    
                    for match in matches:
                        total_matches += 1
                        
                        # 计算相关度（简单的词频统计）
                        keyword_lower = request.keyword.lower()
                        text_lower = text.lower()
                        count = text_lower.count(keyword_lower)
                        score = min(1.0, count * 0.1 + 0.5)  # 基础分0.5，每出现一次加0.1
                        
                        # 生成高亮位置索引
                        highlights = []
                        for hl in match.get("highlights", []):
                            highlights.extend(range(hl[0], hl[1]))
                        
                        results.append(SearchMatch(
                            file=file_path.name,
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
