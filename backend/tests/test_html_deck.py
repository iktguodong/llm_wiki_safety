"""测试 HTML Deck 渲染与 LLM 规划链路。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app import app
from backend.services.presentation.html_deck import (
    HtmlDeckPage,
    HtmlDeckSpec,
    render_html_deck,
)
from backend.services.presentation.models import ContentChunk, ContentPack, SourceRef
from backend.services.presentation.project_store import get_job_paths


def _make_source_refs(title: str) -> list[SourceRef]:
    return [
        SourceRef(
            source_type="kb_document",
            source_id="doc-1",
            kb_id="kb-1",
            document_id="doc-1",
            title=title,
            locator="page 1",
            excerpt="abc",
            confidence=0.9,
        ),
    ]


def _make_content_pack() -> ContentPack:
    return ContentPack(
        id="cp-html-1",
        title="危化品仓库应急处置培训",
        topic="请突出应急处置、报警流程和初期火灾扑救",
        audience="设备部班组长",
        duration_minutes=30,
        sources=[],
        chunks=[
            ContentChunk(
                id="chunk-1",
                title="来源1",
                text="应急处置要先报警，再组织现场隔离和初期灭火。发生险情后先切断风险源。",
                source_refs=_make_source_refs("应急预案.pdf"),
                keywords=["应急", "报警", "处置", "火灾"],
                chunk_type="raw_document",
            ),
            ContentChunk(
                id="chunk-2",
                title="来源2",
                text="发生险情后，要先切断风险源，再按流程上报并复盘闭环。",
                source_refs=_make_source_refs("操作规程.docx"),
                keywords=["流程", "上报", "复盘", "闭环"],
                chunk_type="raw_document",
            ),
        ],
        warnings=[],
    )


def _valid_llm_response() -> str:
    """返回一份合法的 LLM JSON 输出。"""
    return json.dumps(
        {
            "pages": [
                {
                    "page_no": 1,
                    "layout": "hero",
                    "kicker": "Training · 2026",
                    "chrome": "安全培训",
                    "title": "危化品仓库应急处置",
                    "subtitle": "设备部班组长",
                    "summary": "聚焦报警流程与初期火灾扑救",
                    "bullets": ["报警先行", "现场隔离", "初期灭火"],
                    "notes": "开场即抓住关键动作",
                    "source_chunk_ids": ["chunk-1"],
                },
                {
                    "page_no": 2,
                    "layout": "agenda",
                    "kicker": "Agenda",
                    "chrome": "目录",
                    "title": "培训路线图",
                    "subtitle": "",
                    "summary": "先讲风险，再讲流程，最后落到执行",
                    "bullets": ["风险识别", "报警与处置", "复盘闭环"],
                    "notes": "",
                    "source_chunk_ids": ["chunk-1", "chunk-2"],
                },
                {
                    "page_no": 3,
                    "layout": "content",
                    "kicker": "Core",
                    "chrome": "核心内容",
                    "title": "风险识别要点",
                    "subtitle": "",
                    "summary": "仓库常见风险场景与识别方法",
                    "bullets": ["化学品泄漏", "明火作业风险", "设备老化隐患"],
                    "notes": "重点讲三方面风险",
                    "source_chunk_ids": ["chunk-2"],
                },
                {
                    "page_no": 4,
                    "layout": "workflow",
                    "kicker": "Workflow",
                    "chrome": "流程",
                    "title": "报警与处置流程",
                    "subtitle": "",
                    "summary": "从发现险情到完成上报的标准步骤",
                    "bullets": ["切断风险源", "报警上报", "初期灭火", "人员疏散", "复盘闭环"],
                    "notes": "五步走，缺一不可",
                    "source_chunk_ids": ["chunk-1"],
                },
                {
                    "page_no": 5,
                    "layout": "summary",
                    "kicker": "Takeaway",
                    "chrome": "总结",
                    "title": "收束与行动",
                    "subtitle": "",
                    "summary": "落到岗位、班组、现场三个层级",
                    "bullets": ["确认风险点", "走通上报路径", "检查控制措施到位"],
                    "notes": "把关键动作带走",
                    "source_chunk_ids": ["chunk-2"],
                },
            ]
        },
        ensure_ascii=False,
    )


# ── 渲染测试（不需要 LLM）───────────────────────────────────────


def test_html_deck_rendering_hero_and_quote(isolated_training_env):
    """验证 hero 页不再重复显示 notes、quote 页 summary 不等于 title。"""
    pages = [
        HtmlDeckPage(
            id="p1",
            page_no=1,
            layout="hero",
            title="测试封面",
            subtitle="培训对象描述",
            summary="这是封面概述",
            bullets=["要点1", "要点2"],
            notes="这段 notes 不应出现在右侧 hero-aside",
            kicker="Training · 2026",
            chrome="安全培训",
            hero=True,
        ),
        HtmlDeckPage(
            id="p2",
            page_no=2,
            layout="quote",
            title="关键摘录标题",
            summary="关键摘录的正文内容不应等于标题",
            notes="quote 页的提醒说明，出现在 aside 中",
            kicker="Takeaway",
            chrome="要点",
        ),
    ]
    deck = HtmlDeckSpec(
        id="test-render",
        title="测试",
        topic="测试",
        audience="班组长",
        duration_minutes=30,
        style="magazine",
        theme="ink",
        template_id="magazine",
        pages=pages,
        quality_warnings=[],
    )

    render_info = render_html_deck(deck, "html-test-render")
    html_text = Path(render_info["html_path"]).read_text(encoding="utf-8")

    # hero: notes 不应出现在 hero-aside（现在是本页要点 mini-card）
    assert "这段 notes 不应出现在右侧 hero-aside" not in html_text
    # hero: sidebar 应有 "本页要点" 标签
    assert "本页要点" in html_text
    # quote: summary 出现在 quote-body，不应兜底成 title
    assert "关键摘录的正文内容不应等于标题" in html_text
    # quote: notes 出现在 aside
    assert "quote 页的提醒说明" in html_text


def test_html_deck_chrome_kicker_fields(isolated_training_env):
    """验证 kicker/chrome 字段正确渲染。"""
    pages = [
        HtmlDeckPage(
            id="p1",
            page_no=1,
            layout="hero",
            title="测试页",
            subtitle="副标题",
            summary="概述",
            kicker="定制钩子",
            chrome="定制栏目",
            hero=True,
        ),
        HtmlDeckPage(
            id="p2",
            page_no=2,
            layout="agenda",
            title="目录页",
            kicker="定制大纲",
            chrome="定制导航",
        ),
    ]
    deck = HtmlDeckSpec(
        id="test-chrome-kicker",
        title="测试",
        topic="测试",
        audience="测试",
        duration_minutes=30,
        style="magazine",
        theme="ink",
        template_id="magazine",
        pages=pages,
        quality_warnings=[],
    )

    render_info = render_html_deck(deck, "html-test-chrome-kicker")
    html_text = Path(render_info["html_path"]).read_text(encoding="utf-8")

    assert "定制钩子" in html_text
    assert "定制栏目" in html_text
    assert "定制大纲" in html_text
    assert "定制导航" in html_text


# ── LLM 规划测试 ──────────────────────────────────────────────────


def test_html_route_requires_llm(isolated_training_env):
    """未配置模型时应返回 400。"""
    client = TestClient(app)
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "应急培训"}],
            "topic": "测试",
            "audience": "班组长",
            "duration_minutes": 30,
            "render_style": "magazine",
            "theme": "ink",
        },
    )
    assert resp.status_code == 400
    assert "未配置" in resp.json()["detail"] or "模型" in resp.json()["detail"]


@patch("backend.services.presentation.html_llm_planner._check_model_available")
@patch("backend.services.presentation.html_llm_planner.llm_service.chat_sync")
def test_html_deck_full_pipeline_with_mock_llm(
    mock_chat_sync, mock_check_model, isolated_training_env
):
    """用 mock LLM 跑完整链路：规划 → 渲染 → 下载。"""
    mock_check_model.return_value = "fake-model-id"
    mock_chat_sync.return_value = _valid_llm_response()

    client = TestClient(app)
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "应急培训"}],
            "topic": "危化品仓库应急处置培训",
            "audience": "设备部班组长",
            "duration_minutes": 30,
            "slide_count": 8,
            "style": "standard_training",
            "render_style": "magazine",
            "theme": "ink",
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["filename"] == "index.html"
    assert data["download_url"].endswith("/index.html")

    deck = data["deck"]
    assert deck["audience"] == "设备部班组长"
    assert len(deck["pages"]) == 5
    assert deck["pages"][0]["layout"] == "hero"
    assert deck["pages"][-1]["layout"] == "summary"

    # 验证 kicker/chrome 字段透传
    page0 = deck["pages"][0]
    assert "kicker" in page0
    assert "chrome" in page0

    # 验证 HTML 文件已生成且可下载
    job_id = data["job_id"]
    html_file = get_job_paths(job_id).html_dir / "index.html"
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert '<section class="slide' in html_text
    assert "危化品仓库应急处置" in html_text

    download_resp = client.get(f"/api/training/download-html/{job_id}/index.html")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("text/html")


@patch("backend.services.presentation.html_llm_planner._check_model_available")
@patch("backend.services.presentation.html_llm_planner.llm_service.chat_sync")
def test_html_deck_llm_validation_errors(mock_chat_sync, mock_check_model, isolated_training_env):
    """验证 LLM 返回违规 JSON 时正确报错。"""
    mock_check_model.return_value = "fake-model-id"

    client = TestClient(app)

    # 空内容
    mock_chat_sync.return_value = ""
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "测试"}],
            "topic": "测试",
            "audience": "测试",
            "render_style": "magazine",
            "theme": "ink",
        },
    )
    assert resp.status_code == 400
    assert "空" in resp.json()["detail"]

    # 非 JSON
    mock_chat_sync.return_value = "这是普通文本，不是 JSON"
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "测试"}],
            "topic": "测试",
            "audience": "测试",
            "render_style": "magazine",
            "theme": "ink",
        },
    )
    assert resp.status_code == 400
    assert "JSON" in resp.json()["detail"]

    # 首页非 hero
    mock_chat_sync.return_value = json.dumps(
        {
            "pages": [
                {
                    "layout": "content",
                    "title": "非封面首页",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "agenda",
                    "title": "目录",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "content",
                    "title": "正文1",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "content",
                    "title": "正文2",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "summary",
                    "title": "收束",
                    "summary": "a",
                    "bullets": ["a"],
                },
            ]
        },
        ensure_ascii=False,
    )
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "测试"}],
            "topic": "测试",
            "audience": "测试",
            "render_style": "magazine",
            "theme": "ink",
        },
    )
    assert resp.status_code == 400
    assert "hero" in resp.json()["detail"].lower()

    # emoji
    mock_chat_sync.return_value = json.dumps(
        {
            "pages": [
                {
                    "layout": "hero",
                    "title": "测试🔥封面",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "agenda",
                    "title": "目录",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "content",
                    "title": "正文1",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "content",
                    "title": "正文2",
                    "summary": "a",
                    "bullets": ["a"],
                },
                {
                    "layout": "summary",
                    "title": "收束",
                    "summary": "a",
                    "bullets": ["a"],
                },
            ]
        },
        ensure_ascii=False,
    )
    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "测试"}],
            "topic": "测试",
            "audience": "测试",
            "render_style": "magazine",
            "theme": "ink",
        },
    )
    assert resp.status_code == 400
    assert "emoji" in resp.json()["detail"].lower()
