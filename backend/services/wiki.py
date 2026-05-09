"""
Wiki生成服务
调用LLM解析文档，生成结构化Wiki页面
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import (
    get_kb_wiki_path, get_kb_index_path, get_kb_log_path,
    get_kb_doc_track_path, get_kb_meta_path
)
from backend.services.llm import llm_service


# 加载AGENTS.md工作流规范
_AGENTS_MD_PATH = Path(__file__).parent.parent / "prompts" / "AGENTS.md"
_AGENTS_INSTRUCTION = ""
if _AGENTS_MD_PATH.exists():
    with open(_AGENTS_MD_PATH, "r", encoding="utf-8") as f:
        _AGENTS_INSTRUCTION = f.read()

# 文档解析Prompt
DOC_PARSE_PROMPT = """你是一个专业知识库助手。请阅读以下文档内容，并按照LLM Wiki规范生成结构化知识页面。

## 要求

1. **创建文档摘要页面**
   - 文件名以文档名命名（小写+连字符）
   - 包含：Summary、Sources、Last updated
   - 提炼文档的核心内容和结构

2. **创建概念页面**
   - 为文档中的每个核心概念/主题创建独立页面
   - 页面名使用小写+连字符（如：port-fire-emergency）
   - 使用[[wiki-links]]链接到相关概念

3. **更新索引文件**
   - 更新wiki/index.md，添加新页面到对应分类
   - 包含页面名称和一行描述

4. **更新操作日志**
   - 在wiki/log.md追加本次操作记录

## 输出格式

请返回一个JSON数组，每个元素包含：
```json
[
  {
    "file": "wiki/page-name.md",
    "content": "# Page Title\n\n**Summary**: ...\n\n---\n\n正文内容..."
  }
]
```

## 文档内容

