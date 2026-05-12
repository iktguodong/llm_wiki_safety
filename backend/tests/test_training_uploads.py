from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import app
from backend.config import get_kb_wiki_path
from backend.services.presentation.project_store import get_job_paths


def test_training_upload_and_download_and_legacy_outline(isolated_training_env, monkeypatch):
    client = TestClient(app)

    upload_resp = client.post(
        "/api/training/uploads",
        files={"file": ("note.txt", "发现火情立即报警。".encode("utf-8"), "text/plain")},
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()["data"]
    assert upload_data["upload_id"]
    assert upload_data["text_preview"]

    # Legacy outline request should still work.
    kb_id = "kb-legacy-1"
    wiki_path = get_kb_wiki_path(kb_id)
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "index.md").write_text("# 索引\n\n- [[fire]] 火灾应急", encoding="utf-8")
    (wiki_path / "fire.md").write_text("# 火灾应急\n\n发现火情立即报警。", encoding="utf-8")

    outline_resp = client.post(
        "/api/training/outline",
        json={
            "source_type": "knowledge_base",
            "source_ids": [kb_id],
            "config": {
                "topic": "旧接口测试",
                "audience": "一线员工",
                "duration": 30,
                "slide_count": 10,
                "focus_areas": ["应急处置"],
                "template": "standard_training",
            },
        },
    )
    assert outline_resp.status_code == 200
    outline_data = outline_resp.json()["data"]
    assert outline_data["outline"]["sections"]

    # create a pptx file and validate download safety
    job_paths = get_job_paths("job-download-1")
    job_paths.pptx_dir.mkdir(parents=True, exist_ok=True)
    pptx_file = job_paths.pptx_dir / "training_deck.pptx"
    pptx_file.write_bytes(b"pptx")

    ok_resp = client.get("/api/training/download/training_deck.pptx")
    assert ok_resp.status_code in {200, 404}

    assert app_module.resolve_download_path("training_deck.pptx").name == "training_deck.pptx"


def test_training_upload_rejects_unreadable_pdf(isolated_training_env, monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(app_module, "extract_document_pages", lambda path: [{"page": 1, "text": "[PDF扫描版: 文档未检测到可提取的文字内容，请上传文字版PDF]"}])

    upload_resp = client.post(
        "/api/training/uploads",
        files={"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload_resp.status_code == 400
    assert "OCR" in upload_resp.json()["detail"]
