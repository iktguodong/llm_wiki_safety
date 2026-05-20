from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from bs4 import BeautifulSoup

import backend.config as backend_config
import backend.services.training_html as training_module
from backend.models import TrainingHtmlGenerateRequest, TrainingSourceInput
from backend.services.presentation.project_store import save_upload_metadata


@pytest.mark.asyncio
async def test_training_html_prompt_receives_page_count_and_user_fields(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        calls.append(messages)
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(
            title="有限空间作业安全培训",
            report_date="2026年5月",
            presenter="安全管理部",
            audience="一线作业人员、监护人员、班组长",
            requirements="重点讲清审批流程、通风检测和应急处置。",
            document_ids=[],
            page_count=18,
        )
    )

    prompt = calls[0][1]["content"]
    assert "有限空间作业安全培训" in prompt
    assert "2026年5月" in prompt
    assert "安全管理部" in prompt
    assert "一线作业人员、监护人员、班组长" in prompt
    assert "重点讲清审批流程、通风检测和应急处置。" in prompt
    assert "用户指定页数：\n18 页" in prompt
    assert "必须严格生成 18 个 .slide 页面" in prompt
    assert len(calls) == 2
    assert result["slide_count"] == 1


@pytest.mark.asyncio
async def test_training_html_uses_sources_for_temporary_upload(monkeypatch, tmp_path):
    upload_id = "upload-html-test-1"
    upload_file = tmp_path / "source.txt"
    upload_file.write_text("第一段内容。\n\n第二段内容。", encoding="utf-8")
    save_upload_metadata(
        upload_id,
        {
            "upload_id": upload_id,
            "filename": upload_file.name,
            "original_filename": upload_file.name,
            "size": upload_file.stat().st_size,
            "detected_type": "txt",
            "path": str(upload_file),
        },
    )

    calls: list[list[dict[str, str]]] = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        calls.append(messages)
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(
            title="测试",
            sources=[TrainingSourceInput(type="temporary_upload", upload_id=upload_id)],
            document_ids=[],
            page_count=5,
        )
    )

    prompt = calls[0][1]["content"]
    assert "第一段内容" in prompt
    assert len(calls) == 2
    assert result["slide_count"] == 1


@pytest.mark.asyncio
async def test_training_html_reports_progress(monkeypatch):
    progress_calls: list[str] = []
    received_job_ids: list[str | None] = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    def fake_update_job_progress(job_id, message):
        if job_id:
            progress_calls.append(message)

    def fake_collect_training_html_source_context(request, job_id=None):
        received_job_ids.append(job_id)
        return "资料内容"

    monkeypatch.setattr(training_module, "update_job_progress", fake_update_job_progress)
    monkeypatch.setattr(training_module, "collect_training_html_source_context", fake_collect_training_html_source_context)
    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "count_html_slides", lambda html: 5)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(
            title="测试",
            document_ids=[],
            page_count=5,
            job_id="html-job-1",
        )
    )

    assert received_job_ids == ["html-job-1"]
    assert progress_calls[0] == "正在解析文档/输入..."
    assert "正在生成网页..." in progress_calls
    assert any(msg.startswith("正在生成网页（第 1/3 轮）") for msg in progress_calls)
    assert "正在修复网页结构..." in progress_calls
    assert "正在检查网页页数..." in progress_calls
    assert "正在保存网页文件..." in progress_calls
    assert result["slide_count"] == 5


def test_training_html_download_name_uses_title(monkeypatch, tmp_path):
    monkeypatch.setattr(backend_config, "OUTPUT_DIR", tmp_path)

    filename, download_url, preview_url = training_module.save_training_html_file(
        "<html></html>",
        title="相关方安全管理专题培训",
        job_id="abc123",
    )

    assert filename == "training_html_abc123.html"
    assert preview_url.endswith("/api/training/preview-html/training_html_abc123.html")
    parsed = urlsplit(download_url)
    assert parsed.path == "/api/training/download-html/training_html_abc123.html"
    assert parse_qs(parsed.query)["download_name"][0] == "相关方安全管理专题培训.html"
    assert (tmp_path / filename).exists()


def test_count_html_slides_only_counts_real_slide_containers():
    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><style>.slide-title{color:red}.slide-subtitle{color:blue}</style></head>
<body>
  <div class="slide cover active"></div>
  <div class="slide-title">标题</div>
  <div class="slide-subtitle">副标题</div>
  <section class="slide">正文</section>
</body>
</html>
"""

    assert training_module.count_html_slides(html) == 2


def test_slide_fragment_extraction_keeps_top_level_siblings():
    raw = """
