from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.services.presentation.html_deck import render_html_deck
from backend.services.presentation.html_planner import build_html_deck
from backend.services.presentation.models import ContentChunk, ContentPack, SourceRef
from backend.services.presentation.project_store import get_job_paths


def _make_source_refs(title: str) -> list[SourceRef]:
    return [
        SourceRef(source_type="kb_document", source_id="doc-1", kb_id="kb-1", document_id="doc-1", title=title, locator="page 1", excerpt="abc", confidence=0.9),
        SourceRef(source_type="kb_document", source_id="doc-1", kb_id="kb-1", document_id="doc-1", title=title, locator="page 2", excerpt="def", confidence=0.9),
        SourceRef(source_type="kb_document", source_id="doc-1", kb_id="kb-1", document_id="doc-1", title=title, locator="page 3", excerpt="ghi", confidence=0.9),
    ]


def test_html_planner_dedupes_sources_and_skips_boilerplate(isolated_training_env):
    duplicate_title = "绞中港集团有限公司生产安全事故应急预案2023年1月.pdf"
    pack = ContentPack(
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
                text="开场介绍培训主题和背景。培训对象：设备部班组长。应急处置要先报警，再组织现场隔离和初期灭火。",
                source_refs=_make_source_refs(duplicate_title),
                keywords=["应急", "报警", "处置", "火灾"],
                chunk_type="raw_document",
            ),
            ContentChunk(
                id="chunk-2",
                title="来源2",
                text="发生险情后，要先切断风险源，再按流程上报并复盘闭环。",
                source_refs=_make_source_refs(duplicate_title),
                keywords=["流程", "上报", "复盘", "闭环"],
                chunk_type="raw_document",
            ),
        ],
        warnings=[],
    )

    deck = build_html_deck(
        pack,
        {
            "slide_count": 8,
            "render_style": "magazine",
            "theme": "ink",
            "template_id": "magazine",
        },
    )

    assert deck.audience == "设备部班组长"
    assert "开场介绍培训主题和背景" not in deck.pages[0].subtitle
    assert deck.pages[0].source_refs
    assert len(deck.pages[0].source_refs) == 1
    assert deck.pages[0].source_refs[0].title == duplicate_title

    render_info = render_html_deck(deck, "html-test-dedupe")
    html_text = Path(render_info["html_path"]).read_text(encoding="utf-8")
    assert "开场介绍培训主题和背景" not in html_text
    assert "设备部班组长" in html_text


def test_html_route_generates_independent_html(isolated_training_env):
    client = TestClient(app)

    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "请突出应急处置、报警流程和初期火灾扑救"}],
            "topic": "这是我公司的应急预案培训，培训对象为管理层，培训名字为：绥中港应急预案培训会",
            "audience": "",
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
    assert deck["audience"] == "管理层"
    assert deck["title"] == "绥中港应急预案培训会"

    job_id = data["job_id"]
    html_file = get_job_paths(job_id).html_dir / "index.html"
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert "<section class=\"slide\"" in html_text
    assert "这是我公司的应急预案培训，培训对象为管理层，培训名字为：绥中港应急预案培训会" not in html_text
    assert "请突出应急处置、报警流程和初期火灾扑救" not in html_text
    assert "管理层" in html_text

    download_resp = client.get(f"/api/training/download-html/{job_id}/index.html")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("text/html")
