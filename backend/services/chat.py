"""
知识问答服务
基于知识库Wiki页面回答问题
"""

import re
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from backend.config import get_kb_wiki_path, get_kb_index_path
from backend.services.llm import llm_service


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
   - 使用格式：[[页面名]] 或 (来源: 原始文档.pdf)
   - 在答案末尾列出所有引用页面

3. **格式清晰**
   - 使用标题、列表、代码块等Markdown格式
   - 复杂流程使用步骤化描述
   - 关键信息加粗强调

4. **冲突处理**
   - 如果不同页面信息有冲突，明确指出
   - 说明各页面分别是什么观点

## 用户问题

{question}
"""


class ChatService:
    """问答服务"""
    
    @staticmethod
    def _read_file(file_path: Path) -> str:
        """读取文件内容"""
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
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
        keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', question.lower()))
        
        related = []
        
        # 遍历所有Wiki页面
        for file_path in wiki_path.glob("*.md"):
            if file_path.name in ["index.md", "log.md"]:
                continue
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 计算匹配度
            score = 0
            content_lower = content.lower()
            
            for keyword in keywords:
                if keyword in content_lower:
                    score += 1
            
            # 标题匹配权重更高
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).lower()
                for keyword in keywords:
                    if keyword in title:
                        score += 3
            
            if score > 0:
                # 截取相关内容（前3000字）
                excerpt = content[:3000] if len(content) > 3000 else content
                
                related.append({
                    "name": file_path.stem,
                    "score": score,
                    "content": excerpt
                })
        
        # 按匹配度排序，取前N个
        related.sort(key=lambda x: x["score"], reverse=True)
        return related[:max_pages]
    
    @staticmethod
    async def ask(
        question: str,
        knowledge_base_ids: List[str],
        model_id: Optional[str] = None
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
        if not knowledge_base_ids:
            yield "错误：请至少选择一个知识库"
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
            related = ChatService._find_related_pages(kb_id, question)
            for page in related:
                all_related_pages.append({
                    "kb_id": kb_id,
                    **page
                })
        
        if not all_related_pages:
            yield "知识库中暂无相关信息，请尝试上传相关文档或调整问题。"
            return
        
        # 构建相关知识内容
        related_content = ""
        for i, page in enumerate(all_related_pages[:5], 1):
            related_content += f"\n### 页面{i}: {page['name']}\n\n{page['content']}\n\n"
        
        # 构建Prompt
        prompt = QA_PROMPT.format(
            index_content="\n\n".join(all_index_content),
            related_pages=related_content,
            question=question
        )
        
        messages = [
            {"role": "system", "content": "你是一个专业的企业安全知识库问答助手。"},
            {"role": "user", "content": prompt}
        ]
        
        # 调用LLM生成答案
        async for chunk in llm_service.chat(messages, model_id=model_id, stream=True):
            yield chunk
    
    @staticmethod
    async def ask_sync(
        question: str,
        knowledge_base_ids: List[str],
        model_id: Optional[str] = None
    ) -> str:
        """同步回答问题，返回完整文本"""
        result = []
        async for chunk in ChatService.ask(question, knowledge_base_ids, model_id):
            result.append(chunk)
        return "".join(result)


# 服务实例
chat_service = ChatService()
