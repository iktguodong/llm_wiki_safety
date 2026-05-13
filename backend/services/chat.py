"""
知识问答服务
基于知识库Wiki页面回答问题
"""

import html as html_lib
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from backend.config import get_kb_wiki_path, get_kb_index_path
from backend.models import ChatMessage
from backend.services.llm import llm_service


_QUESTION_STOPWORDS = {
    "什么", "怎么", "如何", "哪些", "是否", "是不是", "谁", "哪", "哪个", "哪种",
    "请问", "一下", "一个", "一些", "有关", "关于", "情况", "意思", "原因", "方法",
    "流程", "步骤", "规定", "要求", "内容", "范围", "时候", "如何", "怎样", "为何",
}


# 问答Prompt
QA_PROMPT = """你是一个专业知识库问答助手。请基于以下wiki知识库内容回答用户问题。

## 可用知识

### wiki/index.md（知识库索引）
{index_content}

### 相关知识页面
{related_pages}

## 回答要求

1. **准确性优先**
   - 答案必须基于提供的wiki知识
   - 如果知识中没有答案，明确说明"知识库中暂无相关信息"
   - 不要编造或推测

2. **引用来源**
   - 每个关键论点必须标注来源页面
   - 使用清爽的自然语言写法，例如“来源：应急组织机构及职责”
   - 在答案末尾列出所有引用页面名，不要使用 `[[页面名]]` 这种 Wiki 链接语法

3. **格式清晰**
   - 优先使用自然标题、编号步骤、项目符号和表格组织内容，减少直接暴露 Markdown 语法
   - 复杂流程使用步骤化描述
   - 适合对照的信息可以用表格，不适合表格时改成“字段：内容”的分点说明

4. **冲突处理**
   - 如果不同页面信息有冲突，明确指出
   - 说明各页面分别是什么观点

## 用户问题

{question}
"""

