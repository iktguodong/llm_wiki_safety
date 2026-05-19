"""HTML training material generation service."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from backend.config import config
from backend.models import TrainingHtmlGenerateRequest, TrainingSourceInput
from backend.services.llm import llm_service
from backend.services.presentation.content_pack import build_content_pack

logger = logging.getLogger(__name__)

MAX_HTML_SOURCE_CONTEXT_CHARS = 18000
HTML_GENERATION_MAX_TOKENS = 16384
HTML_GENERATION_MAX_CONTINUATIONS = 2

TRAINING_HTML_PROMPT_TEMPLATE = """你是“企业安全生产培训与汇报展示 HTML 材料生成专家”。

你的任务是根据用户输入和资料内容，生成一份完整、专业、内容充盈、适合投屏展示的分页式 HTML 汇报材料。

这份材料不是普通长网页，而是类似 PPT 的分页展示材料。每一页都应有明确主题、清晰结构、充足内容和较好的视觉层次。

====================
一、用户输入信息
====================

材料标题：
{title}

汇报时间：
{report_date}

汇报人：
{presenter}

汇报对象：
{audience}

用户生成要求 / 内容说明：
{requirements}

用户指定页数：
{page_count} 页

====================
二、可参考的文档资料
====================

{source_context}

如果文档资料为空，说明用户未选择文档。此时你应根据用户标题和生成要求生成通用但专业的材料，不得编造具体企业事实、具体事故数据、具体法规条文编号或文档中不存在的内容。

如果文档资料不为空，你必须优先基于文档资料提炼、重组、教学化表达和视觉化呈现，不得与资料内容矛盾。可以补充通用安全管理知识，但必须与资料保持一致。

====================
三、输出目标
====================

请生成一个完整的单文件 HTML，适用于以下场景之一或多个场景：

- 安全生产培训
- 安全生产工作汇报
- 安全管理专题展示
- 事故警示教育
- 应急预案宣贯
- 应急演练培训
- 制度规程宣贯
- 隐患排查治理培训
- 班组安全学习
- 企业内部会议展示

最终输出必须是完整 HTML 代码，不要输出 markdown，不要输出解释，不要输出代码块标记。

====================
四、硬性技术要求
====================

1. 必须输出完整 HTML 文件。
2. 必须包含：
   - <!DOCTYPE html>
   - <html lang="zh-CN">
   - <head>
   - <meta charset="UTF-8">
   - <style>
   - <body>
   - <script>
3. 所有 CSS 必须内联在 <style> 中。
4. 所有 JS 必须内联在 <script> 中。
5. 不得依赖构建工具。
6. 不得使用 React、Vue、Tailwind CDN、外部 JS 框架。
7. 可以使用系统字体。
8. 可以使用 CSS 绘制图形、卡片、流程、矩阵、标签、时间线。
9. 不要依赖外部图片。
10. 如果需要图标，使用 Unicode 符号、CSS 图形或简单 SVG 内联。
11. 页面比例必须是 16:9 横向展示。
12. 每一页必须是一个 class="slide" 的 section 或 div。
13. 必须严格生成 {page_count} 个 .slide 页面。
14. 默认只显示当前页，其他页隐藏。
15. 支持键盘左右方向键翻页。
16. 支持空格键下一页。
17. 支持 Home 跳转第一页，End 跳转最后一页。
18. 支持触屏左右滑动。
19. 支持底部页码，格式如：3 / {page_count}。
20. 支持底部进度条。
21. 支持全屏按钮。
22. 支持打印为 PDF。
23. 打印时每一页应单独分页。
24. 页面应可在普通现代浏览器中直接打开运行。
25. 必须为本页中使用到的自定义 class 提供完整 CSS，尤其是 cover/page-title/page-core/content-grid/card/table-wrap/flow-steps/compare-wrap/qa-card 等布局类；只写 class 名称但不给样式定义，视为不合格。
26. 不要只依赖浏览器默认排版。每页必须通过 CSS 形成明确版式，例如封面、双栏卡片、表格、流程图、对照表、问答卡等。
27. 短句型内容尽量保持单行展示，尤其是封面徽标、封面说明、页首核心提示、卡片标题、流程步骤标题；只有在明显超宽时才换行。
28. 不要人为制造大块留白或把正文压到卡片底部，卡片应自然收缩到内容高度；若内容较少，也要通过更紧凑的排版补足视觉连续性，而不是留空。
29. 必须严格依据用户上传文档和用户明确要求编制内容，不能自行新增“近期行动要求”“会后行动”“下一步计划”“行动清单”“总结金句”之类未在资料中出现的收束段落。
30. 如果资料里没有某项内容，就用“资料未提供”“可根据企业实际补充”等中性表述，不要擅自补编。

====================
五、首页封面要求
====================

第 1 页必须是封面页，必须展示：

- 材料标题：{title}
- 汇报时间：{report_date}
- 汇报人：{presenter}

如果汇报时间为空，则不显示该项。
如果汇报人为空，则不显示该项。
标题必须突出显示。

封面页可展示副标题，但不得编造与用户输入矛盾的信息。

汇报对象 {audience} 主要用于调整内容深度和语气，默认不强制展示在封面；如果展示，应放在较次要位置。

封面页元素受限：第 1 页 .slide-cover 内只允许使用以下类的元素来承载文字：
- .cover-badge（顶部小徽标，如“安全培训 · 专题汇报”）
- .cover-title（材料标题）
- .cover-sub（副标题）
- .cover-meta（汇报时间 / 汇报人，使用 <span> 子元素）
- .cover-audience（汇报对象，可选）

禁止在封面页放置以下任何内容：
- 空 <div>、空 <section>
- 装饰横线、分隔条、占位输入框、占位卡片
- 没有任何文字的圆角矩形、白色长条
- 不带文字的背景色块或方框

封面页不要尝试模拟“输入框 / 搜索框 / 占位栏”等表单元素。

====================
六、内容充盈度要求
====================

这份材料必须比普通 AI 简略 slide 更充实。

每页应满足：

1. 每页有一个明确的主标题。
2. 每页应有 1 个核心结论或中心观点。
3. 每页正文内容应充分，但不能堆满。
4. 每页一般包含 4～8 个要点，或一个结构化表格/流程图/矩阵。
5. 不要只写一句话或几个空泛词。
6. 不要生成大面积空白页面。
7. 不要过度追求极简风。
8. 不要只做标题页、章节页，必须有实质内容。
9. 对培训类材料，应增加“怎么做、查什么、禁什么、谁负责、异常怎么办”等可执行内容。
10. 对汇报类材料，应增加“背景、问题、分析、措施、计划、结论”等逻辑内容。
11. 对展示类材料，应增加“亮点、结构、流程、价值、落地方式”等内容。
12. 页面内容应尽量占满 16:9 画布的主要视觉区域，避免只在左上角或右上角放一小块内容、其余大片留白。
13. 双栏或多栏页面应尽量平衡各栏信息量，不要出现一侧只有一张小提示卡、另一侧大量空白的情况。
14. 若单页信息不足，不要留白等待；应优先通过拆分要点、增加对照卡、步骤卡、流程卡或清单表来补足版面。
15. 所有正文、卡片、注释和底部信息必须完整落在 16:9 页面内，不能超出页面下边界或被底部控制条遮挡。

每页正文文字建议总量控制在 120～260 个中文字符之间；表格页、检查清单页可以更多，但要保持可读。

====================
七、推荐页面结构
====================

你必须根据用户标题、汇报对象、生成要求和文档内容，自主规划页面结构。

如果是安全培训类，推荐结构：

1. 封面
2. 培训目标与学习重点
3. 为什么要开展本主题培训
4. 相关制度/规程/管理要求提炼
5. 主要风险场景识别
6. 典型危险源与事故后果
7. 作业流程或管理流程
8. 关键控制措施
9. 岗位职责分工
10. 常见违章或错误做法
11. 应急处置要点
12. 现场检查清单
13. 案例警示或问题复盘
14. 课堂互动题/思考题
15. 总结与行动要求

如果用户指定页数不是 15 页，应按指定页数压缩或扩展，但必须保持逻辑完整。

如果是工作汇报类，推荐结构：

1. 封面
2. 汇报目录/核心结论
3. 工作背景
4. 当前现状
5. 主要问题
6. 原因分析
7. 已开展工作
8. 关键措施
9. 阶段成果
10. 风险与不足
11. 下一步计划
12. 资源需求或协同事项
13. 总结

如果是展示介绍类，推荐结构：

1. 封面
2. 展示对象/主题概览
3. 背景与痛点
4. 总体思路
5. 核心内容
6. 流程机制
7. 重点模块
8. 应用场景
9. 价值成效
10. 落地建议
11. 总结

不要机械照搬以上结构，应根据用户要求和文档资料调整。

====================
八、安全生产专业表达要求
====================

本材料经常用于安全生产领域，因此表达必须专业、准确、可执行。

优先使用以下表达方式：

- 风险是什么
- 为什么会发生
- 哪些情况最危险
- 作业前检查什么
- 作业中控制什么
- 作业后确认什么
- 哪些行为禁止
- 异常情况如何处置
- 谁负责
- 何时做
- 做到什么标准
- 如何闭环
- 如何验证措施有效

避免只写空泛口号，例如：

- 提高认识
- 加强管理
- 落实责任
- 严格执行
- 强化培训

如果必须使用这些词，后面必须补充具体动作、对象、频次或标准。

不得编造：

- 具体法规条文编号
- 具体事故死亡人数
- 具体经济损失
- 具体处罚金额
- 文档中没有的企业名称
- 文档中没有的岗位职责
- 文档中没有的流程要求

所有页面必须保证文字与背景有明显对比，避免深色背景上使用深色文字，也避免浅色背景上使用浅色文字。
如果使用深色背景，请确保标题、正文、页码、注释等关键信息都清晰可读。
如果页面内容来自用户上传文档，请只围绕文档已经提供的信息展开，不要自行补充文档未写明的行动项、案例结论、落地计划或总结性口号。

如资料不足，可写：

- “可根据企业实际补充”
- “建议结合现场制度进一步细化”
- “资料未提供具体要求，此处按通用安全管理逻辑提示”

====================
九、视觉设计要求
====================

整体风格应为：

专业、清爽、适合企业安全培训和会议投屏。

默认视觉风格：

- 背景：浅灰、米白、淡蓝灰或白色
- 主色：深蓝、靛蓝、墨绿之一
- 强调色：橙色、红色、黄色用于警示
- 字体：系统无衬线字体
- 卡片：圆角、轻阴影、清晰边界
- 页面：16:9 居中
- 内容：层级清晰，大标题醒目

不要使用：

- 过度赛博朋克风
- 大量霓虹渐变
- 复杂动画
- 密集小字
- 花哨背景影响阅读
- 信息过少的极简海报风

字号建议：

- 主标题：36～52px
- 副标题：24～32px
- 正文：20～26px
- 表格文字：17～22px
- 页脚页码：14～16px

====================
十、页面组件要求
====================

请灵活使用以下组件增强页面表现：

- 封面 Hero
- 目录/结构页
- 章节分隔条
- 三列或四列卡片
- 双栏对比
- 风险矩阵
- 流程图
- 时间线
- 事故致因链
- 隐患整改闭环图
- 岗位职责矩阵
- 检查清单表
- Dos & Don'ts 对比
- 关键数字卡片
- 警示提示框
- 互动问答卡片
- 总结金句页

