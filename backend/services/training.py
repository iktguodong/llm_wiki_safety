"""培训生成服务的薄封装。"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from backend.config import config
from backend.models import TrainingHtmlGenerateRequest

from backend.services.llm import llm_service
from backend.services.presentation.content_pack import build_content_pack, normalize_sources
from backend.services.presentation.outline_builder import generate_outline as build_outline
from backend.services.presentation.project_store import create_job, save_content_pack, save_outline, save_quality_report, save_spec
from backend.services.presentation.pptx_renderer import render_presentation
from backend.services.presentation.quality_check import check_presentation
from backend.services.presentation.slide_planner import plan_slides
from backend.services.presentation.safety_templates import get_template

logger = logging.getLogger(__name__)

MAX_HTML_SOURCE_CONTEXT_CHARS = 18000
HTML_GENERATION_MAX_TOKENS = 8192
HTML_GENERATION_MAX_CONTINUATIONS = 4

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

====================
十一、交互功能要求
====================

HTML 内置 JS 必须实现：

1. 当前页索引 currentSlide。
2. showSlide(index) 方法。
3. nextSlide() 方法。
4. prevSlide() 方法。
5. 键盘事件：
   - ArrowRight 下一页
   - PageDown 下一页
   - Space 下一页
   - ArrowLeft 上一页
   - PageUp 上一页
   - Home 第一页
   - End 最后一页
6. 触屏滑动：
   - 左滑下一页
   - 右滑上一页
7. 页码更新。
8. 进度条更新。
9. 全屏按钮。
10. 打印按钮或打印样式支持。

页面底部应有：

- 上一页按钮
- 下一页按钮
- 页码
- 进度条
- 全屏按钮
- 打印按钮

按钮不要喧宾夺主。

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
    kb_id = request.kb_id or config.get("current_kb_id")
    document_ids = [doc_id for doc_id in request.document_ids if str(doc_id).strip()]
    if not document_ids:
        return ""
    if not kb_id:
        raise ValueError("已选择文档，但当前没有可用知识库")

    sources = [
        {
            "type": "kb_document",
            "kb_id": kb_id,
            "document_id": doc_id,
        }
        for doc_id in document_ids
    ]
    pack = build_content_pack(
        {
            "sources": sources,
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
    html, body {
      -webkit-text-size-adjust: 100%;
      text-rendering: optimizeLegibility;
    }
    .slide {
      overflow: hidden !important;
    }
    .slide :is(p, li, td, .text, .desc, .note, .caption, .subtext) {
      line-height: 1.55 !important;
      font-size: clamp(18px, 1.15vw, 24px) !important;
    }
    .slide :is(h1, h2, h3, .slide-title, .cover-title) {
      line-height: 1.08 !important;
      letter-spacing: 0.01em !important;
    }
    .slide .slide-subtitle,
    .slide .cover-sub,
    .slide .cover-meta {
      line-height: 1.3 !important;
    }
    .slide .card,
    .slide .role-card,
    .slide .alert-box {
      padding: clamp(16px, 2vw, 28px) !important;
    }
    .slide .card-grid {
      gap: clamp(12px, 1.4vw, 24px) !important;
    }
    .slide .alert-box {
      gap: 12px !important;
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
    .slide .list-compact li {
      line-height: 1.55 !important;
      font-size: clamp(18px, 1.1vw, 23px) !important;
    }
    .slide .tag {
      font-size: clamp(13px, 0.9vw, 17px) !important;
    }
    .slide img, .slide svg {
      max-width: 100%;
      height: auto;
    }
  </style>
"""
    needle = "</head>"
    if needle not in html:
        return html
    if 'id="training-html-safety"' in html:
        return html
    return html.replace(needle, f"{style_block}\n{needle}", 1)


def _slide_sections_from_text(text: str) -> list[str]:
    return re.findall(
        r"<(?:section|div)\b[^>]*class=[\"'][^\"']*\bslide\b[^\"']*[\"'][^>]*>.*?</(?:section|div)>",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )


