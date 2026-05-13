from __future__ import annotations

import pytest

import backend.services.training as training_module
from backend.models import TrainingHtmlGenerateRequest


@pytest.mark.asyncio
async def test_training_html_prompt_receives_page_count_and_user_fields(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        captured["messages"] = messages
        captured["model_id"] = model_id
        captured["stream"] = stream
        captured["temperature"] = temperature
        captured["max_tokens"] = max_tokens
        yield {
            "type": "chunk",
            "content": """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>.slide{}</style></head>
<body><section class="slide">1</section><script></script></body></html>""",
        }
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_service.generate_html_material(
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

    prompt = captured["messages"][1]["content"]  # type: ignore[index]
    assert "有限空间作业安全培训" in prompt
    assert "2026年5月" in prompt
    assert "安全管理部" in prompt
    assert "一线作业人员、监护人员、班组长" in prompt
    assert "重点讲清审批流程、通风检测和应急处置。" in prompt
    assert "用户指定页数：\n18 页" in prompt
    assert "必须严格生成 18 个 .slide 页面" in prompt
    assert captured["max_tokens"] == training_module.HTML_GENERATION_MAX_TOKENS
    assert result["slide_count"] == 1


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

    result = await training_module.training_service.generate_html_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=18)
    )

    assert len(calls) == 2
    assert calls[1][-2]["role"] == "assistant"
    assert calls[1][-1]["role"] == "user"
    assert "请从已输出内容的末尾继续" in calls[1][-1]["content"]
    assert result["html"].startswith("<!DOCTYPE html>")
    assert result["slide_count"] == 1


@pytest.mark.asyncio
async def test_training_html_surfaces_llm_api_error(monkeypatch):
    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {"type": "error", "message": "API错误 (400): max_tokens is too large"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)

    with pytest.raises(ValueError, match="max_tokens is too large"):
        await training_module.training_service.generate_html_material(
            TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=18)
        )


@pytest.mark.asyncio
async def test_training_html_wraps_slide_fragments_when_model_omits_shell(monkeypatch):
    async def fake_chat_events(messages, model_id=None, stream=False, temperature=0.7, max_tokens=None):
        yield {"type": "chunk", "content": "<section class=\"slide\"><h1>封面</h1></section><section class=\"slide\"><h2>正文</h2></section>"}
        yield {"type": "done", "finish_reason": "stop"}

    monkeypatch.setattr(training_module.llm_service, "chat_events", fake_chat_events)
    monkeypatch.setattr(training_module, "save_training_html_file", lambda html: ("training_html_test.html", "/api/training/download-html/training_html_test.html", "/api/training/download-html/training_html_test.html"))

    result = await training_module.training_service.generate_html_material(
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

    result = await training_module.training_service.generate_html_material(
        TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=5)
    )

    assert calls == 2
    assert result["slide_count"] == 2


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
        await training_module.training_service.generate_html_material(
            TrainingHtmlGenerateRequest(title="测试", document_ids=[], page_count=5)
        )

    assert saved == {"raw": "我无法生成完整 HTML。", "title": "测试"}