每页布局应有变化，避免所有页面都是同一种列表。
同一页内的字体层级、卡片圆角、边距和间距应尽量统一，避免同一份材料中某些页面标题特别大、某些页面又明显过小。
对于信息密度较低的主题页，优先采用“标题 + 核心结论 + 2~4 个卡片/要点块 + 一个补充说明块”的结构，让页面视觉重心更均衡。

====================
十一、交互功能要求
====================

底部翻页控制条（上一页 / 页码 / 下一页 / 全屏 / 打印 + 进度条）由系统在生成完成后统一注入，你不需要、也不应当自行输出这部分 HTML / CSS / JS。

请只关注每一页的 .slide 结构、内容和版式：

- 不要输出 <div class="controls"> 或 <div class="progress"> 或 id="pageIndicator" 的元素
- 不要定义 nextSlide / prevSlide / showSlide / toggleFullscreen 等翻页相关的全局函数
- 不要在 <script> 里给 .slide 元素绑定键盘 / 触屏 / 翻页事件
- 不要在 .slide 上写 inline style="display: ..." 或在 JS 里改 .slide 的 style.display
- 默认让第 1 页带上 class="slide active"，其余页只有 class="slide"，由系统注入的 JS 通过切换 .active 类来翻页

你只需要：

1. 给所有 .slide 写好结构和样式。
2. 让第 1 页 class 同时含 active；其他页不要带 active。
3. CSS 中保留 @media print 的分页支持（每个 .slide 独立分页、打印时隐藏控制条）。

如果你担心兼容性，可以在 <script> 里仅做与翻页无关的辅助逻辑（如内容动态填充），但禁止重写或干扰系统注入的翻页机制。

====================
十二、打印样式要求
====================

CSS 中必须包含 @media print。

打印要求：

- 每个 .slide 独立分页
- 不显示控制按钮
- 不显示不必要的交互控件
- 保持 16:9 页面比例
- 背景色和卡片尽量保留
- 页面不要被截断

====================
十三、输出格式要求
====================

最终只输出完整 HTML。

不要输出：

- markdown 代码块
- ```html
- 解释说明
- 生成过程
- 额外备注

第一行必须是：

<!DOCTYPE html>

====================
十四、自检要求
====================

输出前请自检：

1. 是否包含完整 HTML 结构？
2. 是否严格生成了 {page_count} 个 class="slide" 页面？
3. 第 1 页是否展示了标题、汇报时间、汇报人？
4. 是否支持键盘翻页？
5. 是否支持触屏滑动？
6. 是否有页码和进度条？
7. 是否有全屏和打印功能？
8. 是否没有依赖外部框架？
9. 内容是否充盈？
10. 是否符合安全生产培训/汇报/展示场景？
11. 是否避免编造具体事实？
12. 是否优先依据文档资料？
"""


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _html_role_model_id() -> str | None:
    roles = config.get("models", {}).get("model_roles", {})
    return roles.get("ppt_gen") or config.get("current_model_id")


def _truncate_context(text: str, limit: int = MAX_HTML_SOURCE_CONTEXT_CHARS) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    head = cleaned[: int(limit * 0.72)].rstrip()
    tail = cleaned[-int(limit * 0.18):].lstrip()
    return f"{head}\n\n[中间内容因长度限制已省略，请优先依据已提供片段，不得编造省略部分细节。]\n\n{tail}"


def build_training_html_prompt(
    title: str,
    report_date: str | None,
    presenter: str | None,
    audience: str | None,
    requirements: str | None,
    page_count: int,
    source_context: str,
) -> str:
    return TRAINING_HTML_PROMPT_TEMPLATE.format(
        title=title.strip(),
        report_date=(report_date or "").strip() or "未填写",
        presenter=(presenter or "").strip() or "未填写",
        audience=(audience or "").strip() or "未填写",
        requirements=(requirements or "").strip() or "未填写",
        page_count=page_count,
        source_context=source_context.strip() or "（无选中文档资料）",
    )


def collect_training_html_source_context(request: TrainingHtmlGenerateRequest) -> str:
    sources = [
        source if isinstance(source, TrainingSourceInput) else TrainingSourceInput(**source.model_dump() if hasattr(source, "model_dump") else dict(source))
        for source in request.sources
        if getattr(source, "type", None) in {"knowledge_base", "wiki_page", "kb_document", "temporary_upload", "prompt"}
    ]
    if not sources and request.document_ids:
        kb_id = request.kb_id or config.get("current_kb_id")
        document_ids = [doc_id for doc_id in request.document_ids if str(doc_id).strip()]
        if not document_ids:
            return ""
        if not kb_id:
            raise ValueError("已选择文档，但当前没有可用知识库")
        sources = [
            TrainingSourceInput(type="kb_document", kb_id=kb_id, document_id=doc_id)
            for doc_id in document_ids
        ]
    if not sources:
        return ""

    pack = build_content_pack(
        {
            "sources": [source.model_dump() for source in sources],
            "topic": request.title,
            "audience": request.audience or "",
            "prefer_wiki_pages": True,
        }
    )
    parts: list[str] = []
    for index, chunk in enumerate(pack.chunks, start=1):
        refs = ", ".join(
            ref.locator or ref.title or ref.document_id or ref.source_type
            for ref in chunk.source_refs
        )
        label = f"资料片段 {index}｜{chunk.title}"
        if refs:
            label = f"{label}｜来源：{refs}"
        parts.append(f"### {label}\n{chunk.text.strip()}")
    return _truncate_context("\n\n".join(parts))


def extract_html_from_model_output(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("模型未返回 HTML 内容")

    fenced = re.search(r"```(?:html|HTML)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    doctype_pos = text.lower().find("<!doctype html")
    html_pos = text.lower().find("<html")
    if doctype_pos >= 0:
        text = text[doctype_pos:]
    elif html_pos >= 0:
        text = "<!DOCTYPE html>\n" + text[html_pos:]

    end_html = text.lower().rfind("</html>")
    if end_html >= 0:
        text = text[: end_html + len("</html>")].strip()

    lowered = text.lower()
    if "<html" not in lowered or "<body" not in lowered or "<style" not in lowered:
        raise ValueError("模型返回内容不是完整 HTML，请重试或减少页数")
    if not lowered.startswith("<!doctype html"):
        text = "<!DOCTYPE html>\n" + text
    return text