WEB_QA_PROMPT = """你是一个专业的企业安全知识助手。请基于提供的联网检索结果和问题回答。

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
    _WEB_SEARCH_BASE_RESULTS = 3
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
    async def _web_search(question: str, max_results: int = _WEB_SEARCH_MAX_CANDIDATES) -> List[Dict[str, str]]:
        """使用 DuckDuckGo HTML 结果页做轻量联网搜索。"""
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Codex Wiki Assistant)"},
            ) as client:
                resp = await client.get("https://html.duckduckgo.com/html/", params={"q": question})
                resp.raise_for_status()
        except Exception:
            return []

        pattern = re.compile(
            r'(?is)<div class="result[^"]*".*?'
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>)'
        )

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

        return results

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
    async def _build_web_results(question: str, history_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        search_question = ChatService._build_contextual_question(question, history_messages)
        raw_results = await ChatService._web_search(search_question)
        return ChatService._select_web_results(search_question, raw_results)

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
                "content": "你是一个专业的企业安全知识助手。请基于通用知识回答用户问题；如果问题明显依赖用户私有知识库，请说明当前未选择知识库，无法基于本地文档回答。回答要清晰、简洁、专业，优先使用自然标题、编号和列表，少用装饰性符号。"
            },
            {"role": "user", "content": question}
        ]

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
        根据问题找到相关的Wiki页面
        
        策略：
        1. 先读取index.md获取知识库结构
        2. 根据关键词匹配相关页面
        3. 返回最相关的页面内容
        """
        wiki_path = get_kb_wiki_path(kb_id)
        if not wiki_path.exists():
            return []
        
        # 提取问题关键词
        keywords = ChatService._build_question_terms(question)
        
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
            score = 0.0
            for keyword in keywords:
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
                    if keyword in heading_lower:
                        score += 0.5

            excerpt = content[:3000] if len(content) > 3000 else content
            related.append({
                "name": file_path.stem,
                "title": title,
                "score": score,
                "content": excerpt
            })

        # 按匹配度排序，取前N个
        related.sort(key=lambda x: (x["score"], len(x["content"])), reverse=True)
        return related[:max_pages]
    
    @staticmethod
    async def ask(
        question: str,
        knowledge_base_ids: List[str],
        messages: Optional[List[ChatMessage]] = None,
        model_id: Optional[str] = None,
        use_web_search: bool = False,
        assistant_prompt: Optional[str] = None
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

        if not knowledge_base_ids:
            if use_web_search:
                web_results = await ChatService._build_web_results(question, history_messages)
                if web_results:
                    prompt = ChatService._build_web_prompt(question, web_results)
                    prompt_messages = [
                        {
                            "role": "system",
                            "content": ChatService._merge_system_prompt(
                                "你是一个专业的企业安全知识助手。请基于联网检索结果回答，不要编造。",
                                assistant_prompt
                            )
                        },
                        *history_messages,
                        {"role": "user", "content": prompt}
                    ]
                    async for chunk in llm_service.chat(prompt_messages, model_id=model_id, stream=True):
                        if chunk is None:
                            continue
                        yield chunk
                    return

            prompt_messages = ChatService._build_general_messages(question)
            prompt_messages[0]["content"] = ChatService._merge_system_prompt(prompt_messages[0]["content"], assistant_prompt)
            prompt_messages[1:1] = history_messages
            async for chunk in llm_service.chat(prompt_messages, model_id=model_id, stream=True):
                if chunk is None:
                    continue
                yield chunk
            return
        
        # 收集所有知识库的相关页面
        all_related_pages = []
        all_index_content = []
        
        for kb_id in knowledge_base_ids:
            # 读取索引
            index_path = get_kb_index_path(kb_id)
            index_content = ChatService._read_file(index_path)
            all_index_content.append(f"知识库「{kb_id}」的索引：\n{index_content}")
            
            # 查找相关页面
            search_question = ChatService._build_contextual_question(question, history_messages)
            related = ChatService._find_related_pages(kb_id, search_question)
            for page in related:
                all_related_pages.append({
                    "kb_id": kb_id,
                    **page
                })
        
        if not all_related_pages:
            if use_web_search:
                web_results = await ChatService._build_web_results(question, history_messages)
                if web_results:
                    prompt = ChatService._build_web_prompt(question, web_results)
                    prompt_messages = [
                        {
                            "role": "system",
                            "content": ChatService._merge_system_prompt(
                                "你是一个专业的企业安全知识助手。请基于联网检索结果回答，不要编造。",
                                assistant_prompt
                            )
                        },
                        *history_messages,
                        {"role": "user", "content": prompt}
                    ]
                    async for chunk in llm_service.chat(prompt_messages, model_id=model_id, stream=True):
                        if chunk is None:
                            continue
                        yield chunk
                    return

            yield "知识库中暂无相关信息，请尝试上传相关文档或调整问题。"
            return

        # 构建相关知识内容
        related_content = ""
        for i, page in enumerate(all_related_pages[:5], 1):
            related_content += f"\n### 页面{i}: {page['title']}\n\n{page['content']}\n\n"
        
        # 构建Prompt
        prompt = QA_PROMPT.format(
            index_content="\n\n".join(all_index_content),
            related_pages=related_content,
            question=question
        )

        if use_web_search:
            web_results = await ChatService._build_web_results(question, history_messages)
            if web_results:
                prompt += "\n\n## 联网检索结果\n\n" + ChatService._format_web_results(web_results)
        
        messages = [
            {
                "role": "system",
                "content": ChatService._merge_system_prompt(
                    "你是一个专业的企业安全知识库问答助手。若提供了联网检索结果，请结合知识库与联网信息作答，不要编造。",
                    assistant_prompt
                )
            },
            *history_messages,
            {"role": "user", "content": prompt}
        ]
        
        # 调用LLM生成答案
        async for chunk in llm_service.chat(messages, model_id=model_id, stream=True):
            if chunk is None:
                continue
            yield chunk
    
    @staticmethod
    async def ask_sync(
        question: str,
        knowledge_base_ids: List[str],
        messages: Optional[List[ChatMessage]] = None,
        model_id: Optional[str] = None,
        use_web_search: bool = False,
        assistant_prompt: Optional[str] = None
    ) -> str:
        """同步回答问题，返回完整文本"""
        result = []
        async for chunk in ChatService.ask(question, knowledge_base_ids, messages, model_id, use_web_search, assistant_prompt):
            if chunk is None:
                continue
            result.append(chunk)
        return "".join(result)


# 服务实例
chat_service = ChatService()