def wrap_slide_fragments_as_html(slide_fragments: list[str], *, title: str) -> str:
    slides = "\n".join(slide_fragments)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: #e5e7eb; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; overflow: hidden; }}
    .deck {{ width: 100vw; height: 100vh; display: grid; place-items: center; padding: 28px; }}
    .slide {{ display: none; width: min(1280px, calc(100vw - 56px)); aspect-ratio: 16 / 9; overflow: hidden; border-radius: 28px; background: #f8fafc; box-shadow: 0 24px 70px rgba(15, 23, 42, .18); padding: 64px; }}
    .slide.active {{ display: block; }}
    .slide h1 {{ margin: 0 0 24px; font-size: 46px; line-height: 1.12; color: #1e3a8a; }}
    .slide h2 {{ margin: 0 0 22px; font-size: 38px; line-height: 1.16; color: #1e3a8a; }}
    .slide p, .slide li {{ font-size: 22px; line-height: 1.55; }}
    .slide ul, .slide ol {{ padding-left: 1.4em; }}
    .controls {{ position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; border: 1px solid rgba(148, 163, 184, .45); border-radius: 999px; background: rgba(255,255,255,.88); padding: 8px 12px; box-shadow: 0 12px 32px rgba(15,23,42,.16); }}
    .controls button {{ border: 0; border-radius: 999px; background: #4f46e5; color: white; padding: 8px 14px; cursor: pointer; }}
    .page-indicator {{ min-width: 78px; text-align: center; font-size: 14px; color: #334155; }}
    .progress {{ position: fixed; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(148,163,184,.28); }}
    .progress-bar {{ height: 100%; width: 0; background: #f97316; transition: width .25s ease; }}
    @media print {{
      body {{ background: white; overflow: visible; }}
      .deck {{ display: block; width: auto; height: auto; padding: 0; }}
      .slide {{ display: block !important; width: 100vw; height: 56.25vw; box-shadow: none; border-radius: 0; break-after: page; page-break-after: always; }}
      .controls, .progress {{ display: none; }}
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
    function showSlide(index) {{
      if (!slides.length) return;
      currentSlide = Math.max(0, Math.min(index, slides.length - 1));
      slides.forEach((slide, i) => slide.classList.toggle('active', i === currentSlide));
      pageIndicator.textContent = `${{currentSlide + 1}} / ${{slides.length}}`;
      progressBar.style.width = `${{((currentSlide + 1) / slides.length) * 100}}%`;
    }}
    function nextSlide() {{ showSlide(currentSlide + 1); }}
    function prevSlide() {{ showSlide(currentSlide - 1); }}
    function toggleFullscreen() {{ document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }}
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
    showSlide(0);
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


def count_html_slides(html: str) -> int:
    count = 0
    for class_attr in re.findall(r'class=["\']([^"\']+)["\']', html, flags=re.IGNORECASE | re.DOTALL):
        tokens = class_attr.split()
        if "slide" in tokens:
            count += 1
    return count


def save_training_html_file(html: str) -> tuple[str, str, str]:
    from backend.config import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"training_html_{time.strftime('%Y%m%d_%H%M%S')}.html"
    path = OUTPUT_DIR / Path(filename).name
    path.write_text(html, encoding="utf-8")
    download_url = f"/api/training/download-html/{filename}"
    preview_url = f"/api/training/preview-html/{filename}"
    return filename, download_url, preview_url


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
            stream=False,
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
        tail = current_output[-800:]
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


def _legacy_payload(
    *,
    source_type: Optional[str] = None,
    source_ids: Optional[list[str]] = None,
    topic: str = "",
    audience: str = "",
    duration_minutes: int = 60,
    slide_count: int = 12,
    focus_areas: Optional[list[str]] = None,
    style: str = "standard_training",
    include_quiz: bool = True,
    include_speaker_notes: bool = True,
    job_id: Optional[str] = None,
    template_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "sources": normalize_sources({
            "source_type": source_type,
            "source_ids": source_ids or [],
            "topic": topic,
        }),
        "topic": topic,
        "audience": audience,
        "duration_minutes": duration_minutes,
        "slide_count": slide_count,
        "focus_areas": focus_areas or [],
        "style": style,
        "include_quiz": include_quiz,
        "include_speaker_notes": include_speaker_notes,
        "job_id": job_id,
        "template_id": template_id or style,
    }


class TrainingService:
    async def generate_outline(
        self,
        source_type: Optional[str] = None,
        source_ids: Optional[list[str]] = None,
        topic: str = "",
        audience: str = "一线员工",
        duration: int = 60,
        slide_count: int = 12,
        focus_areas: Optional[list[str]] = None,
        model_id: Optional[str] = None,
        *,
        sources: Optional[list[dict[str, Any]]] = None,
        style: str = "standard_training",
        include_quiz: bool = True,
        include_speaker_notes: bool = True,
        job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload = _legacy_payload(
            source_type=source_type,
            source_ids=source_ids,
            topic=topic,
            audience=audience,
            duration_minutes=duration,
            slide_count=slide_count,
            focus_areas=focus_areas,
            style=style,
            include_quiz=include_quiz,
            include_speaker_notes=include_speaker_notes,
            job_id=job_id,
            template_id=style,
        )
        if sources is not None:
            payload["sources"] = sources
        payload["model_id"] = model_id
        job = create_job("outline", job_id=job_id)
        pack = build_content_pack(payload, job.job_id)
        outline = await build_outline(pack, payload, llm_service)
        save_content_pack(job.job_id, pack.model_dump())
        save_outline(job.job_id, outline.model_dump())
        return outline.model_dump()

    async def generate_ppt(
        self,
        outline: dict[str, Any],
        topic: str,
        audience: str,
        template: str = "standard_training",
        model_id: Optional[str] = None,
        *,
        source_type: Optional[str] = None,
        source_ids: Optional[list[str]] = None,
        duration_minutes: int = 60,
        slide_count: int = 12,
        focus_areas: Optional[list[str]] = None,
        style: str = "standard_training",
        include_quiz: bool = True,
        include_speaker_notes: bool = True,
        job_id: Optional[str] = None,
        sources: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        payload = _legacy_payload(
            source_type=source_type,
            source_ids=source_ids,
            topic=topic,
            audience=audience,
            duration_minutes=duration_minutes,
            slide_count=slide_count,
            focus_areas=focus_areas,
            style=style,
            include_quiz=include_quiz,
            include_speaker_notes=include_speaker_notes,
            job_id=job_id,
            template_id=template,
        )
        if sources is not None:
            payload["sources"] = sources
        job = create_job("generate", job_id=job_id)
        pack = build_content_pack(payload, job.job_id)
        outline_model = outline if hasattr(outline, "model_dump") else outline
        if not isinstance(outline_model, dict):
            outline_model = _as_dict(outline)
        # 保证生成阶段拿到的是结构化大纲
        if outline_model and "sections" in outline_model:
            outline_struct = outline_model
        else:
            outline_struct = (await build_outline(pack, payload, llm_service)).model_dump()
        spec = await plan_slides(outline_struct, pack, {**payload, "template_id": template}, llm_service)
        report = check_presentation(spec, pack, payload)
        render_info = render_presentation(
            spec,
            get_template(template),
            job.job_id,
            include_speaker_notes=include_speaker_notes,
        )
        save_content_pack(job.job_id, pack.model_dump())
        save_outline(job.job_id, outline_struct)
        save_spec(job.job_id, spec.model_dump())
        save_quality_report(job.job_id, report.model_dump())
        return {
            "job_id": job.job_id,
            "status": "completed" if report.passed else "completed_with_warnings",
            "presentation": spec.model_dump(),
            "quality_report": report.model_dump(),
            "download_url": render_info["download_url"],
            "filename": render_info["filename"],
            "notes_download_url": render_info.get("notes_download_url"),
            "notes_filename": render_info.get("notes_filename"),
        }

    async def generate_html_material(self, request: TrainingHtmlGenerateRequest) -> dict[str, Any]:
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
            logger.warning(
                "HTML material slide count mismatch: expected %s, got %s",
                request.page_count,
                slide_count,
            )
        filename, download_url, preview_url = save_training_html_file(html)
        return {
            "title": title,
            "filename": filename,
            "download_url": download_url,
            "preview_url": preview_url,
            "html": html,
            "slide_count": slide_count,
        }


training_service = TrainingService()
