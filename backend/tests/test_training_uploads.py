from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import app
from backend.services.presentation.project_store import get_upload_dir, save_upload_metadata


def test_training_upload_and_text_preview(isolated_training_env):
    client = TestClient(app)

    upload_resp = client.post(
        "/api/training/uploads",
        files={"file": ("note.txt", "发现火情立即报警。".encode("utf-8"), "text/plain")},
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()["data"]
    assert upload_data["upload_id"]
    assert upload_data["text_preview"]


def test_training_upload_rejects_unreadable_pdf(isolated_training_env, monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(app_module, "extract_document_pages", lambda path: [{"page": 1, "text": "[PDF扫描版: 文档未检测到可提取的文字内容，请上传文字版PDF]"}])

    upload_resp = client.post(
        "/api/training/uploads",
        files={"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload_resp.status_code == 400
    assert "OCR" in upload_resp.json()["detail"]


def test_cleanup_training_uploads_removes_expired_uploads(isolated_training_env):
    upload_id = "upload-expired-1"
    upload_dir = get_upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "old.txt").write_text("old", encoding="utf-8")
    save_upload_metadata(upload_id, {
        "upload_id": upload_id,
        "filename": "old.txt",
        "original_filename": "old.txt",
        "size": 3,
        "detected_type": "txt",
        "path": str(upload_dir / "old.txt"),
        "created_at": (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S"),
    })

    client = TestClient(app)
    resp = client.post("/api/training/cleanup-uploads")

    assert resp.status_code == 200
    assert resp.json()["data"]["deleted_count"] == 1
    assert not upload_dir.exists()


def test_app_lifespan_starts_and_stops_training_cleanup_task(isolated_training_env):
    assert app_module._training_upload_cleanup_task is None

    with TestClient(app):
        task = app_module._training_upload_cleanup_task
        assert task is not None
        assert not task.done()

    assert app_module._training_upload_cleanup_task is None
