"""HTML 训练材料规划器（thin wrapper）。

本模块现在直接委托给 LLM 规划器（html_llm_planner），不再包含规则打分逻辑。
老规则函数（_extract_pool, _condense_statement 等）全部移除；可复用的工具已迁至 html_text_utils.py。
"""

from __future__ import annotations

from typing import Any

from .html_deck import HtmlDeckSpec
from .html_llm_planner import build_html_deck_llm
from .models import ContentPack


async def build_html_deck(content_pack: ContentPack, settings: Any) -> HtmlDeckSpec:
    """生成 HTML Deck（委托 LLM 规划器）。

    LLM 调用异常或输出违反约束时抛 HtmlGenerationError（继承 ValueError），
    app 层需捕获并转为 400 响应。
    """
    return await build_html_deck_llm(content_pack, settings)
