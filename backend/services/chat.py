"""
知识问答服务
基于知识库Wiki页面回答问题
"""

import json
import html as html_lib
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from backend.config import get_kb_wiki_path, get_kb_index_path, get_kb_doc_track_path
from backend.models import ChatMessage
from backend.services.llm import llm_service
from backend.services.presentation.project_store import load_upload_metadata
from backend.services.text_extraction import extract_document_text


_QUESTION_STOPWORDS = {
    "什么", "怎么", "如何", "哪些", "是否", "是不是", "谁", "哪", "哪个", "哪种",
    "请问", "一下", "一个", "一些", "有关", "关于", "情况", "意思", "原因", "方法",
    "流程", "步骤", "规定", "要求", "内容", "范围", "时候", "怎样", "为何",
}


# 问答Prompt
QA_PROMPT = """你是一个专业的企业生产安全知识库问答助手。请基于以下wiki知识库内容回答用户问题。

## 可用知识

### wiki/index.md（知识库索引）
{index_content}

### 相关知识资料（内部检索片段，勿向用户复述本节结构或标识）
{related_pages}

## 回答要求

1. **准确性优先**
   - 答案必须基于提供的wiki知识
   - 如果知识中没有答案，明确说明"知识库中暂无相关信息"
   - 不要编造或推测

2. **资料来源在用户回答中的写法**
   - **不要**向用户展示 Wiki 自动拆分子页面用的**内部英文名/连字符 slug**、`.md` 文件名、文件路径、知识库 ID，也不要复述下方「资料片段」小节标题及其编号
   - **可以**使用各资料片段上方「对应上传资料」行中给出的名称（用户上传材料的显示名，如《安全生产法》或原始文件名）来说明依据；也可使用正文里本身的中文小节标题、条款或表格语境
   - **不要**在文末批量罗列内部技术标识或子页面英文名列表；不要使用 `[[页面名]]` 等 Wiki 链接语法
   - 若片段未标注上传资料名、且无需细究出处，用概括性表述即可（例如「根据知识库中的说明」）

3. **格式清晰**
   - 优先使用自然标题、编号步骤、项目符号和表格组织内容，减少直接暴露 Markdown 语法
   - 复杂流程使用步骤化描述
   - 适合对照的信息可以用表格，不适合表格时改成“字段：内容”的分点说明

4. **冲突处理**
   - 如果不同资料片段中的信息有冲突，明确指出
   - 分别概括不同说法或条款差异，仍遵守第 2 条：不向用户暴露 Wiki 子页面英文名/slug；需要区分来源时优先用「对应上传资料」名称或正文中的中文标题

## 用户问题

{question}
"""

WEB_QA_PROMPT = """你是一个专业的企业生产安全知识助手。请基于提供的联网检索结果和问题回答。

## 联网检索结果
{web_results}

## 回答要求

1. 优先使用检索结果中的信息，避免编造。
2. 如果检索结果不足以回答，请明确说明当前联网结果不足。
3. 语言要清晰、简洁、专业，优先用自然标题、编号和列表组织内容，少用装饰性符号。
4. 只能引用下方“联网检索结果”里真实存在的编号，编号数量可能少于或多于 3 条，禁止新增不存在的编号。
5. 如果引用了某个结果，请在结尾统一列出你实际使用的来源编号，并尽量使用 Markdown 超链接，例如“来源：[结果1](URL)、[结果3](URL)”。

## 用户问题

{question}
"""


