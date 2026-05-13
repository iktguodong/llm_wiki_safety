"""测试 html_llm_planner 的强校验逻辑。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.presentation.html_llm_planner import (
    HtmlGenerationError,
    _check_model_available,
    _extract_json,
    _validate_pages,
    build_html_deck_llm,
)
from backend.services.presentation.html_text_utils import REGISTERED_LAYOUTS
from backend.services.presentation.models import ContentChunk, ContentPack, SourceRef


def _make_pack(chunks: list[ContentChunk] | None = None) -> ContentPack:
    return ContentPack(
        id="cp-test",
        title="测试培训",
        topic="应急处置",
        audience="班组长",
        duration_minutes=30,
        sources=[],
        chunks=chunks or [],
        warnings=[],
    )


def _valid_pages() -> list[dict]:
    return [
        {
            "page_no": 1,
            "layout": "hero",
            "kicker": "Training",
            "chrome": "安全培训",
            "title": "测试封面",
            "subtitle": "班组长培训",
            "summary": "聚焦应急流程",
            "bullets": ["报警", "处置"],
            "notes": "开场页",
            "source_chunk_ids": [],
        },
        {
            "page_no": 2,
            "layout": "agenda",
            "kicker": "Agenda",
            "chrome": "目录",
            "title": "培训大纲",
            "summary": "五步路线",
            "bullets": ["风险", "流程", "复盘"],
            "notes": "",
            "source_chunk_ids": [],
        },
        {
            "page_no": 3,
            "layout": "content",
            "kicker": "Core",
            "chrome": "核心",
            "title": "风险识别",
            "summary": "三大风险场景",
            "bullets": ["火灾", "泄漏", "触电"],
            "notes": "",
            "source_chunk_ids": [],
        },
        {
            "page_no": 4,
            "layout": "workflow",
            "kicker": "Workflow",
            "chrome": "流程",
            "title": "处置步骤",
            "summary": "从发现到闭环",
            "bullets": ["发现", "报警", "处置", "复盘"],
            "notes": "",
            "source_chunk_ids": [],
        },
        {
            "page_no": 5,
            "layout": "summary",
            "kicker": "Takeaway",
            "chrome": "总结",
            "title": "收束与行动",
            "summary": "关键动作清单",
            "bullets": ["确认", "执行", "闭环"],
            "notes": "",
            "source_chunk_ids": [],
        },
    ]


# ── JSON 提取 ────────────────────────────────────────────────────


def test_extract_json_plain_object():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence():
    assert _extract_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_extract_json_nested():
    assert _extract_json('{"pages": [{"title": "a"}]}') == {"pages": [{"title": "a"}]}


def test_extract_json_not_json():
    assert _extract_json("plain text") is None


def test_extract_json_empty():
    assert _extract_json("") is None


# ── 模型可用性 ────────────────────────────────────────────────────


def test_check_model_available_no_model(isolated_training_env):
    """fixture 已清空 providers，应返回 None。"""
    assert _check_model_available() is None


# ── 强校验 ────────────────────────────────────────────────────────


def test_validate_pages_ok():
    pack = _make_pack()
    settings = {"slide_count": 8}
    pages = _validate_pages(_valid_pages(), pack, settings)
    assert len(pages) == 5
    assert pages[0].layout == "hero"
    assert pages[-1].layout == "summary"


def test_validate_pages_too_few():
    pack = _make_pack()
    settings = {"slide_count": 8}
    with pytest.raises(HtmlGenerationError, match="少于"):
        _validate_pages([_valid_pages()[0], _valid_pages()[1]], pack, settings)


def test_validate_pages_too_many():
    pack = _make_pack()
    settings = {"slide_count": 5}
    many = [_valid_pages()[0].copy() for _ in range(10)]
    for i, p in enumerate(many):
        p = dict(p)
        p["title"] = f"p{i}"
    with pytest.raises(HtmlGenerationError, match="超过"):
        _validate_pages(many, pack, settings)


def test_validate_first_not_hero():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], layout="content")
    with pytest.raises(HtmlGenerationError, match="必须为 'hero'"):
        _validate_pages(bad, pack, settings)


def test_validate_last_not_summary():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[-1] = dict(bad[-1], layout="content")
    with pytest.raises(HtmlGenerationError, match="必须为 'summary'"):
        _validate_pages(bad, pack, settings)


def test_validate_unknown_layout():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[2] = dict(bad[2], layout="gallery")
    with pytest.raises(HtmlGenerationError, match="不在登记"):
        _validate_pages(bad, pack, settings)


def test_validate_empty_title():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], title="")
    with pytest.raises(HtmlGenerationError, match="标题为空"):
        _validate_pages(bad, pack, settings)


def test_validate_title_too_long():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], title="这是一个非常长的标题用来测试字数上限限制")
    with pytest.raises(HtmlGenerationError, match="过长"):
        _validate_pages(bad, pack, settings)


def test_validate_emoji_detected():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], title="测试🔥标题")
    with pytest.raises(HtmlGenerationError, match="emoji"):
        _validate_pages(bad, pack, settings)


def test_validate_boilerplate():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], notes="本页目标：讲解应急处置流程")
    with pytest.raises(HtmlGenerationError, match="模板"):
        _validate_pages(bad, pack, settings)


def test_validate_chrome_equals_kicker():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], chrome="相同标签", kicker="相同标签")
    with pytest.raises(HtmlGenerationError, match="相同"):
        _validate_pages(bad, pack, settings)


def test_validate_layout_streak():
    pack = _make_pack()
    settings = {"slide_count": 8}
    # 保持末页为 summary，在中段制造连续 3 个 content
    bad = _valid_pages()
    # page 2(index 1): agenda → content
    bad[1] = dict(bad[1], layout="content", title="正文1")
    # page 3(index 2): content → 保持 content
    bad[2] = dict(bad[2], layout="content", title="正文2")
    # page 4(index 3): workflow → content (形成 content-content-content 连续 3 页)
    bad[3] = dict(bad[3], layout="content", title="正文3")
    with pytest.raises(HtmlGenerationError, match="连续"):
        _validate_pages(bad, pack, settings)


def test_validate_bullets_too_many():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(bad[0], bullets=["a", "b", "c", "d", "e", "f"])
    with pytest.raises(HtmlGenerationError, match="数量"):
        _validate_pages(bad, pack, settings)


def test_validate_bullet_too_long():
    pack = _make_pack()
    settings = {"slide_count": 8}
    bad = _valid_pages()
    bad[0] = dict(
        bad[0],
        bullets=[
            "这是一条非常长的用来测试字数上限限制的bullet超过四十个汉字字符应该就会被拦截了"
        ],
    )
    with pytest.raises(HtmlGenerationError, match="过长"):
        _validate_pages(bad, pack, settings)


# ── 全链路 mock ───────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("backend.services.presentation.html_llm_planner._check_model_available")
@patch("backend.services.presentation.html_llm_planner.llm_service.chat_sync")
async def test_build_html_deck_llm_success(mock_chat_sync, mock_check_model, isolated_training_env):
    mock_check_model.return_value = "fake-model-id"
    mock_chat_sync.return_value = json.dumps(
        {"pages": _valid_pages()}, ensure_ascii=False
    )
    pack = _make_pack(
        [
            ContentChunk(
                id="chunk-1",
                title="来源1",
                text="测试文本内容，围绕应急处置展开。",
                source_refs=[
                    SourceRef(
                        source_type="kb_document",
                        title="测试文档.pdf",
                    )
                ],
                keywords=["应急"],
                chunk_type="raw_document",
            ),
        ]
    )
    settings = {"slide_count": 8, "theme": "ink"}

    deck = await build_html_deck_llm(pack, settings)

    assert deck.style == "magazine"
    assert deck.theme == "ink"
    assert len(deck.pages) == 5
    assert deck.pages[0].layout == "hero"
    assert deck.pages[0].kicker == "Training"
    assert deck.pages[0].chrome == "安全培训"


@pytest.mark.asyncio
@patch("backend.services.presentation.html_llm_planner._check_model_available")
@patch("backend.services.presentation.html_llm_planner.llm_service.chat_sync")
async def test_build_html_deck_llm_failure(mock_chat_sync, mock_check_model, isolated_training_env):
    mock_check_model.return_value = "fake-model-id"
    mock_chat_sync.side_effect = Exception("LLM 超时")
    pack = _make_pack()
    settings = {"slide_count": 8}

    with pytest.raises(HtmlGenerationError, match="LLM"):
        await build_html_deck_llm(pack, settings)
