"""
Wiki生成服务
调用LLM解析文档，生成结构化Wiki页面
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import (
    get_kb_wiki_path, get_kb_index_path, get_kb_log_path,
    get_kb_doc_track_path
)
from backend.services.llm import llm_service
from backend.services.text_extraction import extract_document_text


logger = logging.getLogger(__name__)


# 加载AGENTS.md工作流规范
_AGENTS_MD_PATH = Path(__file__).parent.parent / "prompts" / "AGENTS.md"
_AGENTS_INSTRUCTION = ""
if _AGENTS_MD_PATH.exists():
    with open(_AGENTS_MD_PATH, "r", encoding="utf-8") as f:
        _AGENTS_INSTRUCTION = f.read()

    # 保留写作与结构规范，但移除全局输出契约，避免它和不同阶段的 prompt 互相冲突。
    _AGENTS_INSTRUCTION = re.sub(
        r"\n## Output contract\n[\s\S]*?(?=\n## )",
        "\n",
        _AGENTS_INSTRUCTION,
        count=1,
    ).strip()

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

CHUNK_ANALYSIS_PROMPT = """你正在处理一份长文档的一个分块。请只基于当前分块提取结构化知识，不要臆测分块外的内容。

## 目标

1. 提炼当前分块的核心主题和关键事实。
2. 识别适合独立成页的概念、流程、角色、阈值、规则或风险。
3. 为每个候选页面给出稳定的英文小写连字符 slug。
4. 候选页面只保留当前分块真正支持的内容。

## 输出要求

请只返回 JSON 对象，不要返回额外解释，不要使用 markdown 代码块。

```json
{{
  "chunk_summary": "当前分块的简短总结",
  "key_points": ["关键点1", "关键点2"],
  "candidate_pages": [
    {{
      "slug": "company-law-overview",
      "title": "公司法概览",
      "page_type": "concept",
      "importance": 1,
      "summary": "该页应回答什么问题",
      "key_facts": ["事实1", "事实2"],
      "evidence": ["能够支撑这些结论的原文短句"],
      "related_pages": ["必须是同一次输出 candidate_pages 数组里其它项的 slug；如果不存在合适的对应 slug，留空数组，不要凭空编造"]
    }}
  ]
}}
```

## 文档信息

- 文档名：{doc_name}
- 分块编号：{chunk_index}/{chunk_total}

## 当前分块内容

{chunk_content}
"""

PAGE_RENDER_PROMPT = """你正在把结构化资料写成适合知识库检索与问答的 Markdown 页面。

## 写作要求

1. 只输出完整 Markdown，不要输出 JSON，不要输出解释。
2. 页面必须以 `# {page_title}` 开头。
3. 必须包含元数据三行，且严格按下列格式（同一行内、英文冒号、冒号后留一个空格）：

   ```
   **Summary**: 一句话描述本页内容
   **Sources**: 原始文档名（多个用英文逗号分隔）
   **Last updated**: YYYY-MM-DD
   ```

   - 禁止写成「`**Summary**` 单独一行、内容写在下一行」的两行形式。
   - 禁止将元数据写成 `## Sources` / `## Last updated` 之类的二级标题章节，必须用上面的 `**标签**: 内容` 同行格式。
   - `**Last updated**` 必须是 YYYY-MM-DD 形式的日期。如果源文档中没有明确的更新日期，请使用今天的日期 {today} 填入，不要写“未提供”、“未明确”、“无”等文字。
4. 内容要忠实于给定资料，不要补充未给出的事实、阈值、流程、职责或法律结论。
5. 如果资料不足，明确写出“不足以从当前文档直接确认”的表述，而不是编造。
6. 如果是概览页，优先组织成“核心内容 / 主要主题 / 相关概念”。
7. 如果是概念页，优先组织成“定义 / 适用范围 / 关键规则 / 相关页面”。

## Wiki 链接（[[xxx]]）的强制规则

为避免「断链」（指向不存在的页面），请严格遵守：

- **只能在文末专门的 `## 相关页面` 段落里使用** `[[xxx]]` 链接。
- **链接的 slug 必须来自下方「可用资料」中 `related_pages` 数组**；如果该数组为空或不存在，则**整段不写** `## 相关页面`，也不出现任何 `[[xxx]]`。
- 严禁在正文段落、标题、表格、列表里出现 `[[xxx]]`，即使 xxx 是自然提到的概念也不行——直接用普通文字。
- 严禁凭印象编造 slug（例如 `principal-liability`、`government-safety-supervision`）；只能照抄 `related_pages` 里已经存在的字符串。