<section class="slide"><div class="slide-inner"><h1>封面</h1><div><p>介绍</p></div></div></section>
<section class="slide"><div class="slide-inner"><h2>正文</h2><div><ul><li>要点</li></ul></div></div></section>
"""

    fragments = training_module._slide_sections_from_text(raw)

    assert len(fragments) == 2
    assert all(fragment.startswith("<section") for fragment in fragments)

    wrapped = training_module.wrap_slide_fragments_as_html(fragments, title="测试")
    soup = BeautifulSoup(wrapped, "html.parser")

    assert len(soup.select(".deck > .slide")) == 2


def test_training_html_safety_styles_add_layout_defaults():
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head><body></body></html>"""

    injected = training_module.inject_training_html_safety_styles(html)

    assert 'id="training-html-safety"' in injected
    assert "display: block !important;" in injected
    assert ".content-grid.cols-2" in injected
    assert ".content-grid.col4" in injected
    assert ".card-title" in injected
    assert "body.training-html-presenting .slide.active" in injected
    assert "white-space: nowrap !important;" in injected
    assert "size: 338.7mm 190.5mm;" in injected
    assert "@media print" in injected
    assert "body.training-html-printing .slide" in injected
    assert "body.training-html-printing .slide *" in injected
    assert "width: 338.7mm !important;" in injected
    assert "height: 190.5mm !important;" in injected
    assert ".compare-wrap" in injected
    assert "body.training-html-presenting > .controls" in injected


@pytest.mark.asyncio
async def test_training_html_auto_continues_when_model_hits_length(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        calls.append(messages)
        if len(calls) == 1:
            yield {
                "type": "chunk",
                "content": "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"><style>.slide{}</style></head><body>",
            }
            yield {"type": "done", "finish_reason": "length"}
            return
        yield {"type": "chunk", "content": "<section class=\"slide\">1</section><script></script></body></html>"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=18)
    )

    assert len(calls) == 3
    assert calls[1][-2]["role"] == "assistant"
    assert calls[1][-1]["role"] == "user"
    assert "请从已输出内容的末尾继续" in calls[1][-1]["content"]
    assert "必须严格输出 18 个 class=\"slide\" 页面" in calls[2][-1]["content"]
    assert result["html"].startswith("<!DOCTYPE html>")
    assert result["slide_count"] == 1


@pytest.mark.asyncio
async def test_training_html_surfaces_llm_api_error(monkeypatch):
    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {"type": "error", "message": "API错误 (400): max_tokens is too large"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)

    with pytest.raises(ValueError, match="max_tokens is too large"):
        await training_module.training_html_service.generate_material(
            TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=18)
        )


@pytest.mark.asyncio
async def test_training_html_wraps_slide_fragments_when_model_omits_shell(monkeypatch):
    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {"type": "chunk", "content": "<section class=\"slide\"><h1>封面</h1></section><section class=\"slide\"><h2>正文</h2></section>"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=5)
    )

    assert result["html"].startswith("<!DOCTYPE html>")
    assert "<style>" in result["html"]
    assert "<script>" in result["html"]
    assert result["slide_count"] == 2


@pytest.mark.asyncio
async def test_training_html_repairs_plain_non_html_output(monkeypatch):
    calls = 0

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {"type": "chunk", "content": "第1页：封面。第2页：正文。"}
            yield {"type": "done", "finish_reason": "stop"}
            return
        assert "修复为完整单文件 HTML" in messages[-1]["content"]
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><section class="slide">2</section><script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=5)
    )

    assert calls == 3
    assert result["slide_count"] == 2


@pytest.mark.asyncio
async def test_training_html_repairs_slide_count_mismatch(monkeypatch):
    calls = 0

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        nonlocal calls
        calls += 1
        if calls == 1:
          yield {
              "type": "chunk",
              "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><section class="slide">2</section><section class="slide">3</section><script></script></body></html>""",
          }
          yield {"type": "done", "finish_reason": "stop"}
          return
        assert "必须严格输出 15 个 class=\"slide\" 页面" in messages[-1]["content"]
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body>""" + "".join(f"<section class=\"slide\">{i}</section>" for i in range(1, 16)) + """<script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_html_service.generate_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=15)
    )

    assert calls == 2
    assert result["slide_count"] == 15