def inject_training_html_safety_styles(html: str) -> str:
    """给模型输出加一层轻量的排版修正，避免过小字体和图标压字。"""
    style_block = """
  <style id="training-html-safety">
    :root {
      --training-bg: #eef2ff;
      --training-surface: #f8fafc;
      --training-surface-strong: #ffffff;
      --training-border: rgba(148, 163, 184, 0.24);
      --training-text: #0f172a;
      --training-muted: #475569;
      --training-accent: #4f46e5;
      --training-accent-strong: #3730a3;
      --training-warm: #f97316;
      --training-success: #16a34a;
      --training-warning: #d97706;
      --training-danger: #dc2626;
      --training-shadow: 0 24px 70px rgba(15, 23, 42, 0.14);
      --training-deck-pad-x: clamp(10px, 1.2vw, 18px);
      --training-deck-pad-y: clamp(10px, 1.2vh, 18px);
    }}
    *,
    *::before,
    *::after {
      box-sizing: border-box;
    }}
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      -webkit-text-size-adjust: 100%;
      text-rendering: optimizeLegibility;
    }
    body {
      display: block !important;
      min-height: 100vh;
      overflow-x: hidden;
      overflow-y: auto;
      color: var(--training-text);
      background:
        radial-gradient(circle at top left, rgba(79, 70, 229, 0.12), transparent 24%),
        radial-gradient(circle at bottom right, rgba(249, 115, 22, 0.08), transparent 22%),
        var(--training-bg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    }
    .deck {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: clamp(16px, 2vh, 28px);
      width: 100%;
      min-height: 100vh;
      padding: clamp(16px, 2vh, 28px) var(--training-deck-pad-x) clamp(96px, 10vh, 128px);
      overflow: visible;
    }
    body.training-html-presenting,
    body.training-html-printing {
      overflow: hidden;
    }
    body.training-html-presenting .deck {
      position: fixed;
      inset: 0;
      display: grid;
      place-items: center;
      gap: 0;
      width: auto;
      min-height: 0;
      padding: var(--training-deck-pad-y) var(--training-deck-pad-x);
      overflow: hidden;
    }
    .slide,
    .slide * {
      min-width: 0;
    }
    .slide {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      gap: clamp(10px, 1vw, 18px);
      width: min(
        calc(100vw - (var(--training-deck-pad-x) * 2)),
        calc((100vh - (var(--training-deck-pad-y) * 2)) * 16 / 9)
      );
      height: min(
        calc(100vh - (var(--training-deck-pad-y) * 2)),
        calc((100vw - (var(--training-deck-pad-x) * 2)) * 9 / 16)
      );
      aspect-ratio: 16 / 9;
      padding: clamp(24px, 2.3vw, 42px) clamp(30px, 3vw, 56px) clamp(70px, 6.8vh, 96px);
      border-radius: 0;
      border: 1px solid rgba(255, 255, 255, 0.72);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.98));
      box-shadow: var(--training-shadow);
      overflow: hidden;
      color: var(--training-text);
    }
    body.training-html-presenting .slide {
      display: none !important;
    }
    body.training-html-presenting .slide.active {
      display: flex !important;
    }
    body.training-html-printing .deck {
      display: block !important;
      width: 100% !important;
      height: auto !important;
      padding: 0 !important;
      overflow: visible !important;
    }
    body.training-html-browse .slide {
      width: min(960px, calc(100vw - (var(--training-deck-pad-x) * 2)));
    }
    body.training-html-printing .slide {
      display: flex !important;
      width: 100vw !important;
      height: 56.25vw !important;
      aspect-ratio: 16 / 9 !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      break-after: page;
      page-break-after: always;
    }
    body.training-html-printing .controls,
    body.training-html-printing .progress {
      display: none !important;
    }
    body.training-html-printing,
    body.training-html-printing .deck,
    body.training-html-printing .slide,
    body.training-html-printing .slide * {
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    .slide.dense {
      padding: clamp(20px, 1.9vw, 34px) clamp(24px, 2.2vw, 46px) clamp(58px, 5.6vh, 78px);
      gap: clamp(8px, 0.8vw, 14px);
    }
    .slide.very-dense {
      padding: clamp(16px, 1.6vw, 28px) clamp(20px, 1.9vw, 40px) clamp(50px, 4.8vh, 66px);
      gap: clamp(6px, 0.7vw, 12px);
    }
    .slide.ultra-dense,
    .slide.fit-tight {
      padding: clamp(12px, 1.25vw, 22px) clamp(16px, 1.55vw, 32px) clamp(42px, 4vh, 56px);
      gap: clamp(4px, 0.5vw, 9px);
    }
    .slide :is(p, li, td, th, div, span) {
      overflow-wrap: break-word;
      word-break: break-word;
      text-wrap: pretty;
    }
    .slide img,
    .slide svg {
      max-width: 100%;
      height: auto;
    }
    .slide p,
    .slide ul,
    .slide ol,
    .slide h1,
    .slide h2,
    .slide h3,
    .slide h4,
    .slide h5,
    .slide h6 {
      margin: 0;
    }
    .slide p,
    .slide li {
      font-size: clamp(15px, 1.05vw, 19px) !important;
      line-height: 1.48 !important;
    }
    .slide h1,
    .slide .page-title {
      font-size: clamp(30px, 2.5vw, 44px) !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: clip !important;
    }
    .slide .slide-title {
      font-size: clamp(30px, 2.5vw, 44px) !important;
      font-weight: 900 !important;
      line-height: 1.08 !important;
      color: #111827 !important;
      letter-spacing: 0.01em !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: clip !important;
    }
    .slide h2 {
      font-size: clamp(24px, 2vw, 34px) !important;
    }
    .slide h3,
    .slide .card-title {
      font-size: clamp(18px, 1.35vw, 24px) !important;
    }
    .slide .slide-subtitle,
    .slide .cover-sub,
    .slide .cover-meta,
    .slide .page-core {
      font-size: clamp(16px, 1.05vw, 20px) !important;
      line-height: 1.44 !important;
    }
    .slide .cover-badge,
    .slide .cover-audience {
      white-space: nowrap !important;
    }
    .slide .tag,
    .slide .list-compact li,
    .slide .step-desc,
    .slide .qa-hint,
    .slide .card-body,
    .slide .card-body li,
    .slide .compare-col li,
    .slide .table-wrap td,
    .slide .table-wrap th {
      font-size: clamp(14px, 1vw, 18px) !important;
      line-height: 1.48 !important;
    }
    .slide .meta-note,
    .slide .footnote,
    .slide .caption,
    .slide .subtext {
      font-size: clamp(13px, 0.92vw, 16px) !important;
      line-height: 1.42 !important;
    }
    .slide > :not(.page-title):not(.cover-title):not(.cover-badge):not(.cover-sub):not(.cover-meta):not(.cover-audience):not(.page-core) {
      min-width: 0;
    }
    .slide > div:not(.page-title):not(.cover-title):not(.cover-badge):not(.cover-sub):not(.cover-meta):not(.cover-audience):not(.page-core):not(.content-grid):not(.card):not(.qa-card):not(.table-wrap):not(.compare-wrap):not(.flow-steps):not(.alert-box):not(:empty) {
      max-width: 100%;
      padding: clamp(12px, 1.3vw, 18px);
      border: 1px solid rgba(148, 163, 184, 0.18);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    /* 清除 LLM 在封面输出的装饰性空容器、占位输入框等，避免出现“白色长条” */
    .slide-cover > div:not(.cover-title):not(.cover-badge):not(.cover-sub):not(.cover-meta):not(.cover-audience):not(.page-core):not(.content-grid):not(.card):not(.qa-card):not(.table-wrap):not(.compare-wrap):not(.flow-steps):not(.alert-box),
    .slide-cover > section:not(.cover-title):not(.cover-badge):not(.cover-sub):not(.cover-meta):not(.cover-audience),
    .slide-cover :is(input, textarea, [contenteditable]) {
      background: transparent !important;
      border: 0 !important;
      box-shadow: none !important;
      padding: 0 !important;
      outline: 0 !important;
    }
    .slide :is(div, section, article):empty {
      display: none !important;
      padding: 0 !important;
      border: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
    }
    .slide .content-grid {
      min-height: 0;
      flex: 1 1 auto;
    }
    .content-grid {
      display: grid;
      gap: clamp(12px, 1.4vw, 24px);
      align-items: stretch;
      flex: 1 1 auto;
      min-height: 0;
    }
    .content-grid.cols-2,
    .content-grid.cols-3 {
      align-items: start;
    }
    .content-grid.cols-2 {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .content-grid.two-col {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .content-grid.cols-3 {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .content-grid.three-col {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .content-grid.four-col {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .content-grid.col2 {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .content-grid.col3 {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .content-grid.col4 {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    @media (max-aspect-ratio: 4 / 3) {
      .content-grid.cols-3 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .content-grid.three-col,
      .content-grid.four-col {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    .slide-cover {
      justify-content: center;
      align-items: center;
      background:
        radial-gradient(circle at top right, rgba(79, 70, 229, 0.18), transparent 28%),
        radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.12), transparent 24%),
        linear-gradient(180deg, #ffffff, #f8fafc);
    }
    .slide-cover :is(.cover-badge, .cover-title, .cover-sub, .cover-meta, .cover-audience, .meta-icon) {
      color: #111827 !important;
      text-shadow: none !important;
    }
    .slide-cover .cover-badge {
      background: rgba(79, 70, 229, 0.10);
      color: var(--training-accent-strong) !important;
    }
    .cover-badge {
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(79, 70, 229, 0.08);
      color: var(--training-accent-strong);
      font-size: clamp(14px, 1vw, 18px);
      font-weight: 700;
      letter-spacing: 0.04em;
    }
    .cover-title {
      width: min(72vw, 22em);
      max-width: 100%;
      margin: 12px 0 0;
      font-size: clamp(38px, 3.6vw, 60px) !important;
      line-height: 1.05 !important;
      font-weight: 900;
      color: #111827;
    }
    .cover-sub {
      width: min(60vw, 20em);
      max-width: 100%;
      font-size: clamp(18px, 1.6vw, 26px);
      font-weight: 700;
      line-height: 1.22;
      color: var(--training-accent-strong);
    }
    .cover-meta,
    .cover-audience {
      max-width: 42rem;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 20px;
      align-items: center;
      color: var(--training-muted);
      font-size: clamp(16px, 1.05vw, 20px);
      line-height: 1.4;
    }
    .cover-meta span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .meta-icon {
      font-size: 1.1em;
    }
    .page-title {
      margin: 0;
      font-size: clamp(26px, 2.05vw, 38px);
      line-height: 1.12;
      font-weight: 900;
      color: #111827;
      letter-spacing: 0.01em;
    }
    .page-core {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 12px 16px;
      border-radius: 18px;
      background: rgba(79, 70, 229, 0.06);
      border: 1px solid rgba(79, 70, 229, 0.12);
      color: var(--training-text);
      font-size: clamp(15px, 1vw, 18px);
      line-height: 1.5;
    }
    .core-label {
      flex: 0 0 auto;
      color: var(--training-accent-strong);
      font-weight: 800;
    }
    .card,
    .qa-card,
    .compare-col,
    .compare-item {
      overflow: visible;
    }
    .flow-step,
    .alert-box {
      overflow: hidden;
    }
    .card,
    .qa-card,
    .table-wrap,
    .flow-step,
    .compare-col,
    .compare-item {
      background: var(--training-surface-strong);
      border: 1px solid var(--training-border);
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }
    .card,
    .qa-card,
    .compare-col,
    .compare-item {
      padding: clamp(14px, 1.6vw, 22px);
    }
    .slide.dense .card,
    .slide.dense .qa-card,
    .slide.dense .compare-col,
    .slide.dense .compare-item {
      padding: clamp(12px, 1.3vw, 18px);
    }
    .slide.very-dense .card,
    .slide.very-dense .qa-card,
    .slide.very-dense .compare-col,
    .slide.very-dense .compare-item {
      padding: clamp(10px, 1.1vw, 15px);
    }
    .card-body {
      display: flex;
      flex-direction: column;
      gap: clamp(8px, 0.8vw, 12px);
    }
    .slide.dense .card-body {
      gap: clamp(6px, 0.7vw, 10px);
    }
    .slide.very-dense .card-body {
      gap: clamp(4px, 0.55vw, 8px);
    }
    .card-body > * {
      flex: 0 0 auto;
      margin-top: 0 !important;
    }
    .card-title,
    .qa-q,
    .comp-title,
    .step-label {
      font-weight: 800;
      color: #111827;
      line-height: 1.2;
    }
    .card-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }
    .compare-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
      font-size: clamp(18px, 1.35vw, 24px) !important;
      font-weight: 900;
      color: #111827;
    }
    .card-icon {
      display: inline-flex;
      width: 1.55em;
      align-items: center;
      justify-content: center;
      font-size: 1.05em;
      flex: 0 0 auto;
    }
    .compare-body {
      color: var(--training-muted);
      font-size: clamp(14px, 1vw, 18px);
      line-height: 1.48;
    }
    .card-body,
    .qa-hint,
    .comp-title + ul,
    .compare-body,
    .card-body li,
    .table-wrap td,
    .table-wrap th,
    .alert-box {
      color: var(--training-muted);
      font-size: clamp(15px, 1.02vw, 19px) !important;
      line-height: 1.5 !important;
    }
    .card-body ul,
    .card-body ol,
    .qa-card ul,
    .compare-col ul {
      margin: 0;
      padding-left: 1.2em;
    }
    .card-body li + li,
    .qa-card li + li,
    .compare-col li + li {
      margin-top: 8px;
    }
    .card.info { background: linear-gradient(180deg, rgba(239, 246, 255, 0.95), rgba(255, 255, 255, 0.98)); }
    .card.success { background: linear-gradient(180deg, rgba(236, 253, 245, 0.95), rgba(255, 255, 255, 0.98)); }
    .card.warning { background: linear-gradient(180deg, rgba(255, 247, 237, 0.95), rgba(255, 255, 255, 0.98)); }
    .card.danger { background: linear-gradient(180deg, rgba(254, 242, 242, 0.95), rgba(255, 255, 255, 0.98)); }
    .card.info .card-title { color: #1d4ed8; }
    .card.success .card-title { color: #166534; }
    .card.warning .card-title { color: #b45309; }
    .card.danger .card-title { color: #b91c1c; }
    .alert-box {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: clamp(14px, 1.6vw, 20px);
      border-radius: 20px;
      background: rgba(249, 115, 22, 0.08);
      border: 1px solid rgba(249, 115, 22, 0.16);
    }
    .alert-icon {
      flex: 0 0 auto;
      font-size: 1.35em;
      line-height: 1;
      color: var(--training-warm);
    }
    .table-wrap {
      width: 100%;
      max-height: 100%;
      overflow: hidden;
      padding: 0;
    }
    .table-wrap table {
      width: 100%;
      table-layout: fixed;
      border-collapse: separate;
      border-spacing: 0;
      background: transparent;
    }
    .table-wrap th,
    .table-wrap td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.14);
      vertical-align: top;
      text-align: left;
      word-break: break-word;
      overflow-wrap: break-word;
    }
    .table-wrap th {
      background: linear-gradient(180deg, rgba(79, 70, 229, 0.12), rgba(79, 70, 229, 0.06));
      color: #1e3a8a !important;
      font-weight: 800;
    }
    .table-wrap thead th {
      font-size: clamp(16px, 1.05vw, 19px) !important;
      text-align: center;
      border-bottom: 1px solid rgba(79, 70, 229, 0.16);
    }
    .table-wrap thead th:first-child {
      border-top-left-radius: 18px;
    }
    .table-wrap thead th:last-child {
      border-top-right-radius: 18px;
    }
    .table-wrap tbody tr:nth-child(even) td {
      background: rgba(248, 250, 252, 0.88);
    }
    .table-wrap tbody tr:nth-child(odd) td {
      background: #ffffff;
    }
    .table-wrap tbody td:first-child {
      font-weight: 800;
      color: #111827;
    }
    .flow-steps {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
      gap: clamp(10px, 1vw, 16px);
      align-items: start;
      flex: 1 1 auto;
      min-height: 0;
    }
    .flow-step {
      min-height: 0;
      height: auto;
      padding: 14px 12px;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      gap: 10px;
      text-align: center;
    }
    .step-num {
      width: 42px;
      height: 42px;
      margin: 0 auto;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, var(--training-accent), #7c3aed);
      color: white;
      font-weight: 800;
      box-shadow: 0 10px 24px rgba(79, 70, 229, 0.24);
    }
    .step-desc {
      color: var(--training-muted);
      font-size: clamp(13px, 0.9vw, 17px);
      line-height: 1.45;
    }
    .flow-arrow {
      color: var(--training-accent-strong);
      font-size: clamp(20px, 1.8vw, 30px);
      font-weight: 800;
      text-align: center;
      grid-column: 1 / -1;
      justify-self: center;
      margin: 0.1em 0;
    }
    .compare-wrap {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: clamp(12px, 1.4vw, 20px);
      flex: 1 1 auto;
      min-height: 0;
      align-items: start;
    }
    .compare-col.do {
      border-color: rgba(22, 163, 74, 0.16);
      background: linear-gradient(180deg, rgba(240, 253, 244, 0.96), rgba(255, 255, 255, 0.98));
    }
    .compare-col.dont {
      border-color: rgba(220, 38, 38, 0.16);
      background: linear-gradient(180deg, rgba(254, 242, 242, 0.96), rgba(255, 255, 255, 0.98));
    }
    .comp-title {
      margin-bottom: 12px;
      font-size: clamp(17px, 1.05vw, 22px);
    }
    .comp-title.do {
      color: #15803d;
    }
    .comp-title.dont {
      color: #b91c1c;
    }
    .qa-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .qa-q {
      font-size: clamp(17px, 1.08vw, 22px);
    }
    .qa-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 2.2em;
      margin-right: 8px;
      border-radius: 999px;
      background: rgba(79, 70, 229, 0.1);
      color: var(--training-accent-strong);
      font-weight: 800;
    }
    .qa-hint {
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px dashed rgba(148, 163, 184, 0.24);
    }
    .slide .list-compact li {
      line-height: 1.5 !important;
      font-size: clamp(15px, 1vw, 19px) !important;
    }
    .slide .tag {
      font-size: clamp(13px, 0.9vw, 17px) !important;
    }
    .slide img, .slide svg {
      max-width: 100%;
      height: auto;
    }
    .slide p { margin: 0; }
    .slide ul, .slide ol { margin: 0; }
    .slide h1, .slide h2, .slide h3, .slide h4, .slide h5, .slide h6 { margin: 0; }
    .slide :is(p, li, td, .text, .desc, .note, .caption, .subtext) {
      line-height: 1.5 !important;
    }
    .slide :is(h1, h2, h3, .slide-title, .cover-title) {
      line-height: 1.08 !important;
      letter-spacing: 0.01em !important;
    }
    .slide > :is(h1, .slide-title, .cover-title, .page-title) {
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: clip !important;
    }
    .slide h1 {
      font-size: clamp(30px, 2.8vw, 46px) !important;
      font-weight: 900 !important;
    }
    .slide h2 {
      font-size: clamp(24px, 2.2vw, 36px) !important;
      font-weight: 900 !important;
    }
    .slide h3 {
      font-size: clamp(20px, 1.7vw, 28px) !important;
      font-weight: 800 !important;
    }
    .slide p,
    .slide li {
      font-size: clamp(15px, 1vw, 19px) !important;
    }
    .slide .slide-subtitle,
    .slide .cover-sub,
    .slide .cover-meta {
      line-height: 1.3 !important;
    }
    .slide .cover-sub {
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: clip !important;
    }
    .slide .cover-badge,
    .slide .cover-audience {
      white-space: nowrap !important;
    }
    .slide .alert-box .icon {
      width: 2em !important;
      min-width: 2em !important;
      flex-shrink: 0 !important;
      text-align: center !important;
      line-height: 1 !important;
    }
    .slide .alert-box .text {
      min-width: 0 !important;
    }
    .slide .card[style*="color:#fff"],
    .slide .card[style*="color: #fff"],
    .slide .card[style*="color:#ffffff"],
    .slide .card[style*="color: #ffffff"] {
      color: #ffffff !important;
    }
    .slide .card[style*="color:#fff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color: #fff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color:#ffffff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color: #ffffff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body) {
      color: #ffffff !important;
    }
    .slide.dense h1,
    .slide.dense .slide-title {
      margin-bottom: 14px;
      font-size: clamp(28px, 2.2vw, 38px) !important;
    }
    .slide.dense h2 {
      margin-bottom: 14px;
      font-size: clamp(22px, 1.8vw, 30px) !important;
    }
    .slide.dense h3,
    .slide.dense .card-title {
      margin-bottom: 10px;
      font-size: clamp(17px, 1.2vw, 21px) !important;
    }
    .slide.dense p,
    .slide.dense li {
      font-size: clamp(14px, 0.95vw, 17px) !important;
      line-height: 1.42 !important;
    }
    .slide.dense .page-title {
      font-size: clamp(24px, 1.85vw, 32px) !important;
    }
    .slide.dense .page-core,
    .slide.dense .slide-subtitle,
    .slide.dense .cover-meta {
      font-size: clamp(15px, 0.98vw, 18px) !important;
      line-height: 1.36 !important;
    }
    .slide.dense .content-grid {
      gap: clamp(10px, 1.05vw, 18px);
    }
    .slide.dense .table-wrap th,
    .slide.dense .table-wrap td {
      padding: 12px 14px;
      font-size: clamp(13px, 0.92vw, 16px) !important;
    }
    .slide.dense .flow-step {
      padding: 12px 10px;
    }
    .slide.very-dense h1,
    .slide.very-dense .slide-title {
      margin-bottom: 12px;
      font-size: clamp(24px, 2vw, 34px) !important;
    }
    .slide.very-dense h2 {
      margin-bottom: 12px;
      font-size: clamp(20px, 1.65vw, 28px) !important;
    }
    .slide.very-dense h3,
    .slide.very-dense .card-title {
      margin-bottom: 8px;
      font-size: clamp(15px, 1.05vw, 19px) !important;
    }
    .slide.very-dense p,
    .slide.very-dense li {
      font-size: clamp(13px, 0.88vw, 15px) !important;
      line-height: 1.35 !important;
    }
    .slide.very-dense .page-title {
      font-size: clamp(22px, 1.7vw, 30px) !important;
    }
    .slide.very-dense .page-core,
    .slide.very-dense .slide-subtitle,
    .slide.very-dense .cover-meta {
      font-size: clamp(14px, 0.9vw, 16px) !important;
      line-height: 1.3 !important;
    }
    .slide.very-dense .content-grid {
      gap: clamp(8px, 0.85vw, 14px);
    }
    .slide.very-dense .table-wrap th,
    .slide.very-dense .table-wrap td {
      padding: 10px 12px;
      font-size: clamp(12px, 0.82vw, 14px) !important;
    }
    .slide.very-dense .flow-step {
      padding: 10px 8px;
    }
    .slide.ultra-dense h1,
    .slide.ultra-dense .slide-title,
    .slide.fit-tight h1,
    .slide.fit-tight .slide-title {
      margin-bottom: 10px;
      font-size: clamp(22px, 1.75vw, 30px) !important;
    }
    .slide.ultra-dense h2,
    .slide.fit-tight h2 {
      margin-bottom: 10px;
      font-size: clamp(18px, 1.45vw, 24px) !important;
    }
    .slide.ultra-dense h3,
    .slide.ultra-dense .card-title,
    .slide.fit-tight h3,
    .slide.fit-tight .card-title {
      margin-bottom: 6px;
      font-size: clamp(14px, 0.95vw, 17px) !important;
    }
    .slide.ultra-dense p,
    .slide.ultra-dense li,
    .slide.fit-tight p,
    .slide.fit-tight li {
      font-size: clamp(12px, 0.78vw, 14px) !important;
      line-height: 1.28 !important;
    }
    .slide.ultra-dense .page-title,
    .slide.fit-tight .page-title {
      font-size: clamp(20px, 1.5vw, 27px) !important;
    }
    .slide.ultra-dense .page-core,
    .slide.ultra-dense .slide-subtitle,
    .slide.ultra-dense .cover-meta,
    .slide.fit-tight .page-core,
    .slide.fit-tight .slide-subtitle,
    .slide.fit-tight .cover-meta {
      font-size: clamp(12px, 0.82vw, 15px) !important;
      line-height: 1.24 !important;
    }
    .slide.ultra-dense .card,
    .slide.ultra-dense .qa-card,
    .slide.ultra-dense .compare-col,
    .slide.ultra-dense .compare-item,
    .slide.fit-tight .card,
    .slide.fit-tight .qa-card,
    .slide.fit-tight .compare-col,
    .slide.fit-tight .compare-item {
      padding: clamp(8px, 0.85vw, 12px);
    }
    .slide.ultra-dense .content-grid,
    .slide.fit-tight .content-grid {
      gap: clamp(6px, 0.65vw, 10px);
    }
    .slide.ultra-dense .table-wrap th,
    .slide.ultra-dense .table-wrap td,
    .slide.fit-tight .table-wrap th,
    .slide.fit-tight .table-wrap td {
      padding: 8px 10px;
      font-size: clamp(11px, 0.72vw, 13px) !important;
    }
    /* 防止白底白字：如果卡片同时设了浅色/白色背景及白色文字，则强制转为深色文字 */
    .slide .card[style*="color:#fff"][style*="background:#fff"],
    .slide .card[style*="color: #fff"][style*="background: #fff"],
    .slide .card[style*="color:#ffffff"][style*="background:#ffffff"],
    .slide .card[style*="color: #ffffff"][style*="background: #ffffff"],
    .slide .card[style*="color:#fff"][style*="background:white"],
    .slide .card[style*="color:#ffffff"][style*="background:white"] {
      color: #0f172a !important;
    }
    /* 系统注入的底部控制条/进度条/页码指示器的默认样式，
       避免 LLM 未定义样式时被 safety CSS 渲染为白色卡片或被遮挡 */
    body > .controls {
      position: fixed;
      left: 50%;
      bottom: 18px;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border: 1px solid rgba(148, 163, 184, 0.45);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: 0 12px 32px rgba(15, 23, 42, 0.16);
      z-index: 9999;
    }
    body > .controls button {
      border: 0;
      border-radius: 999px;
      background: #4f46e5;
      color: #ffffff;
      padding: 8px 14px;
      font-size: 14px;
      cursor: pointer;
    }
    body > .controls button:hover {
      background: #4338ca;
    }
    body > .controls .page-indicator {
      min-width: 78px;
      text-align: center;
      font-size: 14px;
      color: #334155;
    }
    body > .progress {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      height: 4px;
      background: rgba(148, 163, 184, 0.28);
      z-index: 9998;
    }
    body > .progress > .progress-bar {
      height: 100%;
      width: 0;
      background: #f97316;
      transition: width 0.25s ease;
    }
    body.training-html-presenting > .controls,
    body.training-html-presenting > .progress,
    body.training-html-printing > .controls,
    body.training-html-printing > .progress,
    :fullscreen .controls,
    :fullscreen .progress {
      display: none !important;
    }
    @page {
      size: 16in 9in;
      margin: 0;
    }
    @media print {
      html,
      body {
        width: 100%;
        height: auto;
        background: #ffffff !important;
        overflow: visible !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
      .deck {
        display: block !important;
        width: 100% !important;
        height: auto !important;
        padding: 0 !important;
      }
      .deck > .slide {
        display: flex !important;
        width: 100vw !important;
        height: 56.25vw !important;
        aspect-ratio: 16 / 9 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        break-after: page;
        page-break-after: always;
      }
      .deck > .slide-cover {
        background: linear-gradient(180deg, #ffffff, #f8fafc) !important;
        background-image:
          radial-gradient(circle at top right, rgba(79, 70, 229, 0.18), transparent 28%),
          radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.12), transparent 24%),
          linear-gradient(180deg, #ffffff, #f8fafc) !important;
      }
      .controls,
      .progress {
        display: none !important;
      }
    }
  </style>
"""
    needle = "</head>"
    if needle not in html:
        return html
    if 'id="training-html-safety"' in html:
        return html
    return html.replace(needle, f"{style_block}\n{needle}", 1)


