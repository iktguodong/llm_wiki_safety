"""助手提示词优化服务"""

from __future__ import annotations

import re

from backend.services.llm import llm_service


PROMPT_OPTIMIZER_SYSTEM = """你是一个资深的中文系统提示词编辑器。

任务：把用户给出的助手设定改写成更高质量、可直接使用的系统提示词。

要求：
1. 保持原有助手的核心角色、目标、边界和语气，不要擅自改变任务范围。
2. 合并重复内容，删除空话、口号、冗余解释和重复的格式要求。
3. 尽量整理成清晰结构，优先包含：角色定位、核心任务、回答原则、输出格式、边界与禁止事项。
4. 如果原提示词较短，可适当补足结构，但不要引入与主题无关的新能力。
5. 需要保留原有的关键约束、专有名词和业务背景。
6. 只输出最终可直接使用的提示词正文，不要输出分析、说明、前缀、后缀、标题或代码块标记。
7. 使用简洁、专业、可执行的中文表达。
"""

_CODE_BLOCK_RE = re.compile(r"```(?:[\w-]+)?\s*(.*?)\s*```", re.S)
_PREFIX_RE = re.compile(
    r"^(?:优化后的提示词|优化结果|重写后的提示词|重写结果|提示词优化结果|以下是优化后的提示词|下面是优化后的提示词)[:：]?\s*",
    re.S,
)


def _clean_optimized_prompt(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    code_block = _CODE_BLOCK_RE.search(cleaned)
    if code_block:
        cleaned = code_block.group(1).strip()

    cleaned = _PREFIX_RE.sub("", cleaned).strip()
    cleaned = cleaned.strip("`").strip()
    return cleaned


async def optimize_prompt(
    name: str,
    description: str,
    system_prompt: str,
    model_id: str | None = None,
) -> str:
    user_prompt = f"""请优化下面这个助手提示词，让它更适合作为系统提示词使用。

助手名称：{name}
助手描述：{description or '无'}

当前提示词：
{system_prompt.strip()}
"""
    result = await llm_service.chat_sync(
        [
            {"role": "system", "content": PROMPT_OPTIMIZER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        model_id=model_id,
        temperature=0.2,
    )
    cleaned = _clean_optimized_prompt(result)
    if not cleaned:
        raise ValueError("优化提示词失败：模型没有返回有效内容")
    if cleaned.startswith("API Key 未配置") or cleaned.startswith("错误") or cleaned.startswith("API错误") or cleaned.startswith("请求错误"):
        raise ValueError(cleaned)
    return cleaned