## 引用规则（Citation）

- 重要事实建议在句末用 `（来源：原文档名）` 标注，文档名取「关联源文件」的值。
- 不要伪造来源、不要把法规条款写成确切数值，除非「可用资料」里直接给出。

## 页面计划

- 页面类型：{page_type}
- 页面 slug：{page_slug}
- 关联源文件：{source_file}

## 可用资料

{page_context}
"""

MAX_CHUNK_CHARS = 7000
MAX_PARALLEL_LLM_CALLS = 3
MAX_CONCEPT_PAGES = 8


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
    def _extract_json_object(response_text: str):
        """从模型回复中提取 JSON 对象。"""
        if not response_text:
            return None

        cleaned = response_text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        start = cleaned.find("{")
        if start == -1:
            return None

        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            return None

        return value if isinstance(value, dict) else None

    @staticmethod
    def _slugify_page_name(value: str, fallback: str = "page") -> str:
        """将标题或 slug 规范化为适合文件名的形式。"""
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        slug = re.sub(r"-{2,}", "-", slug)
        return slug or fallback

    @staticmethod
    def _split_document_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
        """按自然段和标题边界切分长文档。"""
        normalized = re.sub(r"\r\n?", "\n", text).strip()
        if not normalized:
            return []
        if len(normalized) <= max_chars:
            return [normalized]

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        def flush_current():
            nonlocal current, current_len
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0

        for paragraph in paragraphs:
            heading_like = bool(
                re.match(r"^(#{1,6}\s+|第[一二三四五六七八九十百千0-9]+[章节条款编卷部分]?|[一二三四五六七八九十]+、)", paragraph)
            )

            if len(paragraph) > max_chars:
                flush_current()
                lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
                line_buffer: List[str] = []
                line_len = 0
                for line in lines:
                    line_size = len(line)
                    if line_buffer and line_len + line_size + 1 > max_chars:
                        chunks.append("\n".join(line_buffer).strip())
                        line_buffer = [line]
                        line_len = line_size
                    else:
                        line_buffer.append(line)
                        line_len += line_size + (1 if line_buffer else 0)
                if line_buffer:
                    chunks.append("\n".join(line_buffer).strip())
                continue

            if current and (current_len + len(paragraph) + 2 > max_chars or (heading_like and current_len > max_chars * 0.35)):
                flush_current()

            current.append(paragraph)
            current_len += len(paragraph) + 2

        flush_current()

        merged: List[str] = []
        for chunk in chunks:
            if not chunk:
                continue
            if merged and len(chunk) < max_chars * 0.2 and len(merged[-1]) + len(chunk) + 2 <= max_chars:
                merged[-1] = merged[-1] + "\n\n" + chunk
            else:
                merged.append(chunk)

        return merged

    @staticmethod
    def _build_system_content() -> str:
        """组装 system prompt。"""
        system_content = "你是一个专业的知识库助手，擅长将文档转化为结构化的Wiki知识页面。"
        if _AGENTS_INSTRUCTION:
            system_content += "\n\n## 工作流规范\n\n" + _AGENTS_INSTRUCTION
        return system_content

    @staticmethod
    def _merge_chunk_cards(chunk_cards: List[Dict], source_file: str):
        """把多个分块的抽取结果合并成页面计划。"""
        merged: Dict[str, Dict] = {}
        doc_summary_notes: List[str] = []
        doc_key_points: List[str] = []

        for card in chunk_cards:
            if not isinstance(card, dict):
                continue

            chunk_summary = str(card.get("chunk_summary", "")).strip()
            if chunk_summary:
                doc_summary_notes.append(chunk_summary)

            for key_point in card.get("key_points", []) or []:
                if isinstance(key_point, str) and key_point.strip():
                    doc_key_points.append(key_point.strip())

            for candidate in card.get("candidate_pages", []) or []:
                if not isinstance(candidate, dict):
                    continue

                raw_title = str(candidate.get("title") or candidate.get("slug") or "").strip()
                raw_slug = str(candidate.get("slug") or raw_title).strip()
                page_slug = WikiService._slugify_page_name(raw_slug, fallback="page")
                if not page_slug:
                    continue

                importance = candidate.get("importance", 1)
                try:
                    importance_value = int(importance)
                except (TypeError, ValueError):
                    importance_value = 1

                page_entry = merged.setdefault(page_slug, {
                    "slug": page_slug,
                    "title": raw_title or page_slug,
                    "page_type": str(candidate.get("page_type") or "concept"),
                    "importance": 0,
                    "occurrences": 0,
                    "summary_notes": [],
                    "key_facts": [],
                    "evidence": [],
                    "related_pages": set(),
                })

                if raw_title and page_entry["title"] == page_slug:
                    page_entry["title"] = raw_title
                if candidate.get("page_type"):
                    page_entry["page_type"] = str(candidate.get("page_type"))

                page_entry["importance"] = max(page_entry["importance"], importance_value)
                page_entry["occurrences"] += 1

                summary = str(candidate.get("summary", "")).strip()
                if summary:
                    page_entry["summary_notes"].append(summary)

                for fact in candidate.get("key_facts", []) or []:
                    if isinstance(fact, str) and fact.strip():
                        page_entry["key_facts"].append(fact.strip())

                for evidence in candidate.get("evidence", []) or []:
                    if isinstance(evidence, str) and evidence.strip():
                        page_entry["evidence"].append(evidence.strip())

                for related in candidate.get("related_pages", []) or []:
                    if isinstance(related, str) and related.strip():
                        page_entry["related_pages"].add(WikiService._slugify_page_name(related.strip()))

        def score(item: Dict) -> float:
            return float(item["importance"]) * 2.0 + float(item["occurrences"]) + min(len(item["evidence"]), 12) * 0.2

        ranked = sorted(merged.values(), key=score, reverse=True)
        selected = ranked[:MAX_CONCEPT_PAGES]

        summary_plan = {
            "slug": f"{Path(source_file).stem}-summary",
            "title": Path(source_file).stem,
            "page_type": "summary",
            "chunk_summaries": doc_summary_notes,
            "key_points": doc_key_points,
        }

        return summary_plan, selected

    @staticmethod
    def _fallback_markdown_page(page_title: str, source_file: str, summary_text: str, body_lines: List[str]) -> str:
        """生成保底 Markdown 页面。"""
        lines = [
            f"# {page_title}",
            "",
            f"**Summary**: {summary_text}",
            "",
            f"**Sources**: {source_file}",
            "",
            f"**Last updated**: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
        ]
        lines.extend(body_lines)
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    async def _extract_chunk_card(
        *,
        system_content: str,
        doc_name: str,
        chunk_text: str,
        chunk_index: int,
        chunk_total: int,
        model_id: str,
    ) -> Dict:
        """对单个文档分块做结构化抽取。"""
        prompt = CHUNK_ANALYSIS_PROMPT.format(
            doc_name=doc_name,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_content=chunk_text,
        )
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        response = await llm_service.chat_sync(messages, model_id=model_id, temperature=0.2)
        if not response.strip():
            return {}
        card = WikiService._extract_json_object(response)
        if not card:
            card_list = WikiService._extract_json_array(response)
            if card_list and isinstance(card_list[0], dict):
                return card_list[0]
            return {}
        return card

    @staticmethod
    async def _render_page_markdown(
        *,
        system_content: str,
        page_plan: Dict,
        source_file: str,
        model_id: str,
    ) -> str:
        """根据页面计划渲染最终 Markdown。"""
        page_context = {
            "title": page_plan.get("title"),
            "slug": page_plan.get("slug"),
            "page_type": page_plan.get("page_type"),
            "summary_notes": page_plan.get("summary_notes", []),
            "key_facts": page_plan.get("key_facts", []),
            "evidence": page_plan.get("evidence", []),
            "related_pages": sorted(page_plan.get("related_pages", [])),
            "importance": page_plan.get("importance", 1),
            "occurrences": page_plan.get("occurrences", 1),
        }
        prompt = PAGE_RENDER_PROMPT.format(
            page_title=page_plan.get("title") or page_plan.get("slug"),
            page_type=page_plan.get("page_type", "concept"),
            page_slug=page_plan.get("slug"),
            source_file=source_file,
            page_context=json.dumps(page_context, ensure_ascii=False, indent=2),
            today=datetime.now().strftime('%Y-%m-%d'),
        )
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        response = await llm_service.chat_sync(messages, model_id=model_id, temperature=0.25)
        cleaned = response.strip()
        fence_match = re.search(r"```(?:markdown|md)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return cleaned

    @staticmethod
    def _is_reserved_page(file_name: str) -> bool:
        """判断是否为保留文件，避免覆盖 wiki/index.md 和 wiki/log.md。"""
        normalized = file_name.replace("wiki/", "")
        stem = Path(normalized).stem
        return stem in {"index", "log"}
    
    @staticmethod
    async def extract_text(file_path: Path) -> str:
        """提取文档文本内容"""
        return extract_document_text(file_path)
    
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

        started_at = time.perf_counter()

        async def fail_parse(error: str):
            await doc_service.update_parse_status(kb_id, doc_id, "failed", error_message=error[:500])
            logger.warning(
                "document parse failed",
                extra={
                    "event": "document_parse",
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "model_id": target_model_id if "target_model_id" in locals() else model_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "failed",
                    "error": error[:160],
                },
            )

        try:
            # 前置检查：优先使用文档解析角色，其次回退到当前模型。
            model_roles = config.get("models", {}).get("model_roles", {})
            target_model_id = model_id or model_roles.get("doc_parse") or config.get("current_model_id")
            logger.info(
                "document parse started",
                extra={
                    "event": "document_parse",
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "model_id": target_model_id,
                    "status": "started",
                },
            )
            providers = config.get("models", {}).get("providers", [])
            provider_of_model = None
            for p in providers:
                if any(m.get("id") == target_model_id for m in p.get("models", [])):
                    provider_of_model = p
                    break
            if not provider_of_model:
                await fail_parse(f"未找到模型 {target_model_id} 的服务商配置")
                return
            if not provider_of_model.get("api_key"):
                await fail_parse(f"服务商 {provider_of_model.get('name', provider_of_model.get('id'))} 的 API Key 未配置")
                return

            # 更新状态为解析中
            await doc_service.update_parse_status(kb_id, doc_id, "parsing")

            # 获取文档信息
            track_path = get_kb_doc_track_path(kb_id)
            with open(track_path, "r", encoding="utf-8") as f:
                track = json.load(f)

            doc_info = track.get("documents", {}).get(doc_id)
            if not doc_info:
                await fail_parse("文档信息不存在")
                return

            # 提取文本
            raw_path = Path(get_kb_doc_track_path(kb_id)).parent
            file_path = raw_path / doc_info["file"]

            if not file_path.exists():
                await fail_parse(f"文件不存在：{doc_info['file']}")
                return

            text = await WikiService.extract_text(file_path)

            if not text.strip():
                await fail_parse("文档未提取到可读文本，请确认文件内容不是空白")
                return

            if text.startswith("[") and text.endswith("]") and len(text) < 200:
                # 提取错误（形如 [PDF解析错误: ...]）
                await fail_parse(text.strip("[]"))
                return

            system_content = WikiService._build_system_content()
            chunks = WikiService._split_document_into_chunks(text)
            if not chunks:
                chunks = [text]

            import asyncio

            semaphore = asyncio.Semaphore(MAX_PARALLEL_LLM_CALLS)

            async def limited(coro):
                async with semaphore:
                    return await coro

            chunk_tasks = [
                limited(
                    WikiService._extract_chunk_card(
                        system_content=system_content,
                        doc_name=doc_info["file"],
                        chunk_text=chunk,
                        chunk_index=index + 1,
                        chunk_total=len(chunks),
                        model_id=target_model_id,
                    )
                )
                for index, chunk in enumerate(chunks)
            ]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            chunk_cards: List[Dict] = []
            for result in chunk_results:
                if isinstance(result, Exception):
                    continue
                if isinstance(result, dict) and result:
                    chunk_cards.append(result)

            summary_plan, concept_plans = WikiService._merge_chunk_cards(chunk_cards, doc_info["file"])
            if not summary_plan.get("chunk_summaries"):
                source_excerpt = text[:2000].strip()
                summary_plan["chunk_summaries"] = [source_excerpt] if source_excerpt else [
                    "当前文档未提取到可读摘要，请检查源文档或模型输出"
                ]
            summary_plan["source_excerpt"] = text[:2000].strip()
            page_plans = [summary_plan] + concept_plans

            if not page_plans:
                page_plans = [{
                    "slug": f"{Path(doc_info['file']).stem}-summary",
                    "title": Path(doc_info["file"]).stem,
                    "page_type": "summary",
                    "chunk_summaries": [text[:2000]],
                    "key_points": [],
                }]

            page_tasks = [
                limited(
                    WikiService._render_page_markdown(
                        system_content=system_content,
                        page_plan=page_plan,
                        source_file=doc_info["file"],
                        model_id=target_model_id,
                    )
                )
                for page_plan in page_plans
            ]
            rendered_pages = await asyncio.gather(*page_tasks, return_exceptions=True)

            filtered_wiki_files = []
            for page_plan, rendered in zip(page_plans, rendered_pages):
                page_slug = WikiService._slugify_page_name(str(page_plan.get("slug") or page_plan.get("title") or "page"))
                if not page_slug or WikiService._is_reserved_page(page_slug):
                    continue

                content = ""
                if isinstance(rendered, str):
                    content = rendered.strip()
                # 判定 LLM 返回内容是否为“错误/不完整”：
                # 1) 为空；
                # 2) 以任意一个友好错误提示前缀开头（与 llm.py 的 _format_request_exception / _format_missing_* 保持一致）；
                # 3) 内容完全没有 markdown 标题（`# `），实际上几乎只能是错误文本。
                _llm_error_prefixes = (
                    "API错误", "请求错误", "错误：",
                    "无法连接到模型服务", "连接模型服务",
                    "通过代理访问模型服务", "调用模型服务",
                    "未配置模型服务", "未为模型服务",
                )
                _is_llm_error_text = (
                    not content
                    or content.startswith(_llm_error_prefixes)
                    or not re.search(r'^#\s', content, re.MULTILINE)
                )
                if _is_llm_error_text:
                    page_title = str(page_plan.get("title") or page_slug)
                    page_type = str(page_plan.get("page_type") or "concept")
                    if page_type == "summary":
                        summary_text = "；".join(page_plan.get("chunk_summaries", [])[:3]) or "文档摘要"
                        body_lines = ["## 核心内容", ""]
                        summary_notes = [note for note in page_plan.get("chunk_summaries", [])[:5] if note]
                        if summary_notes:
                            for note in summary_notes:
                                body_lines.append(f"- {note}")
                        else:
                            source_excerpt = str(page_plan.get("source_excerpt") or "").strip()
                            if source_excerpt:
                                body_lines.append(f"- {source_excerpt}")
                            else:
                                body_lines.append("- 当前模型未抽取到可用摘要，请检查源文档或模型输出")
                        if page_plan.get("key_points"):
                            body_lines.extend(["", "## 关键要点", ""])
                            for point in page_plan.get("key_points", [])[:10]:
                                body_lines.append(f"- {point}")
                    else:
                        summary_text = "；".join(page_plan.get("summary_notes", [])[:2]) or "概念页面"
                        body_lines = []
                        if page_plan.get("key_facts"):
                            body_lines.extend(["## 关键事实", ""])
                            for fact in page_plan.get("key_facts", [])[:12]:
                                body_lines.append(f"- {fact}")
                        if page_plan.get("evidence"):
                            body_lines.extend(["", "## 依据片段", ""])
                            for evidence in page_plan.get("evidence", [])[:8]:
                                body_lines.append(f"- {evidence}")
                        if page_plan.get("related_pages"):
                            body_lines.extend(["", "## 相关页面", ""])
                            for related in sorted(page_plan.get("related_pages", []))[:8]:
                                body_lines.append(f"- [[{related}]]")

                    content = WikiService._fallback_markdown_page(
                        page_title=page_title,
                        source_file=doc_info["file"],
                        summary_text=summary_text,
                        body_lines=body_lines or ["正文内容"],
                    )

                filtered_wiki_files.append({
                    "file": f"wiki/{page_slug}.md",
                    "content": content,
                })

            if not filtered_wiki_files:
                filtered_wiki_files = [{
                    "file": f"wiki/{Path(doc_info['file']).stem}-summary.md",
                    "content": WikiService._fallback_markdown_page(
                        page_title=Path(doc_info["file"]).stem,
                        source_file=doc_info["file"],
                        summary_text="文档摘要",
                        body_lines=["正文内容"],
                    )
                }]

            # 兑底清洗：即使提示词不生效，也要把路过 [[xxx]] 中指向本次实际生成页面之外的 slug
            # 降级为普通文本，避免在 lint 里报“断链”。只保留合法 slug 的 [[xxx]] 原样。
            # 合法 slug = 本文档本次生成的 slug 集合 ⋃ 知识库里已有的其它 wiki 页面 slug。
            valid_slugs = {
                Path(wiki_file["file"]).stem
                for wiki_file in filtered_wiki_files
            }
            try:
                existing_wiki_dir = get_kb_wiki_path(kb_id)
                if existing_wiki_dir.exists():
                    for existing in existing_wiki_dir.glob("*.md"):
                        if existing.name in ("index.md", "log.md"):
                            continue
                        valid_slugs.add(existing.stem)
            except Exception:
                pass

            def _strip_invalid_wiki_links(text: str) -> str:
                def _replace(match: re.Match) -> str:
                    inner = match.group(1)
                    target = inner.split("|")[0].strip()
                    alias = inner.split("|", 1)[1].strip() if "|" in inner else target
                    if target in valid_slugs:
                        return match.group(0)
                    return alias
                return re.sub(r"\[\[([^\[\]]+)\]\]", _replace, text)

            for wiki_file in filtered_wiki_files:
                wiki_file["content"] = _strip_invalid_wiki_links(wiki_file["content"])
            
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
            logger.info(
                "document parse completed",
                extra={
                    "event": "document_parse",
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "model_id": target_model_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "completed",
                    "page_count": len(wiki_page_names),
                },
            )
            
        except Exception as e:
            await fail_parse(str(e))
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
            
            # 元数据兼容三种写法：1) `**Summary**: 内容`（同行带冒号）；
            # 2) `**Summary**` 后换行再写内容（markdown 段落标题写法）；
            # 3) `## Summary`（二级标题 + 下一行内容或 `- 内容`）。
            summary_match = re.search(r'(?:\*\*Summary\*\*|##\s+Summary)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content)
            summary = summary_match.group(1).strip() if summary_match else ""
            
            # 提取Sources
            sources = []
            sources_match = re.search(r'(?:\*\*Sources\*\*|##\s+Sources)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content)
            if sources_match:
                sources = [s.strip() for s in sources_match.group(1).split(",")]
            
            # 提取Last updated
            updated_match = re.search(r'(?:\*\*Last updated\*\*|##\s+Last updated)\s*[:：]?\s*\n?\s*[-*]?\s*(\d{4}-\d{2}-\d{2})', content)
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
        
        # 元数据兼容「同行带冒号」/「换行段落」/「`## 标题` 二级标题」三种写法
        summary_match = re.search(r'(?:\*\*Summary\*\*|##\s+Summary)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content)
        summary = summary_match.group(1).strip() if summary_match else ""
        
        sources_match = re.search(r'(?:\*\*Sources\*\*|##\s+Sources)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content)
        sources = []
        if sources_match:
            sources = [s.strip() for s in sources_match.group(1).split(",")]
        
        updated_match = re.search(r'(?:\*\*Last updated\*\*|##\s+Last updated)\s*[:：]?\s*\n?\s*[-*]?\s*(\d{4}-\d{2}-\d{2})', content)
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
            # 兼容三种写法：1) `**Summary**: 内容`；2) `**Summary**` 后换行再写内容；
            # 3) `## Summary` 二级标题 + 下一行内容（或 `- 内容`）。只要标签存在且后面能取到非空内容就视为合格。
            if not re.search(r'(?:\*\*Summary\*\*|##\s+Summary)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content):
                issues.append({
                    "type": "format",
                    "severity": "warning",
                    "page": page_name,
                    "message": "页面缺少 Summary 元数据",
                    "suggestion": "在页面顶部添加 '**Summary**: 一句话描述'"
                })
            
            if not re.search(r'(?:\*\*Sources\*\*|##\s+Sources)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)', content):
                issues.append({
                    "type": "missing_source",
                    "severity": "info",
                    "page": page_name,
                    "message": "页面未标注来源文档",
                    "suggestion": "添加 '**Sources**: 原始文档名.pdf'"
                })
            
            # Last updated：先看标签是否存在（不论 `**` 还是 `## ` 写法），再看是否能取出 YYYY-MM-DD 日期。
            _has_last_updated_label = re.search(r'(?:\*\*Last updated\*\*|##\s+Last updated)', content)
            _has_last_updated_date = re.search(r'(?:\*\*Last updated\*\*|##\s+Last updated)\s*[:：]?\s*\n?\s*[-*]?\s*(\d{4}-\d{2}-\d{2})', content)
            if not _has_last_updated_label:
                issues.append({
                    "type": "format",
                    "severity": "warning",
                    "page": page_name,
                    "message": "页面缺少 Last updated 元数据",
                    "suggestion": "添加 '**Last updated**: YYYY-MM-DD'"
                })
            elif not _has_last_updated_date:
                # 标签存在但内容不是日期，降级为提示
                issues.append({
                    "type": "format",
                    "severity": "info",
                    "page": page_name,
                    "message": "Last updated 未填日期或格式不规范",
                    "suggestion": "将 Last updated 内容改为 YYYY-MM-DD 格式"
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