def _add_unique_classes(tag: Any, additions: list[str]) -> None:
    classes = list(tag.get("class") or [])
    for cls in additions:
        if cls not in classes:
            classes.append(cls)
    tag["class"] = classes


def _normalize_training_layout_classes(soup: BeautifulSoup) -> None:
    alias_map = {
        "col2": ["cols-2", "two-col"],
        "two-column": ["cols-2", "two-col"],
        "two-col": ["cols-2"],
        "col3": ["cols-3", "three-col"],
        "three-column": ["cols-3", "three-col"],
        "three-col": ["cols-3"],
        "col4": ["four-col"],
        "four-column": ["four-col"],
    }
    for tag in soup.find_all(True):
        classes = tag.get("class") or []
        additions: list[str] = []
        for cls in classes:
            additions.extend(alias_map.get(cls, []))
        if additions:
            _add_unique_classes(tag, additions)


def normalize_training_html_structure(html: str) -> str:
    """统一模型 HTML 和后端包装 HTML 的最终页面外壳。"""
    if "</body>" not in html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    if not soup.body:
        return html

    _normalize_training_layout_classes(soup)

    def is_slide_tag(tag: Any) -> bool:
        classes = tag.get("class") or []
        return tag.name in {"section", "div", "main"} and "slide" in classes

    slides = [tag for tag in soup.find_all(is_slide_tag) if tag.find_parent(is_slide_tag) is None]
    if not slides:
        return str(soup)

    deck = next(
        (
            child
            for child in soup.body.find_all(recursive=False)
            if "deck" in (child.get("class") or [])
        ),
        None,
    )
    if deck is None:
        deck = soup.new_tag("main")
        deck["class"] = ["deck"]
        soup.body.insert(0, deck)

    for slide in slides:
        if slide.find_parent(class_="deck") is deck:
            continue
        deck.append(slide.extract())

    shell_classes = {
        "slides-wrapper",
        "slide-wrapper",
        "slides-container",
        "slide-container",
        "presentation",
        "presentation-wrapper",
        "presentation-container",
        "deck-wrapper",
    }
    preserved_classes = {"deck", "controls", "progress", "progress-bar"}
    for child in list(soup.body.find_all(recursive=False)):
        if child is deck or child.name in {"script", "style"}:
            continue
        classes = set(child.get("class") or [])
        if classes & preserved_classes:
            continue
        if child.select_one(".slide"):
            continue
        if classes & shell_classes:
            child.decompose()
            continue
        if child.name in {"div", "section", "main", "article"} and not child.get_text(strip=True):
            child.decompose()

    display_pattern = re.compile(r"display\s*:[^;]+;?", re.IGNORECASE)
    for idx, slide in enumerate(deck.select(".slide")):
        style_attr = slide.get("style")
        if style_attr:
            new_style = display_pattern.sub("", style_attr).strip().rstrip(";").strip()
            if new_style:
                slide["style"] = new_style
            else:
                del slide["style"]

        classes = [cls for cls in (slide.get("class") or []) if cls not in {"active"}]
        if idx == 0:
            classes.append("active")
        slide["class"] = classes

    return str(soup)