class ChatService:
    """问答服务"""

    _WEB_SEARCH_MAX_CANDIDATES = 8
    _WEB_SEARCH_BASE_RESULTS = 5
    _AUTO_CONTINUATION_MAX_ATTEMPTS = 4
    _AUTO_CONTINUATION_TAIL_CHARS = 240
    _AUTO_CONTINUATION_MAX_TOKENS = 8192
    _AUTO_CONTINUATION_PROMPT = (
        "上面的回答因为长度限制而中断了。请从已输出内容的末尾继续回答，"
        "补完剩余内容，不要重复前文，只输出后续内容。"
    )
    _WEB_SEARCH_COMPLEXITY_MARKERS = (
        "以及",
        "同时",
        "另外",
        "此外",
        "并且",
        "或者",
        "还是",
        "分别",
        "对比",
        "比较",
        "区别",
        "汇总",
        "全面",
        "所有",
        "全部",
        "有哪些",
        "列出",
        "罗列",
        "清单",
        "多种",
        "多个",
    )

    def __init__(self, llm_client: Any = llm_service):
        self.llm_service = llm_client
    
    @staticmethod
    def _read_file(file_path: Path) -> str:
        """读取文件内容"""
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    @staticmethod
    def _build_question_terms(question: str) -> List[str]:
        """把问题拆成更适合检索的短语和 n-gram。"""
        terms = set()
        chunks = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9_-]{2,}', question.lower())

        for chunk in chunks:
            if chunk in _QUESTION_STOPWORDS:
                continue

            if re.fullmatch(r'[\u4e00-\u9fa5]+', chunk):
                terms.add(chunk)
                max_len = min(5, len(chunk))
                for size in range(2, max_len + 1):
                    for idx in range(0, len(chunk) - size + 1):
                        piece = chunk[idx:idx + size]
                        if piece not in _QUESTION_STOPWORDS:
                            terms.add(piece)
            else:
                terms.add(chunk)

        return sorted(terms, key=len, reverse=True)

    @staticmethod
    def _extract_page_title(content: str, fallback: str) -> str:
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else fallback

    @staticmethod
    def _extract_page_summary(content: str) -> str:
        match = re.search(r'\*\*Summary\*\*:\s*(.+)', content)
        return match.group(1).strip() if match else ""

    _WIKI_SOURCES_LINE_RE = re.compile(
        r"(?:\*\*Sources\*\*|##\s+Sources)\s*[:：]?\s*\n?\s*[-*]?\s*(\S[^\n]*)",
        re.IGNORECASE,
    )

    @staticmethod
    def _extract_wiki_sources_line(content: str) -> List[str]:
        match = ChatService._WIKI_SOURCES_LINE_RE.search(content)
        if not match:
            return []
        return [s.strip() for s in match.group(1).split(",") if s.strip()]

    @staticmethod
    def _build_page_stem_to_user_doc_label(kb_id: str) -> Dict[str, str]:
        """Wiki 页面 stem → 用户上传资料的可见名称（文档追踪中的 original_name 或 file）。"""
        track_path = get_kb_doc_track_path(kb_id)
        if not track_path.exists():
            return {}
        try:
            with open(track_path, "r", encoding="utf-8") as f:
                track = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        out: Dict[str, str] = {}
        for doc in track.get("documents", {}).values():
            label = (doc.get("original_name") or doc.get("file") or "").strip()
            if not label:
                continue
            for wp in doc.get("wiki_pages") or []:
                stem = Path(str(wp)).stem
                if stem and stem not in {"index", "log"}:
                    out[stem] = label
        return out

    @staticmethod
    def _user_visible_doc_label_for_page(
        wiki_stem: str,
        content: str,
        stem_to_label: Dict[str, str],
    ) -> str:
        if wiki_stem in stem_to_label:
            return stem_to_label[wiki_stem]
        sources = ChatService._extract_wiki_sources_line(content)
        return sources[0] if sources else ""

    @staticmethod
    def _strip_html(text: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_lib.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_web_url(raw_url: str) -> str:
        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        parsed = urlparse(raw_url)
        if "duckduckgo.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            uddg = query.get("uddg", [None])[0]
            if uddg:
                return unquote(uddg)
        return raw_url

    @staticmethod
    def _score_web_result(question_terms: List[str], item: Dict[str, str]) -> float:
        title = (item.get("title") or "").lower()
        snippet = (item.get("snippet") or "").lower()
        url = (item.get("url") or "").lower()

        score = 0.0
        for term in question_terms:
            if term in title:
                score += 4.0
            if term in snippet:
                score += 1.5
            if term in url:
                score += 0.25
        return score

    @staticmethod
    def _estimate_web_result_limit(question: str, available: int) -> int:
        """根据问题复杂度估算最终保留多少条联网结果。"""
        if available <= 0:
            return 0

        normalized = re.sub(r"\s+", "", question.strip())
        chunks = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9_-]{2,}', question.lower())
        limit = ChatService._WEB_SEARCH_BASE_RESULTS

        if len(normalized) > 18 or len(chunks) > 3:
            limit += 1
        if len(normalized) > 36 or len(chunks) > 5:
            limit += 1
        if len(normalized) > 60 or len(chunks) > 7:
            limit += 1

        marker_hits = sum(1 for marker in ChatService._WEB_SEARCH_COMPLEXITY_MARKERS if marker in question)
        if marker_hits >= 1:
            limit += 1
        if marker_hits >= 3:
            limit += 1

        if re.search(r"[、,，/;；].*[、,，/;；]", question):
            limit += 1

        return max(1, min(available, min(limit, ChatService._WEB_SEARCH_MAX_CANDIDATES)))

    @staticmethod
    def _simplify_web_search_question(question: str) -> str:
        """把检索词做轻量清洗，尽量保留原意。"""
        text = re.sub(r"\s+", " ", question).strip()
        if not text:
            return text

        if "：" in text or ":" in text:
            text = re.split(r"[:：]", text)[-1].strip() or text

        text = re.sub(r"[，,。！？!?；;、/]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _select_web_results(question: str, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not results:
            return []

        question_terms = ChatService._build_question_terms(question)
        scored_results = []
        for idx, item in enumerate(results):
            scored_results.append({
                **item,
                "_score": ChatService._score_web_result(question_terms, item),
                "_rank": idx,
            })

        scored_results.sort(key=lambda item: (item["_score"], -item["_rank"]), reverse=True)
        limit = ChatService._estimate_web_result_limit(question, len(scored_results))
        selected = scored_results[:limit]
        return [{k: v for k, v in item.items() if not k.startswith("_")} for item in selected]

    @staticmethod
    def _build_temporary_upload_context(temporary_upload_ids: Optional[List[str]]) -> str:
        if not temporary_upload_ids:
            return ""

        sections: List[str] = []
        total_chars = 0
        seen_ids = set()

        for upload_id in temporary_upload_ids:
            if not upload_id or upload_id in seen_ids:
                continue
            seen_ids.add(upload_id)

            meta = load_upload_metadata(upload_id)
            if not meta:
                continue

            path_value = meta.get("path")
            if not path_value:
                continue

            file_path = Path(str(path_value))
            if not file_path.exists():
                continue

            try:
                text = extract_document_text(file_path).strip()
            except Exception:
                continue

            if not text:
                continue

            filename = str(meta.get("original_filename") or meta.get("filename") or file_path.name)
            excerpt = text[:6000]
            section = f"### 临时上传文档：{filename}\n\n{excerpt}"
            sections.append(section)
            total_chars += len(section)
            if len(sections) >= 3 or total_chars >= 12000:
                break

        return "\n\n".join(sections)

    @staticmethod
    async def _web_search(question: str, max_results: int = _WEB_SEARCH_MAX_CANDIDATES) -> List[Dict[str, str]]:
        """使用 DuckDuckGo HTML 结果页做轻量联网搜索。"""
        pattern = re.compile(
            r'(?is)<div class="result[^"]*".*?'
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>)'
        )

        queries = [question.strip()]
        simplified_question = ChatService._simplify_web_search_question(question)
        if simplified_question and simplified_question not in queries:
            queries.append(simplified_question)

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Codex Wiki Assistant)"},
        ) as client:
            for search_question in queries:
                try:
                    resp = await client.get("https://html.duckduckgo.com/html/", params={"q": search_question})
                    resp.raise_for_status()
                except Exception:
                    continue

                if resp.status_code != 200:
                    continue

                results: List[Dict[str, str]] = []
                for match in pattern.finditer(resp.text):
                    url = ChatService._normalize_web_url(match.group(1).strip())
                    title = ChatService._strip_html(match.group(2))
                    snippet = ChatService._strip_html(match.group(3) or match.group(4) or "")
                    if not title or not snippet:
                        continue
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    })
                    if len(results) >= max_results:
                        break

                if results:
                    return results

        return []

    @staticmethod
    def _format_web_results(results: List[Dict[str, str]]) -> str:
        lines = []
        for idx, item in enumerate(results, 1):
            lines.append(
                f"### 结果{idx}: [{item['title']}]({item['url']})\n"
                f"- 链接：[{item['url']}]({item['url']})\n"
                f"- 摘要：{item['snippet']}"
            )
        return "\n\n".join(lines)

    @staticmethod
    async def _build_web_results(question: str) -> List[Dict[str, str]]:
        raw_results = await ChatService._web_search(question)
        return ChatService._select_web_results(question, raw_results)

    @staticmethod
    def _build_web_prompt(question: str, web_results: List[Dict[str, str]]) -> str:
        return WEB_QA_PROMPT.format(
            web_results=ChatService._format_web_results(web_results),
            question=question,
        )

    @staticmethod
    def _build_general_messages(question: str) -> List[Dict[str, str]]:
        """没有知识库时，直接调用模型进行通用问答。"""
        return [
            {
                "role": "system",
                "content": "你是一个专业的企业生产安全知识助手。请只回答企业生产安全、职业健康、应急处置、事故预防、隐患排查治理和现场安全管理相关问题；不要扩展到信息安全、网络安全、数据保护、个人隐私、合规、法务、财务或其他企业管理领域。如果问题明显依赖用户私有知识库，请说明当前未选择知识库，无法基于本地文档回答。回答要清晰、简洁、专业，优先使用自然标题、编号和列表，少用装饰性符号。你的回答要始终简洁高效，直奔主题，一针见血。"
            },
            {"role": "user", "content": question}
        ]

    @staticmethod
    def _build_continuation_messages(
        base_messages: List[Dict[str, str]],
        accumulated_answer: str,
    ) -> List[Dict[str, str]]:
        tail = accumulated_answer[-ChatService._AUTO_CONTINUATION_TAIL_CHARS:].strip()
        continuation_user_prompt = ChatService._AUTO_CONTINUATION_PROMPT
        if tail:
            continuation_user_prompt += f"\n\n已输出末尾：{tail}"
        return [
            *base_messages,
            {"role": "assistant", "content": accumulated_answer},
            {"role": "user", "content": continuation_user_prompt},
        ]

    async def _stream_with_auto_continuation(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        accumulated_answer = ""
        attempt = 0
        current_messages = list(messages)

        while attempt < ChatService._AUTO_CONTINUATION_MAX_ATTEMPTS:
            attempt_buffer = []
            finish_reason = None

            async for event in self.llm_service.chat_events(
                current_messages,
                model_id=model_id,
                stream=True,
                temperature=temperature,
                max_tokens=ChatService._AUTO_CONTINUATION_MAX_TOKENS,
            ):
                event_type = event.get("type")
                if event_type == "chunk":
                    chunk = event.get("content") or ""
                    if not chunk:
                        continue
                    attempt_buffer.append(chunk)
                    yield chunk
                elif event_type == "done":
                    finish_reason = event.get("finish_reason")
                elif event_type == "error":
                    message = event.get("message") or "请求错误"
                    if message:
                        yield message
                    return

            attempt_answer = "".join(attempt_buffer)
            accumulated_answer += attempt_answer

            if finish_reason not in {"length", "max_tokens"}:
                return

            attempt += 1
            if attempt >= ChatService._AUTO_CONTINUATION_MAX_ATTEMPTS:
                return

            current_messages = ChatService._build_continuation_messages(messages, accumulated_answer)

    @staticmethod
    def _merge_system_prompt(base_prompt: str, assistant_prompt: Optional[str] = None) -> str:
        if not assistant_prompt or not assistant_prompt.strip():
            return base_prompt
        return f"{assistant_prompt.strip()}\n\n{base_prompt}"

    @staticmethod
    def _normalize_history_messages(messages: Optional[List[ChatMessage]], max_messages: int = 12) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        if not messages:
            return normalized

        for msg in messages[-max_messages:]:
            role = (msg.role or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = (msg.content or "").strip()
            if not content:
                continue
            normalized.append({"role": role, "content": content})

        return normalized

    @staticmethod
    def _build_contextual_question(question: str, history_messages: List[Dict[str, str]]) -> str:
        """用最近一轮或两轮上下文轻微扩展检索问题。"""
        previous_user_messages = [msg["content"] for msg in history_messages if msg["role"] == "user"]
        if not previous_user_messages:
            return question

        context = " ".join(previous_user_messages[-2:])
        combined = f"{context} {question}".strip()
        return combined if combined else question
    
    @staticmethod
    def _find_related_pages(kb_id: str, question: str, max_pages: int = 5) -> List[Dict]:
        """
        在知识库 wiki 目录下扫描除 index.md / log.md 外的页面，按关键词子串匹配打分，
        返回 score > 0 的页面摘要（索引由 ask() 单独读取）。
        """
        wiki_path = get_kb_wiki_path(kb_id)
        if not wiki_path.exists():
            return []
        
        # 提取问题关键词
        keywords = ChatService._build_question_terms(question)

        stem_to_label = ChatService._build_page_stem_to_user_doc_label(kb_id)

        related = []
        
        # 遍历所有Wiki页面
        for file_path in sorted(wiki_path.glob("*.md")):
            if file_path.name in ["index.md", "log.md"]:
                continue
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            title = ChatService._extract_page_title(content, file_path.stem)
            summary = ChatService._extract_page_summary(content)
            content_lower = content.lower()
            title_lower = title.lower()
            summary_lower = summary.lower()

            # 计算匹配度
            # 只使用长度 >= 3 的关键词参与评分：
            # 2字符词（如"安全"、"生产"）在安全生产领域极为通用，
            # 几乎所有页面都会命中，导致无关页面得分虚高、冲淡相关排序。
            score = 0.0
            for keyword in keywords:
                if len(keyword) < 3:
                    continue
                if keyword in title_lower:
                    score += 4
                if summary and keyword in summary_lower:
                    score += 2
                if keyword in content_lower:
                    score += 1

            headings = re.findall(r'^#{2,}\s+(.+)$', content, re.MULTILINE)
            for heading in headings[:8]:
                heading_lower = heading.lower()
                for keyword in keywords:
                    if len(keyword) < 3:
                        continue
                    if keyword in heading_lower:
                        score += 0.5

            excerpt = content[:3000] if len(content) > 3000 else content
            user_doc_label = ChatService._user_visible_doc_label_for_page(
                file_path.stem, content, stem_to_label
            )
            related.append({
                "name": file_path.stem,
                "title": title,
                "score": score,
                "content": excerpt,
                "user_doc_label": user_doc_label,
            })

        # 过滤掉完全不相关的页面（score=0 意味着问题关键词在该页面中完全没有命中）
        related = [p for p in related if p["score"] > 0]
        # 按匹配度排序，取前N个
        related.sort(key=lambda x: (x["score"], len(x["content"])), reverse=True)
        return related[:max_pages]
    
    async def ask(
        self,
        question: str,
        knowledge_base_ids: List[str],
        messages: Optional[List[ChatMessage]] = None,
        model_id: Optional[str] = None,
        use_web_search: bool = False,
        assistant_prompt: Optional[str] = None,
        temporary_upload_ids: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        回答问题
        
        Args:
            question: 用户问题
            knowledge_base_ids: 知识库ID列表
            model_id: 模型ID
        
        Yields:
            流式输出答案文本
        """
        history_messages = ChatService._normalize_history_messages(messages)
        temporary_upload_context = ChatService._build_temporary_upload_context(temporary_upload_ids)
        upload_context_message = (
            {
                "role": "system",
                "content": "以下是用户临时上传的文档内容，仅供本次问答参考：\n\n" + temporary_upload_context,
            }
            if temporary_upload_context
            else None
        )

        if not knowledge_base_ids:
            if use_web_search:
                web_results = await ChatService._build_web_results(question)
                if web_results:
                    prompt = ChatService._build_web_prompt(question, web_results)
                    prompt_messages = [
                        {
                            "role": "system",
                            "content": ChatService._merge_system_prompt(
                                "你是一个专业的企业生产安全知识助手。请基于联网检索结果回答，不要编造。只聚焦企业生产安全、职业健康、应急处置、事故预防、隐患排查治理和现场安全管理；不要扩展到信息安全、网络安全、数据保护、个人隐私、合规、法务、财务或其他企业管理领域。你的回答要始终简洁高效，直奔主题，一针见血。",
                                assistant_prompt
                            )
                        }
                    ]
                    if upload_context_message:
                        prompt_messages.append(upload_context_message)
                    prompt_messages.extend(history_messages)
                    prompt_messages.append({"role": "user", "content": prompt})
                    async for chunk in self._stream_with_auto_continuation(
                        prompt_messages,
                        model_id=model_id,
                    ):
                        if chunk is None:
                            continue
                        yield chunk
                    return

            prompt_messages = ChatService._build_general_messages(question)
            prompt_messages[0]["content"] = ChatService._merge_system_prompt(prompt_messages[0]["content"], assistant_prompt)
            if upload_context_message:
                prompt_messages.append(upload_context_message)
            prompt_messages.extend(history_messages)
            async for chunk in self._stream_with_auto_continuation(
                prompt_messages,
                model_id=model_id,
            ):
                if chunk is None:
                    continue
                yield chunk
            return
        
        # 收集所有知识库的相关页面（只要选了知识库，始终走知识库问答，不因无命中而降级联网/通用模型）
        all_related_pages = []
        all_index_content = []
        search_question = ChatService._build_contextual_question(question, history_messages)

        for kb_id in knowledge_base_ids:
            # 读取索引
            index_path = get_kb_index_path(kb_id)
            index_content = ChatService._read_file(index_path)
            all_index_content.append(f"知识库「{kb_id}」的索引：\n{index_content}")
            
            # 查找相关页面
            related = ChatService._find_related_pages(kb_id, search_question)
            for page in related:
                all_related_pages.append({
                    "kb_id": kb_id,
                    **page
                })

        # 构建相关知识内容
        related_content = ""
        for i, page in enumerate(all_related_pages[:5], 1):
            label = (page.get("user_doc_label") or "").strip()
            header_extra = ""
            if label:
                header_extra = (
                    "\n> **对应上传资料**（需要说明出处时可写此名；"
                    "**禁止**写 Wiki 子页面英文名、`.md` 或下方「资料片段」编号）："
                    f"{label}\n"
                )
            related_content += f"\n### 资料片段 {i}{header_extra}\n\n{page['content']}\n\n"
        
        # 构建Prompt
        prompt = QA_PROMPT.format(
            index_content="\n\n".join(all_index_content),
            related_pages=related_content,
            question=question
        )
        
        prompt_messages = [
            {
                "role": "system",
                "content": ChatService._merge_system_prompt(
                    "你是一个专业的企业生产安全知识库问答助手。请基于知识库内容回答，不要编造。只聚焦企业生产安全、职业健康、应急处置、事故预防、隐患排查治理和现场安全管理；不要扩展到信息安全、网络安全、数据保护、个人隐私、合规、法务、财务或其他企业管理领域。你的回答要始终简洁高效，直奔主题，一针见血。",
                    assistant_prompt
                )
            },
        ]
        if upload_context_message:
            prompt_messages.append(upload_context_message)
        prompt_messages.extend(history_messages)
        prompt_messages.append({"role": "user", "content": prompt})
        
        # 调用LLM生成答案
        async for chunk in self._stream_with_auto_continuation(
            prompt_messages,
            model_id=model_id,
        ):
            if chunk is None:
                continue
            yield chunk
    
    async def ask_sync(
        self,
        question: str,
        knowledge_base_ids: List[str],
        messages: Optional[List[ChatMessage]] = None,
        model_id: Optional[str] = None,
        use_web_search: bool = False,
        assistant_prompt: Optional[str] = None,
        temporary_upload_ids: Optional[List[str]] = None,
    ) -> str:
        """同步回答问题，返回完整文本"""
        result = []
        async for chunk in self.ask(
            question,
            knowledge_base_ids,
            messages,
            model_id,
            use_web_search,
            assistant_prompt,
            temporary_upload_ids,
        ):
            if chunk is None:
                continue
            result.append(chunk)
        return "".join(result)


# 服务实例
chat_service = ChatService()