@pytest.mark.asyncio
async def test_training_html_saves_failed_raw_when_repair_fails(monkeypatch):
    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {"type": "chunk", "content": "我无法生成完整 HTML。"}
        yield {"type": "done", "finish_reason": "stop"}

    saved: dict[str, str] = {}

    def fake_save_failure(raw: str, *, title: str) -> str:
        saved["raw"] = raw
        saved["title"] = title
        return "training_html_failed_test.txt"

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_failure", fake_save_failure)

    with pytest.raises(ValueError, match="training_html_failed_test.txt"):
        await training_module.training_html_service.generate_material(
            TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=5)
        )

    assert saved == {"raw": "我无法生成完整 HTML。", "title": "测试"}


def test_inject_training_html_controls_replaces_llm_provided_controls():
    """LLM 自带一套控制条和翻页 JS 时，注入后应覆盖为标准实现，且只有一组 controls。"""
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body>
  <section class="slide" style="display: block">1</section>
  <section class="slide" style="display: none">2</section>
  <div class="controls">
    <button onclick="prevSlide()">上一页</button>
    <span id="pageIndicator">1/2</span>
    <button onclick="nextSlide()">下一页</button>
  </div>
  <div class="progress"><div id="progressBar" class="progress-bar"></div></div>
  <script>
    const slides = document.querySelectorAll('.slide');
    function nextSlide() { /* LLM 的翻页逻辑 */ }
    function prevSlide() {}
  </script>
</body></html>"""

    result = training_module.inject_training_html_controls(html)

    # 最终 HTML 包含标准注入的函数名
    assert "trainingPrevSlide" in result
    assert "trainingNextSlide" in result
    assert "trainingToggleFullscreen" in result

    # 只有一组 controls / progress
    assert result.count('class="controls"') == 1
    assert result.count('class="progress"') == 1

    # LLM 自带的 nextSlide / prevSlide 函数定义已被剥离
    assert "function nextSlide" not in result
    assert "function prevSlide" not in result
    assert "window.print()" in result
    assert "training-html-browse" in result
    assert "training-html-presenting" in result
    assert "training-html-printing" in result
    assert "beforeprint" in result
    assert "afterprint" in result
    assert "scrollIntoView" in result
    assert "fitSlideTitles" in result

    # .slide 上的 inline display 已被清理
    assert 'style="display: block"' not in result
    assert 'style="display: none"' not in result

    # 第 1 页带上 active
    soup = BeautifulSoup(result, "html.parser")
    slides = soup.select(".slide")
    assert len(slides) == 2
    assert "active" in (slides[0].get("class") or [])
    assert "active" not in (slides[1].get("class") or [])
    assert len(soup.select("body > .deck > .slide")) == 2


def test_normalize_training_html_structure_wraps_slides_and_aliases_columns():
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body>
  <section class="slide active">1</section>
  <section class="slide">2<div class="content-grid col4"><div class="card">A</div></div></section>
  <div class="controls">old</div>
</body></html>"""

    result = training_module.normalize_training_html_structure(html)
    soup = BeautifulSoup(result, "html.parser")

    assert len(soup.select("body > .deck > .slide")) == 2
    assert len(soup.select("body > .controls")) == 1
    grid_classes = soup.select_one(".content-grid").get("class")
    assert "col4" in grid_classes
    assert "four-col" in grid_classes


def test_normalize_training_html_structure_removes_empty_original_shell():
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body>
  <div class="slides-wrapper">
    <section class="slide active">1</section>
    <section class="slide">2</section>
  </div>
</body></html>"""

    result = training_module.normalize_training_html_structure(html)
    soup = BeautifulSoup(result, "html.parser")

    assert len(soup.select("body > .deck > .slide")) == 2
    assert not soup.select("body > .slides-wrapper")


def test_training_html_safety_styles_avoid_default_card_clipping():
    injected = training_module.inject_training_html_safety_styles(
        """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head><body></body></html>"""
    )

    assert ".card,\n    .qa-card,\n    .compare-col,\n    .compare-item {\n      overflow: visible;" in injected
    assert ".flow-step,\n    .alert-box {\n      overflow: hidden;" in injected


def test_training_html_safety_styles_guard_cover_and_empty_div():
    """safety CSS 必须包含封面空容器保护、空 div 隐藏、以及标准 .controls 定义。"""
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head><body></body></html>"""

    injected = training_module.inject_training_html_safety_styles(html)

    # 封面页非白名单 div 的装饰被取消
    assert ".slide-cover > div" in injected
    assert ".slide-cover :is(input, textarea, [contenteditable])" in injected

    # 空 div / section 被隐藏
    assert ".slide :is(div, section, article):empty" in injected

    # 底部标准控制条样式
    assert "body > .controls" in injected
    assert "body > .progress" in injected
    assert "z-index: 9999" in injected

    # 原有卡片兑底规则加上了 :not(:empty)
    assert ":not(.alert-box):not(:empty)" in injected