def inject_training_html_controls(html: str) -> str:
    """剥离 LLM 自带的底部控件和翻页 JS 后，统一注入标准控制条。

    LLM 经常自己输出 <div class="controls"> 和一套 nextSlide/prevSlide 翻页 JS，
    但翻页 JS 常使用 slide.style.display = 'block'，会被 safety CSS 的
    `.slide:not(.active) { display: none !important }` 覆盖，导致下载后只能看到
    第 1 页且底部按钮位置错乱。这里统一以后端标准实现为准（采用 classList 切换
    active 类，与 safety CSS 兼容）。
    """
    if "</body>" not in html:
        return html

    # 用 BeautifulSoup 剥离 LLM 自带的控件和翻页 JS
    soup = BeautifulSoup(html, "html.parser")

    # 1. 删除底部控制条 / 进度条 / 页码指示器
    for node in soup.select(".controls, .progress, .progress-bar, #pageIndicator, #progressBar"):
        node.decompose()

    # 2. 删除任何包含翻页 / 全屏 / slide 事件绑定的 <script>，避免与注入 JS 冲突
    conflict_pattern = re.compile(
        r"\b(?:nextSlide|prevSlide|showSlide|toggleFullscreen|currentSlide)\b|"
        r"querySelectorAll\s*\(\s*[\'\"]\.slide[\'\"]\)|"
        r"requestFullscreen\s*\(",
        re.IGNORECASE,
    )
    for script in soup.find_all("script"):
        if script.get("src"):
            continue
        text = script.string or script.get_text() or ""
        if conflict_pattern.search(text):
            script.decompose()

    # 3. 清理 .slide 上 LLM 可能写的 inline style="display: ..."，避免被 `!important` 覆盖后锁死
    display_pattern = re.compile(r"display\s*:[^;]+;?", re.IGNORECASE)
    for slide in soup.select(".slide"):
        style_attr = slide.get("style")
        if not style_attr:
            continue
        new_style = display_pattern.sub("", style_attr).strip().rstrip(";").strip()
        if new_style:
            slide["style"] = new_style
        else:
            del slide["style"]

    # 4. 确保第 1 页带 active，其余页去掉 active（避免多页同时显示）
    slides = soup.select(".slide")
    for idx, slide in enumerate(slides):
        classes = slide.get("class") or []
        if idx == 0:
            if "active" not in classes:
                slide["class"] = classes + ["active"]
        else:
            if "active" in classes:
                slide["class"] = [c for c in classes if c != "active"]

    normalized_html = normalize_training_html_structure(str(soup))
    cleaned_html = _apply_density_classes(normalized_html)
    if "</body>" not in cleaned_html:
        return cleaned_html

    controls_block = """
  <div class="controls">
    <button onclick="trainingPrevSlide()">上一页</button>
    <span id="pageIndicator" class="page-indicator">1 / 1</span>
    <button onclick="trainingNextSlide()">下一页</button>
    <button onclick="trainingToggleFullscreen()">全屏</button>
    <button onclick="window.print()">打印</button>
  </div>
  <div class="progress"><div id="progressBar" class="progress-bar"></div></div>
  <script>
    (function () {
      const slides = Array.from(document.querySelectorAll('.slide'));
      const pageIndicator = document.getElementById('pageIndicator');
      const progressBar = document.getElementById('progressBar');
      let currentSlide = 0;

      function isPresenting() {
        return !!document.fullscreenElement;
      }

      function fitAllSlides() {
        slides.forEach((slide) => fitActiveSlide(slide));
      }

      function fitSlideTitles(slide) {
        if (!slide) return;
        slide.querySelectorAll(':scope > h1, :scope > .slide-title, :scope > .cover-title, :scope > .page-title').forEach((title) => {
          if (!title) return;
          if (title.dataset.initialFontSize == null) {
            title.dataset.initialFontSize = getComputedStyle(title).fontSize;
          } else {
            title.style.fontSize = title.dataset.initialFontSize;
          }
          title.style.whiteSpace = 'nowrap';
          title.style.overflow = 'hidden';
          title.style.textOverflow = 'clip';
          const baseSize = Number.parseFloat(title.dataset.initialFontSize);
          if (!Number.isFinite(baseSize) || baseSize <= 0) return;
          const minSize = Math.max(16, baseSize * 0.58);
          let size = baseSize;
          const maxWidth = title.clientWidth || title.parentElement?.clientWidth || slide.clientWidth;
          while (size > minSize && title.scrollWidth > maxWidth) {
            size -= 1;
            title.style.fontSize = `${size}px`;
          }
        });
      }

      function syncModeState() {
        const presenting = isPresenting();
        document.body.classList.toggle('training-html-browse', !presenting);
        document.body.classList.toggle('training-html-presenting', presenting);
        document.body.classList.toggle('training-html-printing', false);
        if (presenting) {
          slides.forEach((slide, i) => slide.classList.toggle('active', i === currentSlide));
          requestAnimationFrame(() => {
            fitActiveSlide(slides[currentSlide]);
            fitSlideTitles(slides[currentSlide]);
          });
        } else {
          requestAnimationFrame(() => {
            fitAllSlides();
            slides.forEach((slide) => fitSlideTitles(slide));
          });
        }
      }

      function rememberInitialDensity(slide) {
        if (slide.dataset.initialDensity != null) return;
        slide.dataset.initialDensity = ['dense', 'very-dense']
          .filter((cls) => slide.classList.contains(cls))
          .join(' ');
      }

      function restoreInitialDensity(slide) {
        rememberInitialDensity(slide);
        slide.classList.remove('dense', 'very-dense', 'ultra-dense', 'fit-tight');
        slide.dataset.initialDensity
          .split(' ')
          .filter(Boolean)
          .forEach((cls) => slide.classList.add(cls));
      }

      function isOverflowing(slide) {
        return slide.scrollHeight > slide.clientHeight + 2 || slide.scrollWidth > slide.clientWidth + 2;
      }

      function fitActiveSlide(slide) {
        if (!slide) return;
        restoreInitialDensity(slide);
        ['dense', 'very-dense', 'ultra-dense', 'fit-tight'].forEach((cls) => {
          if (isOverflowing(slide)) slide.classList.add(cls);
        });
        fitSlideTitles(slide);
      }

      function showSlide(index, options = { scrollIntoView: true }) {
        if (!slides.length) return;
        currentSlide = (index + slides.length) % slides.length;
        slides.forEach((slide, i) => slide.classList.toggle('active', i === currentSlide));
        if (pageIndicator) pageIndicator.textContent = `${currentSlide + 1} / ${slides.length}`;
        if (progressBar) progressBar.style.width = `${((currentSlide + 1) / slides.length) * 100}%`;
        if (isPresenting()) {
          requestAnimationFrame(() => fitActiveSlide(slides[currentSlide]));
        } else if (options.scrollIntoView) {
          slides[currentSlide]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          requestAnimationFrame(() => fitSlideTitles(slides[currentSlide]));
        } else {
          requestAnimationFrame(() => fitSlideTitles(slides[currentSlide]));
        }
      }

      window.trainingNextSlide = function () { showSlide(currentSlide + 1); };
      window.trainingPrevSlide = function () { showSlide(currentSlide - 1); };
      window.trainingToggleFullscreen = function () {
        if (document.fullscreenElement) {
          document.exitFullscreen?.();
        } else {
          const target = document.querySelector('.deck') || document.documentElement;
          target.requestFullscreen?.();
        }
        requestAnimationFrame(syncModeState);
      };

      document.addEventListener('fullscreenchange', syncModeState);
      window.addEventListener('beforeprint', () => {
        document.body.classList.add('training-html-printing');
        document.body.classList.remove('training-html-browse');
        slides.forEach((slide) => slide.classList.remove('active'));
      });
      window.addEventListener('afterprint', () => {
        document.body.classList.remove('training-html-printing');
        syncModeState();
        showSlide(currentSlide, { scrollIntoView: false });
        requestAnimationFrame(() => {
          if (isPresenting()) {
            fitActiveSlide(slides[currentSlide]);
          } else {
            fitAllSlides();
            slides.forEach((slide) => fitSlideTitles(slide));
          }
        });
      });
      syncModeState();
      window.addEventListener('resize', () => {
        requestAnimationFrame(() => {
          if (isPresenting()) {
            fitActiveSlide(slides[currentSlide]);
          } else {
            fitAllSlides();
            slides.forEach((slide) => fitSlideTitles(slide));
          }
        });
      });

      window.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
          event.preventDefault();
          showSlide(currentSlide + 1);
        }
        if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
          event.preventDefault();
          showSlide(currentSlide - 1);
        }
        if (event.key === 'Home') showSlide(0);
        if (event.key === 'End') showSlide(slides.length - 1);
      });

      let startX = null;
      window.addEventListener('touchstart', (event) => {
        startX = event.touches?.[0]?.clientX ?? null;
      }, { passive: true });
      window.addEventListener('touchend', (event) => {
        if (startX == null) return;
        const endX = event.changedTouches?.[0]?.clientX ?? startX;
        const delta = endX - startX;
        if (Math.abs(delta) > 40) {
          if (delta < 0) showSlide(currentSlide + 1);
          else showSlide(currentSlide - 1);
        }
        startX = null;
      }, { passive: true });

      showSlide(0, { scrollIntoView: false });
      requestAnimationFrame(() => {
        fitAllSlides();
        slides.forEach((slide) => fitSlideTitles(slide));
      });
    })();
  </script>
"""
    return cleaned_html.replace("</body>", f"{controls_block}\n</body>", 1)


