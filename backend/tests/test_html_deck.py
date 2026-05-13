from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from backend.services.presentation.project_store import get_job_paths


def test_html_deck_generation_and_download(isolated_training_env):
    client = TestClient(app)

    outline = {
        "id": "outline-html-1",
        "title": "危险化学品仓库火灾应急处置培训",
        "topic": "危险化学品仓库火灾应急处置培训",
        "audience": "一线员工",
        "duration_minutes": 30,
        "style": "standard_training",
        "slides": [
            {
                "id": "slide-1",
                "slide_no": 1,
                "title": "危险化学品仓库火灾应急处置培训",
                "key_points": ["应急处置", "报警流程", "初期火灾扑救"],
                "notes": "封面页",
                "layout_hint": "封面",
                "slide_type": "cover",
                "source_refs": [],
                "visual_type": "cards",
                "safety_level": "normal",
            },
            {
                "id": "slide-2",
                "slide_no": 2,
                "title": "目录",
                "key_points": ["背景", "流程", "行动"],
                "notes": "目录页",
                "layout_hint": "目录",
                "slide_type": "agenda",
                "source_refs": [],
                "visual_type": "cards",
                "safety_level": "normal",
            },
        ],
        "sections": [],
        "warnings": [],
    }

    resp = client.post(
        "/api/training/html",
        json={
            "sources": [{"type": "prompt", "prompt": "危险化学品仓库火灾应急处置"}],
            "topic": "危险化学品仓库火灾应急处置培训",
            "audience": "一线员工",
            "duration_minutes": 30,
            "slide_count": 2,
            "style": "standard_training",
            "render_style": "magazine",
            "theme": "ink",
            "outline": outline,
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["filename"] == "index.html"
    assert data["download_url"].endswith("/index.html")

    job_id = data["job_id"]
    html_file = get_job_paths(job_id).html_dir / "index.html"
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert "<section class=\"slide\"" in html_text
    assert "HTML Deck" in html_text

    download_resp = client.get(f"/api/training/download-html/{job_id}/index.html")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("text/html")