{document_content}
"""


class WikiService:
    """Wiki生成服务"""
    
    @staticmethod
    def _extract_text_from_pdf(file_path: Path) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
            text = ""
            with fitz.open(file_path) as doc:
                for page in doc:
                    text += page.get_text() + "\n\n"
            return text
        except Exception as e:
            return f"[PDF解析错误: {str(e)}]"
    
    @staticmethod
    def _extract_text_from_docx(file_path: Path) -> str:
        """从Word提取文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
        except Exception as e:
            return f"[Word解析错误: {str(e)}]"
    
    @staticmethod
    def _extract_text_from_markdown(file_path: Path) -> str:
        """从Markdown读取文本"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[Markdown读取错误: {str(e)}]"
    
    @staticmethod
    async def extract_text(file_path: Path) -> str:
        """提取文档文本内容"""
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return WikiService._extract_text_from_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            return WikiService._extract_text_from_docx(file_path)
        elif suffix in [".md", ".markdown"]:
            return WikiService._extract_text_from_markdown(file_path)
        else:
            return f"[不支持的文件格式: {suffix}]"
    
    @staticmethod
    async def parse_document(kb_id: str, doc_id: str, model_id: Optional[str] = None):
        """
        解析文档生成Wiki页面
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            model_id: 使用的模型ID
        """
        from backend.services.document import doc_service
        
        # 更新状态为解析中
        await doc_service.update_parse_status(kb_id, doc_id, "parsing")
        
        # 获取文档信息
        track_path = get_kb_doc_track_path(kb_id)
        with open(track_path, "r", encoding="utf-8") as f:
            track = json.load(f)
        
        doc_info = track["documents"].get(doc_id)
        if not doc_info:
            await doc_service.update_parse_status(kb_id, doc_id, "failed")
            return
        
        # 提取文本
        raw_path = Path(get_kb_doc_track_path(kb_id)).parent
        file_path = raw_path / doc_info["file"]
        
        if not file_path.exists():
            await doc_service.update_parse_status(kb_id, doc_id, "failed")
            return
        
        text = await WikiService.extract_text(file_path)
        
        if text.startswith("[") and text.endswith("]"):
            # 解析错误
            await doc_service.update_parse_status(kb_id, doc_id, "failed")
            return
        
        # 构建Prompt
        prompt = DOC_PARSE_PROMPT.format(document_content=text[:15000])  # 限制长度
        
        # 使用AGENTS.md作为system prompt
        system_content = "你是一个专业的知识库助手，擅长将文档转化为结构化的Wiki知识页面。"
        if _AGENTS_INSTRUCTION:
            system_content += "\n\n## 工作流规范\n\n" + _AGENTS_INSTRUCTION
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # 调用LLM生成Wiki
            response = await llm_service.chat_sync(messages, model_id=model_id, temperature=0.3)
            
            # 解析JSON响应
            # 提取JSON部分
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                wiki_files = json.loads(json_match.group())
            else:
                # 如果无法解析JSON，创建简单的摘要页面
                wiki_files = [{
                    "file": f"wiki/{doc_info['file'].split('.')[0]}-summary.md",
                    "content": f"# {doc_info['file']}\n\n**Summary**: 文档摘要\n\n**Sources**: {doc_info['file']}\n\n**Last updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n{text[:5000]}"
                }]
            
            # 保存Wiki文件
            wiki_path = get_kb_wiki_path(kb_id)
            wiki_path.mkdir(parents=True, exist_ok=True)
            
            wiki_page_names = []
            for wiki_file in wiki_files:
                file_name = wiki_file["file"].replace("wiki/", "")
                file_path = wiki_path / file_name
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(wiki_file["content"])
                
                wiki_page_names.append(file_name)
            
            # 更新索引
            await WikiService._update_index(kb_id, wiki_files, doc_info["file"])
            
            # 更新日志
            await WikiService._update_log(kb_id, doc_info["file"], wiki_page_names)
            
            # 更新文档状态
            await doc_service.update_parse_status(
                kb_id, doc_id, "completed",
                wiki_pages=wiki_page_names,
                page_count=len(wiki_page_names)
            )
            
        except Exception as e:
            await doc_service.update_parse_status(kb_id, doc_id, "failed")
            raise e
    
    @staticmethod
    async def _update_index(kb_id: str, wiki_files: List[Dict], source_file: str):
        """更新知识库索引"""
        index_path = get_kb_index_path(kb_id)
        
        # 读取现有索引
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = f"# 知识库索引\n\n**Last updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n## 源文档\n\n| 页面 | 描述 |\n|------|------|\n\n## 概念页面\n\n| 页面 | 描述 |\n|------|------|\n"
        
        # 添加新页面到索引
        for wiki_file in wiki_files:
            file_name = wiki_file["file"].replace("wiki/", "").replace(".md", "")
            title_match = re.search(r'^# (.+)$', wiki_file["content"], re.MULTILINE)
            title = title_match.group(1) if title_match else file_name
            
            # 检查是否已在索引中
            if f"[[{file_name}]]" not in content:
                # 添加到概念页面
                concept_section = "## 概念页面"
                if concept_section in content:
                    lines = content.split("\n")
                    insert_idx = -1
                    for i, line in enumerate(lines):
                        if concept_section in line:
                            insert_idx = i + 2  # 跳过表头
                            break
                    
                    if insert_idx > 0:
                        lines.insert(insert_idx, f"| [[{file_name}]] | {title} |")
                        content = "\n".join(lines)
        
        # 更新Last updated
        content = re.sub(
            r'\*\*Last updated\*\*: \d{4}-\d{2}-\d{2}',
            f"**Last updated**: {datetime.now().strftime('%Y-%m-%d')}",
            content
        )
        
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    @staticmethod
    async def _update_log(kb_id: str, source_file: str, wiki_pages: List[str]):
        """更新操作日志"""
        log_path = get_kb_log_path(kb_id)
        
        log_entry = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n- 解析文档「{source_file}」\n- 生成 {len(wiki_pages)} 个Wiki页面:\n"
        for page in wiki_pages:
            log_entry += f"  - [[{page.replace('.md', '')}]]\n"
        
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# 知识库操作日志\n"
        
        content += log_entry
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    @staticmethod
    async def list_wiki_pages(kb_id: str) -> List[Dict]:
        """列出知识库的所有Wiki页面"""
        wiki_path = get_kb_wiki_path(kb_id)
        if not wiki_path.exists():
            return []
        
        pages = []
        for file_path in wiki_path.glob("*.md"):
            if file_path.name in ["index.md", "log.md"]:
                continue
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 提取标题和摘要
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else file_path.stem
            
            summary_match = re.search(r'\*\*Summary\*\*: (.+)', content)
            summary = summary_match.group(1) if summary_match else ""
            
            # 提取Sources
            sources = []
            sources_match = re.search(r'\*\*Sources\*\*: (.+)', content)
            if sources_match:
                sources = [s.strip() for s in sources_match.group(1).split(",")]
            
            # 提取Last updated
            updated_match = re.search(r'\*\*Last updated\*\*: (\d{4}-\d{2}-\d{2})', content)
            last_updated = updated_match.group(1) if updated_match else ""
            
            pages.append({
                "name": file_path.stem,
                "title": title,
                "summary": summary,
                "last_updated": last_updated,
                "sources": sources
            })
        
        return sorted(pages, key=lambda x: x["name"])
    
    @staticmethod
    async def get_wiki_page(kb_id: str, page_name: str) -> Optional[Dict]:
        """获取Wiki页面内容"""
        wiki_path = get_kb_wiki_path(kb_id)
        file_path = wiki_path / f"{page_name}.md"
        
        if not file_path.exists():
            return None
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else page_name
        
        summary_match = re.search(r'\*\*Summary\*\*: (.+)', content)
        summary = summary_match.group(1) if summary_match else ""
        
        sources_match = re.search(r'\*\*Sources\*\*: (.+)', content)
        sources = []
        if sources_match:
            sources = [s.strip() for s in sources_match.group(1).split(",")]
        
        updated_match = re.search(r'\*\*Last updated\*\*: (\d{4}-\d{2}-\d{2})', content)
        last_updated = updated_match.group(1) if updated_match else ""
        
        return {
            "name": page_name,
            "title": title,
            "summary": summary,
            "last_updated": last_updated,
            "sources": sources,
            "content": content
        }


# 服务实例
wiki_service = WikiService()