def _slide_sections_from_text(text: str) -> list[str]:
    soup = BeautifulSoup(text or "", "html.parser")

    def is_slide_tag(tag: Any) -> bool:
        classes = tag.get("class") or []
        return tag.name in {"section", "div"} and "slide" in classes

    slides: list[str] = []
    for tag in soup.find_all(is_slide_tag):
        if tag.find_parent(is_slide_tag) is None:
            slides.append(str(tag))

    if slides:
        return slides

    return re.findall(
        r"<(?:section|div)\b[^>]*class=[\"'][^\"']*\bslide\b[^\"']*[\"'][^>]*>.*?</(?:section|div)>",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )


def _slide_density_level(slide_tag: Any) -> str | None:
    text = re.sub(r"\s+", "", slide_tag.get_text(" ", strip=True))
    if not text:
        return None

    card_count = len(slide_tag.select(".card, .qa-card, .compare-col, .compare-item, .flow-step, .alert-box, .table-wrap"))
    table_count = len(slide_tag.select("table"))
    list_count = len(slide_tag.select("ul, ol"))
    heading_count = len(slide_tag.select("h1, h2, h3"))

    density_score = len(text)
    density_score += card_count * 260
    density_score += table_count * 520
    density_score += list_count * 120
    density_score += heading_count * 60

    if density_score >= 5200:
        return "very-dense"
    if density_score >= 3000:
        return "dense"
    return None


