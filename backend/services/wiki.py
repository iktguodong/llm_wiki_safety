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
  {{
    "file": "wiki/page-name.md",
    "content": "# Page Title\\n\\n**Summary**: ...\\n\\n---\\n\\n正文内容..."
  }}
]
```

## 文档内容

{document_content}
"""


class WikiService:
    """Wiki生成服务"""

    @staticmethod
    def _extract_json_array(response_text: str):
        """从模型回复中提取 JSON 数组。"""
        if not response_text:
            return None

        cleaned = response_text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        start = cleaned.find("[")
        if start == -1:
            return None

        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            return None

        return value if isinstance(value, list) else None

    @staticmethod
    def _is_reserved_page(file_name: str) -> bool:
        """判断是否为保留文件，避免覆盖 wiki/index.md 和 wiki/log.md。"""
        normalized = file_name.replace("wiki/", "")
        stem = Path(normalized).stem
        return stem in {"index", "log"}
    
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
        from backend.config import config

        try:
            # 前置检查：优先使用文档解析角色，其次回退到当前模型。
            model_roles = config.get("models", {}).get("model_roles", {})
            target_model_id = model_id or model_roles.get("doc_parse") or config.get("current_model_id")
            providers = config.get("models", {}).get("providers", [])
            provider_of_model = None
            for p in providers:
                if any(m.get("id") == target_model_id for m in p.get("models", [])):
                    provider_of_model = p
                    break
            if not provider_of_model:
                await doc_service.update_parse_status(
                    kb_id, doc_id, "failed",
                    error_message=f"未找到模型 {target_model_id} 的服务商配置"
                )
                return
            if not provider_of_model.get("api_key"):
                await doc_service.update_parse_status(
                    kb_id, doc_id, "failed",
                    error_message=f"服务商 {provider_of_model.get('name', provider_of_model.get('id'))} 的 API Key 未配置，请在「设置」页填写 API Key 后重试。"
                )
                return

            # 更新状态为解析中
            await doc_service.update_parse_status(kb_id, doc_id, "parsing")

            # 获取文档信息
            track_path = get_kb_doc_track_path(kb_id)
            with open(track_path, "r", encoding="utf-8") as f:
                track = json.load(f)

            doc_info = track.get("documents", {}).get(doc_id)
            if not doc_info:
                await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message="文档信息不存在")
                return

            # 提取文本
            raw_path = Path(get_kb_doc_track_path(kb_id)).parent
            file_path = raw_path / doc_info["file"]

            if not file_path.exists():
                await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message=f"文件不存在：{doc_info['file']}")
                return

            text = await WikiService.extract_text(file_path)

            if text.startswith("[") and text.endswith("]") and len(text) < 200:
                # 提取错误（形如 [PDF解析错误: ...]）
                await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message=text.strip("[]"))
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

            # 调用LLM生成Wiki
            response = await llm_service.chat_sync(messages, model_id=target_model_id, temperature=0.3)

            # 如果 LLM 返回的是错误文本（形如 "API错误 (401): ..." 或 "请求错误: ..."）—— 直接失败
            if response and (response.startswith("API错误") or response.startswith("请求错误") or response.startswith("错误：")):
                await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message=response[:500])
                return

            if not response.strip():
                await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message="LLM 返回空响应，未生成 Wiki 内容")
                return
            
            # 解析JSON响应
            wiki_files = WikiService._extract_json_array(response)
            if wiki_files is None:
                # 如果无法解析JSON，创建简单的摘要页面
                wiki_files = [{
                    "file": f"wiki/{doc_info['file'].split('.')[0]}-summary.md",
                    "content": f"# {doc_info['file']}\n\n**Summary**: 文档摘要\n\n**Sources**: {doc_info['file']}\n\n**Last updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n{text[:5000]}"
                }]

            filtered_wiki_files = []
            for wiki_file in wiki_files:
                if not isinstance(wiki_file, dict):
                    continue
                file_name = str(wiki_file.get("file", "")).replace("wiki/", "")
                if not file_name or WikiService._is_reserved_page(file_name):
                    continue
                if not isinstance(wiki_file.get("content"), str) or not wiki_file["content"].strip():
                    continue
                filtered_wiki_files.append(wiki_file)

            if not filtered_wiki_files:
                filtered_wiki_files = [{
                    "file": f"wiki/{Path(doc_info['file']).stem}-summary.md",
                    "content": f"# {doc_info['file']}\n\n**Summary**: 文档摘要\n\n**Sources**: {doc_info['file']}\n\n**Last updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n{text[:5000]}"
                }]
            
            # 保存Wiki文件
            wiki_path = get_kb_wiki_path(kb_id)
            wiki_path.mkdir(parents=True, exist_ok=True)
            
            wiki_page_names = []
            for wiki_file in filtered_wiki_files:
                file_name = wiki_file["file"].replace("wiki/", "")
                file_path = wiki_path / file_name
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(wiki_file["content"])

                wiki_page_names.append(file_name)

            # 更新索引
            await WikiService._update_index(kb_id, filtered_wiki_files, doc_info["file"])
            
            # 更新日志
            await WikiService._update_log(kb_id, doc_info["file"], wiki_page_names)
            
            # 更新文档状态
            await doc_service.update_parse_status(
                kb_id, doc_id, "completed",
                wiki_pages=wiki_page_names,
                page_count=len(wiki_page_names)
            )
            
        except Exception as e:
            await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message=str(e)[:500])
            # 不再 raise，避免在 fire-and-forget 任务里形成未捕获异常警告
    
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

        def insert_row(section_name: str, row: str):
            nonlocal content
            marker = f"## {section_name}\n\n| 页面 | 描述 |\n|------|------|\n"
            if row in content:
                return
            if marker in content:
                content = content.replace(marker, marker + row + "\n", 1)
            else:
                content += f"\n## {section_name}\n\n| 页面 | 描述 |\n|------|------|\n{row}\n"

        source_base = Path(source_file).stem
        source_rows: List[str] = []
        concept_rows: List[str] = []

        for wiki_file in wiki_files:
            file_name = wiki_file["file"].replace("wiki/", "").replace(".md", "")
            title_match = re.search(r'^# (.+)$', wiki_file["content"], re.MULTILINE)
            title = title_match.group(1) if title_match else file_name

            row = f"| [[{file_name}]] | {title} |"
            if file_name == f"{source_base}-summary" or file_name.endswith("-summary"):
                source_rows.append(row)
            else:
                concept_rows.append(row)

        for row in source_rows:
            insert_row("源文档", row)

        for row in concept_rows:
            insert_row("概念页面", row)
        
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


    @staticmethod
    async def lint_wiki(kb_id: str) -> Dict:
        """
        检查Wiki知识库的质量问题
        
        检查项：
        1. 页面格式：是否包含必需的元数据（Summary, Sources, Last updated）
        2. 链接完整性：[[wiki-links]]指向的页面是否存在
        3. 孤儿页面：没有被其他页面引用的页面
        4. 来源缺失：没有标注Sources的页面
        5. 索引同步：index.md是否包含所有页面
        """
        wiki_path = get_kb_wiki_path(kb_id)
        if not wiki_path.exists():
            return {
                "total_pages": 0,
                "issues": [],
                "summary": "Wiki目录不存在"
            }
        
        issues = []
        all_pages = set()
        linked_pages = set()
        page_contents = {}
        
        # 收集所有页面
        for file_path in wiki_path.glob("*.md"):
            if file_path.name in ["index.md", "log.md"]:
                continue
            page_name = file_path.stem
            all_pages.add(page_name)
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            page_contents[page_name] = content
            
            # 检查页面格式
            if "**Summary**:" not in content:
                issues.append({
                    "type": "format",
                    "severity": "warning",
                    "page": page_name,
                    "message": "页面缺少 Summary 元数据",
                    "suggestion": "在页面顶部添加 '**Summary**: 一句话描述'"
                })
            
            if "**Sources**:" not in content:
                issues.append({
                    "type": "missing_source",
                    "severity": "info",
                    "page": page_name,
                    "message": "页面未标注来源文档",
                    "suggestion": "添加 '**Sources**: 原始文档名.pdf'"
                })
            
            if "**Last updated**:" not in content:
                issues.append({
                    "type": "format",
                    "severity": "warning",
                    "page": page_name,
                    "message": "页面缺少 Last updated 元数据",
                    "suggestion": "添加 '**Last updated**: YYYY-MM-DD'"
                })
            
            # 收集所有wiki-links
            wiki_links = re.findall(r'\[\[([^\]]+)\]\]', content)
            for link in wiki_links:
                # 去除可能的|别名
                linked_name = link.split("|")[0].strip()
                linked_pages.add(linked_name)
        
        # 检查孤儿页面（index.md中的链接不计入）
        index_path = get_kb_index_path(kb_id)
        index_links = set()
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                index_content = f.read()
            index_links = set(re.findall(r'\[\[([^\]]+)\]\]', index_content))
            index_links = {link.split("|")[0].strip() for link in index_links}
        
        for page in all_pages:
            # 排除自身引用和index引用
            inbound = {p for p in linked_pages if p == page}
            # 检查是否有其他页面引用此页面
            has_inbound = False
            for other_page, content in page_contents.items():
                if other_page == page:
                    continue
                links = re.findall(r'\[\[([^\]]+)\]\]', content)
                for link in links:
                    if link.split("|")[0].strip() == page:
                        has_inbound = True
                        break
                if has_inbound:
                    break
            
            if not has_inbound and page not in index_links:
                issues.append({
                    "type": "orphan",
                    "severity": "info",
                    "page": page,
                    "message": "孤儿页面：未被任何页面或索引引用",
                    "suggestion": "在其他相关页面中添加 [[" + page + "]] 链接，或将其加入 index.md"
                })
        
        # 检查断链
        for linked in linked_pages:
            if linked not in all_pages and linked not in ["index", "log"]:
                issues.append({
                    "type": "link",
                    "severity": "error",
                    "page": "unknown",
                    "message": f"断链：[[{linked}]] 指向的页面不存在",
                    "suggestion": f"创建页面 {linked}.md 或修正链接"
                })
        
        # 生成摘要
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        info_count = sum(1 for i in issues if i["severity"] == "info")
        
        if not issues:
            summary = f"检查完成，共 {len(all_pages)} 个页面，未发现质量问题。"
        else:
            summary = f"检查完成，共 {len(all_pages)} 个页面，发现 {error_count} 个错误、{warning_count} 个警告、{info_count} 个提示。"
        
        return {
            "total_pages": len(all_pages),
            "issues": issues,
            "summary": summary
        }


# 服务实例
wiki_service = WikiService()