def _apply_density_classes(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for slide in soup.select(".slide"):
        level = _slide_density_level(slide)
        classes = slide.get("class") or []
        classes = [cls for cls in classes if cls not in {"dense", "very-dense"}]
        if level:
            classes.append(level)
        slide["class"] = classes
    return str(soup)


def wrap_slide_fragments_as_html(slide_fragments: list[str], *, title: str) -> str:
    slides = "\n".join(_apply_density_classes(fragment) for fragment in slide_fragments)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --deck-pad-x: clamp(10px, 1.2vw, 18px);
      --deck-pad-y: clamp(10px, 1.2vh, 18px);
      --slide-bg: #f8fafc;
      --slide-text: #0f172a;
      --slide-muted: #334155;
      --slide-border: rgba(148, 163, 184, 0.22);
      --slide-shadow: 0 24px 70px rgba(15, 23, 42, .18);
    }}
    *,
    *::before,
    *::after {{ box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      background: #eef2ff;
      color: var(--slide-text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      overflow-x: hidden;
      overflow-y: auto;
      -webkit-text-size-adjust: 100%;
      text-rendering: optimizeLegibility;
    }}
    .deck {{
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: clamp(16px, 2vh, 28px);
      width: 100%;
      min-height: 100vh;
      padding: clamp(16px, 2vh, 28px) var(--deck-pad-x) clamp(96px, 10vh, 128px);
      overflow: visible;
    }}
    body.training-html-presenting,
    body.training-html-printing {{
      overflow: hidden;
    }}
    body.training-html-presenting .deck {{
      position: fixed;
      inset: 0;
      display: grid;
      place-items: center;
      gap: 0;
      width: auto;
      min-height: 0;
      padding: var(--deck-pad-y) var(--deck-pad-x);
      overflow: hidden;
    }}
    .slide,
    .slide * {{
      min-width: 0;
    }}
    .slide {{
      position: relative;
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      gap: clamp(10px, 1vw, 18px);
      width: min(
        calc(100vw - (var(--deck-pad-x) * 2)),
        calc((100vh - (var(--deck-pad-y) * 2)) * 16 / 9)
      );
      height: min(
        calc(100vh - (var(--deck-pad-y) * 2)),
        calc((100vw - (var(--deck-pad-x) * 2)) * 9 / 16)
      );
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border-radius: 0;
      background: var(--slide-bg);
      color: var(--slide-text);
      box-shadow: var(--slide-shadow);
      padding: clamp(24px, 2.3vw, 42px) clamp(30px, 3vw, 56px) clamp(70px, 6.8vh, 96px);
    }}
    .slide.active {{
      display: flex;
      flex-direction: column;
    }}
    body.training-html-presenting .slide {{
      display: none !important;
    }}
    body.training-html-presenting .slide.active {{
      display: flex !important;
    }}
    body.training-html-printing .deck {{
      display: block !important;
      width: 100% !important;
      height: auto !important;
      padding: 0 !important;
      overflow: visible !important;
    }}
    body.training-html-printing .slide {{
      display: flex !important;
      width: 100vw !important;
      height: 56.25vw !important;
      aspect-ratio: 16 / 9 !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      break-after: page;
      page-break-after: always;
    }}
    body.training-html-printing .controls,
    body.training-html-printing .progress {{
      display: none !important;
    }}
    body.training-html-printing,
    body.training-html-printing .deck,
    body.training-html-printing .slide,
    body.training-html-printing .slide * {{
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}
    .slide.dense {{
      padding: clamp(20px, 1.9vw, 34px) clamp(24px, 2.2vw, 46px) clamp(58px, 5.6vh, 78px);
      gap: clamp(8px, 0.8vw, 14px);
    }}
    .slide.very-dense {{
      padding: clamp(16px, 1.6vw, 28px) clamp(20px, 1.9vw, 40px) clamp(50px, 4.8vh, 66px);
      gap: clamp(6px, 0.7vw, 12px);
    }}
    .slide :is(p, li, td, th, div, span) {{
      overflow-wrap: break-word;
      word-break: break-word;
      text-wrap: pretty;
    }}
    .slide p, .slide li {{
      font-size: clamp(15px, 1.05vw, 19px);
      line-height: 1.48;
      color: var(--slide-muted);
    }}
    .slide h1 {{ margin: 0 0 20px; font-size: clamp(30px, 2.5vw, 44px); line-height: 1.08; color: #111827; font-weight: 900; }}
    .slide .slide-title {{ margin: 0 0 20px; font-size: clamp(30px, 2.5vw, 44px); line-height: 1.08; color: #111827; font-weight: 900; letter-spacing: 0.01em; }}
    .slide h2 {{ margin: 0 0 18px; font-size: clamp(24px, 2vw, 34px); line-height: 1.1; color: #111827; font-weight: 900; }}
    .slide h3 {{ margin: 0 0 14px; font-size: clamp(18px, 1.35vw, 24px); line-height: 1.12; color: #111827; font-weight: 800; }}
    .slide ul, .slide ol {{ padding-left: 1.4em; margin: 0; }}
    .slide p {{ margin: 0; }}
    .slide img, .slide svg {{ max-width: 100%; height: auto; }}
    .slide > h1,
    .slide > .slide-title,
    .slide > .cover-title,
    .slide > .page-title {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: clip;
    }}
    .slide .cover-sub {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: clip;
    }}
    .slide > div:not(.page-title):not(.cover-title):not(.cover-badge):not(.cover-sub):not(.cover-meta):not(.cover-audience):not(.page-core):not(.content-grid):not(.card):not(.qa-card):not(.table-wrap):not(.compare-wrap):not(.flow-steps):not(.alert-box) {{
      max-width: 100%;
      padding: clamp(12px, 1.3vw, 18px);
      border: 1px solid rgba(148, 163, 184, 0.18);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }}
    .content-grid {{
      min-height: 0;
      flex: 1 1 auto;
      display: grid;
      gap: clamp(12px, 1.4vw, 24px);
      align-items: stretch;
    }}
    .content-grid.cols-2,
    .content-grid.cols-3 {{
      align-items: start;
    }}
    .content-grid.cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .content-grid.two-col {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .content-grid.cols-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .content-grid.three-col {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .content-grid.four-col {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    @media (max-aspect-ratio: 4 / 3) {{
      .content-grid.cols-3 {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .content-grid.three-col,
      .content-grid.four-col {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    .card,
    .qa-card,
    .compare-col,
    .compare-item {{
      overflow: visible;
    }}
    .flow-step,
    .alert-box {{
      overflow: hidden;
    }}
    .card,
    .qa-card,
    .compare-col,
    .flow-step,
    .table-wrap,
    .alert-box {{
      border: 1px solid var(--slide-border);
      border-radius: 20px;
      background: white;
      box-shadow: 0 10px 30px rgba(15, 23, 42, .06);
      color: #0f172a;
    }}
    .card,
    .qa-card,
    .compare-col,
    .compare-item {{
      padding: clamp(14px, 1.6vw, 22px);
    }}
    .slide.dense .card,
    .slide.dense .qa-card,
    .slide.dense .compare-col,
    .slide.dense .compare-item {{
      padding: clamp(12px, 1.3vw, 18px);
    }}
    .slide.very-dense .card,
    .slide.very-dense .qa-card,
    .slide.very-dense .compare-col,
    .slide.very-dense .compare-item {{
      padding: clamp(10px, 1.1vw, 15px);
    }}
    .card-body {{
      display: flex;
      flex-direction: column;
      gap: clamp(8px, 0.8vw, 12px);
    }}
    .slide.dense .card-body {{
      gap: clamp(6px, 0.7vw, 10px);
    }}
    .slide.very-dense .card-body {{
      gap: clamp(4px, 0.55vw, 8px);
    }}
    .card-body > * {{
      flex: 0 0 auto;
      margin-top: 0 !important;
    }}
    .card-body,
    .qa-hint,
    .compare-col ul,
    .compare-body,
    .flow-step .step-desc {{
      overflow-wrap: break-word;
      word-break: break-word;
    }}
    .card-body,
    .card-body li,
    .qa-hint,
    .compare-col li,
    .table-wrap td {{
      color: #334155;
      font-size: clamp(14px, 1vw, 18px);
      line-height: 1.48;
    }}
    .card-title,
    .qa-q,
    .comp-title,
    .step-label {{
      font-weight: 800;
      color: #111827;
      line-height: 1.2;
    }}
    .compare-title {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
      font-size: clamp(18px, 1.35vw, 24px) !important;
      font-weight: 900;
      color: #111827;
    }}
    .compare-body {{
      color: var(--slide-muted);
      font-size: clamp(14px, 1vw, 18px);
      line-height: 1.48;
    }}
    .table-wrap {{
      width: 100%;
      max-height: 100%;
      overflow: hidden;
      padding: 0;
    }}
    .table-wrap table {{
      width: 100%;
      table-layout: fixed;
      border-collapse: separate;
      border-spacing: 0;
    }}
    .table-wrap th,
    .table-wrap td {{
      padding: 14px 16px;
      border-bottom: 1px solid rgba(148, 163, 184, .14);
      text-align: left;
      vertical-align: top;
      word-break: break-word;
      overflow-wrap: break-word;
    }}
    .table-wrap th {{
      background: linear-gradient(180deg, rgba(79, 70, 229, 0.12), rgba(79, 70, 229, 0.06));
      color: #1e3a8a;
      font-weight: 800;
    }}
    .table-wrap thead th {{
      font-size: clamp(16px, 1.05vw, 19px);
      text-align: center;
      border-bottom: 1px solid rgba(79, 70, 229, 0.16);
    }}
    .table-wrap thead th:first-child {{
      border-top-left-radius: 18px;
    }}
    .table-wrap thead th:last-child {{
      border-top-right-radius: 18px;
    }}
    .table-wrap tbody tr:nth-child(even) td {{
      background: rgba(248, 250, 252, 0.88);
    }}
    .table-wrap tbody tr:nth-child(odd) td {{
      background: #ffffff;
    }}
    .table-wrap tbody td:first-child {{
      font-weight: 800;
      color: #111827;
    }}
    .flow-steps {{
      display: grid;
      grid-auto-flow: row;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: clamp(10px, 1vw, 16px);
      align-items: start;
      flex: 1 1 auto;
      min-height: 0;
    }}
    .flow-step {{
      min-height: 0;
      height: auto;
      padding: 14px 12px;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      gap: 10px;
      text-align: center;
    }}
    .flow-arrow {{
      color: #3730a3;
      font-size: clamp(20px, 1.8vw, 30px);
      font-weight: 800;
      text-align: center;
      grid-column: 1 / -1;
      justify-self: center;
      margin: 0.1em 0;
    }}
    .compare-wrap {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: clamp(12px, 1.4vw, 20px);
      flex: 1 1 auto;
      min-height: 0;
      align-items: start;
    }}
    .controls {{ position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; border: 1px solid rgba(148, 163, 184, .45); border-radius: 999px; background: rgba(255,255,255,.88); padding: 8px 12px; box-shadow: 0 12px 32px rgba(15,23,42,.16); }}
    .controls button {{ border: 0; border-radius: 999px; background: #4f46e5; color: white; padding: 8px 14px; cursor: pointer; }}
    .page-indicator {{ min-width: 78px; text-align: center; font-size: 14px; color: #334155; }}
    .progress {{ position: fixed; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(148,163,184,.28); }}
    .progress-bar {{ height: 100%; width: 0; background: #f97316; transition: width .25s ease; }}
    body.training-html-presenting .controls,
    body.training-html-presenting .progress,
    body.training-html-printing .controls,
    body.training-html-printing .progress {{
      display: none !important;
    }}
    .slide .card[style*="color:#fff"],
    .slide .card[style*="color: #fff"],
    .slide .card[style*="color:#ffffff"],
    .slide .card[style*="color: #ffffff"] {{
      color: #ffffff !important;
    }}
    .slide .card[style*="color:#fff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color: #fff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color:#ffffff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body),
    .slide .card[style*="color: #ffffff"] :is(p, li, span, div, strong, b, em, .card-title, .card-body) {{
      color: #ffffff !important;
    }}
    .slide.dense h1,
    .slide.dense .slide-title {{
      margin-bottom: 14px;
      font-size: clamp(28px, 2.2vw, 38px) !important;
    }}
    .slide.dense h2 {{
      margin-bottom: 14px;
      font-size: clamp(22px, 1.8vw, 30px) !important;
    }}
    .slide.dense h3,
    .slide.dense .card-title {{
      margin-bottom: 10px;
      font-size: clamp(17px, 1.2vw, 21px) !important;
    }}
    .slide.dense p,
    .slide.dense li {{
      font-size: clamp(14px, 0.95vw, 17px) !important;
      line-height: 1.42 !important;
    }}
    .slide.dense .page-title {{
      font-size: clamp(24px, 1.85vw, 32px) !important;
    }}
    .slide.dense .page-core,
    .slide.dense .slide-subtitle,
    .slide.dense .cover-meta {{
      font-size: clamp(15px, 0.98vw, 18px) !important;
      line-height: 1.36 !important;
    }}
    .slide.dense .content-grid {{
      gap: clamp(10px, 1.05vw, 18px);
    }}
    .slide.dense .table-wrap th,
    .slide.dense .table-wrap td {{
      padding: 12px 14px;
      font-size: clamp(13px, 0.92vw, 16px) !important;
    }}
    .slide.dense .flow-step {{
      padding: 12px 10px;
    }}
    .slide.very-dense h1,
    .slide.very-dense .slide-title {{
      margin-bottom: 12px;
      font-size: clamp(24px, 2vw, 34px) !important;
    }}
    .slide.very-dense h2 {{
      margin-bottom: 12px;
      font-size: clamp(20px, 1.65vw, 28px) !important;
    }}
    .slide.very-dense h3,
    .slide.very-dense .card-title {{
      margin-bottom: 8px;
      font-size: clamp(15px, 1.05vw, 19px) !important;
    }}
    .slide.very-dense p,
    .slide.very-dense li {{
      font-size: clamp(13px, 0.88vw, 15px) !important;
      line-height: 1.35 !important;
    }}
    .slide.very-dense .page-title {{
      font-size: clamp(22px, 1.7vw, 30px) !important;
    }}
    .slide.very-dense .page-core,
    .slide.very-dense .slide-subtitle,
    .slide.very-dense .cover-meta {{
      font-size: clamp(14px, 0.9vw, 16px) !important;
      line-height: 1.3 !important;
    }}
    .slide.very-dense .content-grid {{
      gap: clamp(8px, 0.85vw, 14px);
    }}
    .slide.very-dense .table-wrap th,
    .slide.very-dense .table-wrap td {{
      padding: 10px 12px;
      font-size: clamp(12px, 0.82vw, 14px) !important;
    }}
    .slide.very-dense .flow-step {{
      padding: 10px 8px;
    }}
    @page {{
      size: 16in 9in;
      margin: 0;
    }}
    @media print {{
      html,
      body {{
        width: 100%;
        height: auto;
        background: #ffffff !important;
        overflow: visible !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }}
      .deck {{
        display: block !important;
        width: 100% !important;
        height: auto !important;
        padding: 0 !important;
      }}
      .slide {{
        display: flex !important;
        width: 100vw !important;
        height: 56.25vw !important;
        aspect-ratio: 16 / 9 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        break-after: page;
        page-break-after: always;
      }}
      .slide-cover {{
        background: linear-gradient(180deg, #ffffff, #f8fafc) !important;
        background-image:
          radial-gradient(circle at top right, rgba(79, 70, 229, 0.18), transparent 28%),
          radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.12), transparent 24%),
          linear-gradient(180deg, #ffffff, #f8fafc) !important;
      }}
      .controls,
      .progress {{
        display: none !important;
      }}
    }}
  </style>
</head>
<body>
  <main class="deck">
{slides}
  </main>
  <div class="controls">
    <button onclick="prevSlide()">上一页</button>
    <span id="pageIndicator" class="page-indicator">1 / 1</span>
    <button onclick="nextSlide()">下一页</button>
    <button onclick="toggleFullscreen()">全屏</button>
    <button onclick="window.print()">打印</button>
  </div>
  <div class="progress"><div id="progressBar" class="progress-bar"></div></div>
  <script>
    let currentSlide = 0;
    const slides = Array.from(document.querySelectorAll('.slide'));
    const pageIndicator = document.getElementById('pageIndicator');
    const progressBar = document.getElementById('progressBar');
    function isPresenting() {{
      return !!document.fullscreenElement;
    }}
    function fitAllSlides() {{
      slides.forEach((slide) => fitActiveSlide(slide));
    }}
    function fitSlideTitles(slide) {{
      if (!slide) return;
      slide.querySelectorAll(':scope > h1, :scope > .slide-title, :scope > .cover-title, :scope > .page-title').forEach((title) => {{
        if (!title) return;
        if (title.dataset.initialFontSize == null) {{
          title.dataset.initialFontSize = getComputedStyle(title).fontSize;
        }} else {{
          title.style.fontSize = title.dataset.initialFontSize;
        }}
        title.style.whiteSpace = 'nowrap';
        title.style.overflow = 'hidden';
        title.style.textOverflow = 'clip';
        const baseSize = Number.parseFloat(title.dataset.initialFontSize);
        if (!Number.isFinite(baseSize) || baseSize <= 0) return;
          const minSize = Math.max(16, baseSize * 0.58);
        let size = baseSize;
        const maxWidth = title.clientWidth || title.parentElement?.clientWidth || slide.clientWidth;
        while (size > minSize && title.scrollWidth > maxWidth) {{
          size -= 1;
          title.style.fontSize = `${{size}}px`;
        }}
      }});
    }}
    function rememberInitialDensity(slide) {{
      if (slide.dataset.initialDensity != null) return;
      slide.dataset.initialDensity = ['dense', 'very-dense']
        .filter((cls) => slide.classList.contains(cls))
        .join(' ');
    }}
    function restoreInitialDensity(slide) {{
      rememberInitialDensity(slide);
      slide.classList.remove('dense', 'very-dense', 'ultra-dense', 'fit-tight');
      slide.dataset.initialDensity
        .split(' ')
        .filter(Boolean)
        .forEach((cls) => slide.classList.add(cls));
    }}
    function isOverflowing(slide) {{
      return slide.scrollHeight > slide.clientHeight + 2 || slide.scrollWidth > slide.clientWidth + 2;
    }}
    function fitActiveSlide(slide) {{
      if (!slide) return;
      restoreInitialDensity(slide);
      ['dense', 'very-dense', 'ultra-dense', 'fit-tight'].forEach((cls) => {{
        if (isOverflowing(slide)) slide.classList.add(cls);
      }});
      fitSlideTitles(slide);
    }}
    function syncModeState() {{
      const presenting = isPresenting();
      document.body.classList.toggle('training-html-browse', !presenting);
      document.body.classList.toggle('training-html-presenting', presenting);
      document.body.classList.toggle('training-html-printing', false);
      if (presenting) {{
        slides.forEach((slide, i) => slide.classList.toggle('active', i === currentSlide));
        requestAnimationFrame(() => {{
          fitActiveSlide(slides[currentSlide]);
          fitSlideTitles(slides[currentSlide]);
        }});
      }} else {{
        requestAnimationFrame(() => {{
          fitAllSlides();
          slides.forEach((slide) => fitSlideTitles(slide));
        }});
      }}
    }}
    function showSlide(index, options = {{ scrollIntoView: true }}) {{
      if (!slides.length) return;
      currentSlide = (index + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle('active', i === currentSlide));
      pageIndicator.textContent = `${{currentSlide + 1}} / ${{slides.length}}`;
      progressBar.style.width = `${{((currentSlide + 1) / slides.length) * 100}}%`;
      if (isPresenting()) {{
        requestAnimationFrame(() => {{
          fitActiveSlide(slides[currentSlide]);
          fitSlideTitles(slides[currentSlide]);
        }});
      }} else if (options.scrollIntoView) {{
        slides[currentSlide]?.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        requestAnimationFrame(() => fitSlideTitles(slides[currentSlide]));
      }} else {{
        requestAnimationFrame(() => fitSlideTitles(slides[currentSlide]));
      }}
    }}
    function nextSlide() {{ showSlide(currentSlide + 1); }}
    function prevSlide() {{ showSlide(currentSlide - 1); }}
    function toggleFullscreen() {{ document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }}
    document.addEventListener('fullscreenchange', syncModeState);
    window.addEventListener('beforeprint', () => {{
      document.body.classList.add('training-html-printing');
      document.body.classList.remove('training-html-browse');
      slides.forEach((slide) => slide.classList.remove('active'));
    }});
    window.addEventListener('afterprint', () => {{
      document.body.classList.remove('training-html-printing');
      syncModeState();
      showSlide(currentSlide, {{ scrollIntoView: false }});
      requestAnimationFrame(() => {{
        if (isPresenting()) {{
          fitActiveSlide(slides[currentSlide]);
        }} else {{
          fitAllSlides();
          slides.forEach((slide) => fitSlideTitles(slide));
        }}
      }});
    }});
    syncModeState();
    window.addEventListener('resize', () => {{
      requestAnimationFrame(() => {{
        if (isPresenting()) {{
          fitActiveSlide(slides[currentSlide]);
        }} else {{
          fitAllSlides();
          slides.forEach((slide) => fitSlideTitles(slide));
        }}
      }});
    }});
    document.addEventListener('keydown', (event) => {{
      if (['ArrowRight', 'PageDown', ' '].includes(event.key)) {{ event.preventDefault(); nextSlide(); }}
      if (['ArrowLeft', 'PageUp'].includes(event.key)) {{ event.preventDefault(); prevSlide(); }}
      if (event.key === 'Home') showSlide(0);
      if (event.key === 'End') showSlide(slides.length - 1);
    }});
    let touchStartX = 0;
    document.addEventListener('touchstart', (event) => {{ touchStartX = event.changedTouches[0].clientX; }}, {{ passive: true }});
    document.addEventListener('touchend', (event) => {{
      const dx = event.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 50) dx < 0 ? nextSlide() : prevSlide();
    }}, {{ passive: true }});
    showSlide(0, {{ scrollIntoView: false }});
    requestAnimationFrame(() => {{
      fitAllSlides();
      slides.forEach((slide) => fitSlideTitles(slide));
    }});
  </script>
</body>
</html>"""


def save_training_html_failure(raw: str, *, title: str) -> str:
    from backend.config import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"training_html_failed_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    path = OUTPUT_DIR / filename
    path.write_text(f"TITLE: {title}\n\n{raw}", encoding="utf-8")
    return filename


async def _repair_html_output(raw: str, *, title: str, page_count: int, model_id: str | None) -> str:
    repair_prompt = f"""下面是模型上一次生成的 HTML 汇报材料输出，但它不是完整可运行 HTML。

请基于这份已有输出，修复为完整单文件 HTML。要求：
- 第一行必须是 <!DOCTYPE html>
- 必须包含 <html lang="zh-CN">、<head>、<meta charset="UTF-8">、<style>、<body>、<script>
- 保留已有内容，不要重新发散
- 尽量保持 {page_count} 个 class="slide" 页面
- 修复时顺便收紧版式：避免大面积留白、避免单页内容挤在角落、避免左右栏严重失衡、避免底部内容超出 16:9 边界
- 短句型内容优先单行展示，流程图中的箭头与步骤不要拆成互相分离的孤立列，卡片内不要把正文压到卡片底部留出大块空白
- 同一份材料内的标题字号、正文字号、卡片边距和行距应保持相对统一，不要某些页特别大、某些页特别小
- 不要输出 markdown，不要解释

材料标题：{title}

上一次输出如下：
{raw[:30000]}
"""
    repaired = await _generate_html_with_continuation(
        [
            {"role": "system", "content": "你只输出修复后的完整 HTML，不输出解释。"},
            {"role": "user", "content": repair_prompt},
        ],
        model_id=model_id,
    )
    return extract_html_from_model_output(repaired)


async def _repair_html_slide_count(html: str, *, title: str, page_count: int, model_id: str | None) -> str:
    current_count = count_html_slides(html)
    repair_prompt = f"""下面是一份已经生成出来的 HTML 汇报材料，但页数不符合要求。

请在尽量保留原有主题、视觉风格、封面信息、内容重点和版式结构的基础上，修复为完整单文件 HTML。
要求：
- 第一行必须是 <!DOCTYPE html>
- 必须包含 <html lang="zh-CN">、<head>、<meta charset="UTF-8">、<style>、<body>、<script>
- 必须严格输出 {page_count} 个 class="slide" 页面
- 当前 HTML 只有 {current_count} 页，必须补足到 {page_count} 页
- 如果页面过少，请补充新的实质内容页，不要只重复标题
- 如果页面过多，请合并或删减到目标页数
- 封面必须保留在第 1 页
- 修复时同步检查版式：不要留下大块空白，不要让卡片超出 16:9 页面边界，不要让某些页明显比其他页更松散
- 短句型内容优先单行展示，流程图中的箭头与步骤应连贯排布，不要拆成互相分离的孤立列；卡片内不要把正文压到底部留出大块空白
- 不要输出 markdown，不要输出解释

材料标题：{title}

当前 HTML 如下：
{html[:30000]}
"""
    repaired = await _generate_html_with_continuation(
        [
            {"role": "system", "content": "你只输出修复后的完整 HTML，不输出解释。"},
            {"role": "user", "content": repair_prompt},
        ],
        model_id=model_id,
    )
    return extract_html_from_model_output(repaired)


def count_html_slides(html: str) -> int:
    count = 0
    for class_attr in re.findall(r'class=["\']([^"\']+)["\']', html, flags=re.IGNORECASE | re.DOTALL):
        tokens = class_attr.split()
        if "slide" in tokens:
            count += 1
    return count


def save_training_html_file(
    html: str,
    *,
    title: str | None = None,
    job_id: str | None = None,
) -> tuple[str, str, str]:
    from backend.config import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"training_html_{job_id or time.strftime('%Y%m%d_%H%M%S')}.html"
    path = OUTPUT_DIR / Path(filename).name
    path.write_text(html, encoding="utf-8")
    download_url = f"/api/training/download-html/{filename}"
    if title:
        download_name = build_training_html_download_name(title)
        download_url = f"{download_url}?{urlencode({'download_name': download_name})}"
    preview_url = f"/api/training/preview-html/{filename}"
    return filename, download_url, preview_url


def build_training_html_download_name(title: str, fallback: str = "training-material") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    return f"{cleaned}.html"


async def _generate_html_with_continuation(
    messages: list[dict[str, str]],
    *,
    model_id: str | None,
) -> str:
    """Generate long HTML and continue when the model stops because of length."""
    current_messages = list(messages)
    output_parts: list[str] = []

    for attempt in range(HTML_GENERATION_MAX_CONTINUATIONS + 1):
        part_parts: list[str] = []
        finish_reason: str | None = None
        async for event in llm_service.chat_events(
            current_messages,
            model_id=model_id,
            stream=True,
            temperature=0.45,
            max_tokens=HTML_GENERATION_MAX_TOKENS,
        ):
            if event.get("type") == "chunk":
                content = event.get("content") or ""
                if content:
                    part_parts.append(content)
            elif event.get("type") == "error":
                raise ValueError(event.get("message") or "模型调用失败")
            elif event.get("type") == "done":
                finish_reason = event.get("finish_reason")

        part = "".join(part_parts)
        if part:
            output_parts.append(part)

        if finish_reason not in {"length", "max_tokens"}:
            return "".join(output_parts)

        if attempt >= HTML_GENERATION_MAX_CONTINUATIONS:
            raise ValueError("模型输出达到长度上限，自动续写后仍未完成 HTML。请减少页数或精简文档内容后重试。")

        current_output = "".join(output_parts)
        # 只回传最后一个已闭合 </section> 之后的尾部，减少接下来的输入 token 占用
        last_closed = current_output.rfind("</section>")
        if last_closed >= 0:
            tail = current_output[last_closed + len("</section>"):]
        else:
            tail = current_output
        tail = tail[-800:]
        current_messages = [
            *messages,
            {"role": "assistant", "content": current_output},
            {
                "role": "user",
                "content": (
                    "你的 HTML 输出因为长度限制中断了。请从已输出内容的末尾继续，"
                    "不要重复已经输出的内容，不要重新开始，不要解释，只继续输出剩余 HTML。"
                    f"\n\n已输出末尾：\n{tail}"
                ),
            },
        ]

    return "".join(output_parts)





class TrainingHtmlService:
    async def generate_material(self, request: TrainingHtmlGenerateRequest) -> dict[str, Any]:
        title = request.title.strip()
        if not title:
            raise ValueError("本次材料标题不能为空")

        source_context = collect_training_html_source_context(request)
        prompt = build_training_html_prompt(
            title=title,
            report_date=request.report_date,
            presenter=request.presenter,
            audience=request.audience,
            requirements=request.requirements,
            page_count=request.page_count,
            source_context=source_context,
        )
        model_id = _html_role_model_id()
        raw = await _generate_html_with_continuation(
            [
                {
                    "role": "system",
                    "content": "你只输出完整单文件 HTML 代码，不输出解释、Markdown 或代码块标记。",
                },
                {"role": "user", "content": prompt},
            ],
            model_id=model_id,
        )
        try:
            html = extract_html_from_model_output(raw)
        except ValueError:
            fragments = _slide_sections_from_text(raw)
            if fragments:
                html = wrap_slide_fragments_as_html(fragments, title=title)
            else:
                try:
                    html = await _repair_html_output(raw, title=title, page_count=request.page_count, model_id=model_id)
                except ValueError as exc:
                    failure_file = save_training_html_failure(raw, title=title)
                    preview = re.sub(r"\s+", " ", raw.strip())[:220] or "空输出"
                    raise ValueError(
                        "模型返回内容不是完整 HTML，且自动修复失败。"
                        f"失败原文已保存到 output/{failure_file}。模型输出开头：{preview}"
                    ) from exc
        html = inject_training_html_safety_styles(html)
        slide_count = count_html_slides(html)
        if slide_count != request.page_count:
            try:
                repaired_html = await _repair_html_slide_count(
                    html,
                    title=title,
                    page_count=request.page_count,
                    model_id=model_id,
                )
                html = inject_training_html_safety_styles(repaired_html)
                slide_count = count_html_slides(html)
            except ValueError:
                pass
        html = inject_training_html_controls(html)
        if slide_count != request.page_count:
            logger.warning(
                "HTML material slide count mismatch: expected %s, got %s",
                request.page_count,
                slide_count,
            )
        try:
            filename, download_url, preview_url = save_training_html_file(html, title=title, job_id=request.job_id)
        except TypeError:
            filename, download_url, preview_url = save_training_html_file(html)
        return {
            "title": title,
            "filename": filename,
            "download_url": download_url,
            "preview_url": preview_url,
            "html": html,
            "slide_count": slide_count,
        }



training_html_service = TrainingHtmlService()
