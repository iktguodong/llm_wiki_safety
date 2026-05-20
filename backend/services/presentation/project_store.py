"""工作目录与产物存储。"""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass
from threading import Event
from pathlib import Path
from typing import Any, Optional

from backend.config import OUTPUT_DIR
from .models import utc_now_str


PRESENTATIONS_DIR = OUTPUT_DIR / "presentations"
UPLOADS_DIR = PRESENTATIONS_DIR / "_uploads"
TRAINING_HTML_PREFIX = "training_html_"

@dataclass
class RunningTrainingJob:
    task: asyncio.Task[Any]
    cancel_event: Event


_RUNNING_TRAINING_JOBS: dict[str, RunningTrainingJob] = {}
_JOB_PROGRESS: dict[str, str] = {}
_JOB_PROGRESS_LOCK = threading.Lock()


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    root: Path
    source_uploads: Path
    pptx_dir: Path
    html_dir: Path
    content_pack_path: Path
    outline_path: Path
    spec_path: Path
    quality_report_path: Path


def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _json_load(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def job_dir(job_id: str) -> Path:
    return PRESENTATIONS_DIR / job_id


def get_job_paths(job_id: str) -> JobPaths:
    root = job_dir(job_id)
    return JobPaths(
        job_id=job_id,
        root=root,
        source_uploads=root / "source" / "uploads",
        pptx_dir=root / "pptx",
        html_dir=root / "html",
        content_pack_path=root / "content_pack.json",
        outline_path=root / "outline.json",
        spec_path=root / "spec.json",
        quality_report_path=root / "quality_report.json",
    )


def register_running_job(job_id: str, task: asyncio.Task[Any]) -> None:
    _RUNNING_TRAINING_JOBS[job_id] = RunningTrainingJob(task=task, cancel_event=Event())


def unregister_running_job(job_id: str, task: asyncio.Task[Any] | None = None) -> None:
    current = _RUNNING_TRAINING_JOBS.get(job_id)
    if current is None:
        return
    if task is None or current.task is task:
        _RUNNING_TRAINING_JOBS.pop(job_id, None)


def cancel_running_job(job_id: str) -> bool:
    task = _RUNNING_TRAINING_JOBS.get(job_id)
    if task is None or task.task.done():
        return False
    task.cancel_event.set()
    task.task.cancel()
    return True


def get_running_job_entry(job_id: str) -> RunningTrainingJob | None:
    return _RUNNING_TRAINING_JOBS.get(job_id)


def get_running_job_cancel_event(job_id: str) -> Event | None:
    current = _RUNNING_TRAINING_JOBS.get(job_id)
    if current is None:
        return None
    return current.cancel_event


def update_job_progress(job_id: str, message: str) -> None:
    with _JOB_PROGRESS_LOCK:
        if message:
            _JOB_PROGRESS[job_id] = message
        else:
            _JOB_PROGRESS.pop(job_id, None)


def get_job_progress(job_id: str) -> str | None:
    with _JOB_PROGRESS_LOCK:
        return _JOB_PROGRESS.get(job_id)


def clear_job_progress(job_id: str) -> None:
    with _JOB_PROGRESS_LOCK:
        _JOB_PROGRESS.pop(job_id, None)


def cleanup_training_job(job_id: str) -> None:
    paths = get_job_paths(job_id)
    shutil.rmtree(paths.root, ignore_errors=True)
    html_file = OUTPUT_DIR / f"{TRAINING_HTML_PREFIX}{job_id}.html"
    if html_file.exists():
        try:
            html_file.unlink()
        except OSError:
            pass
    clear_job_progress(job_id)


def get_upload_dir(upload_id: str) -> Path:
    return UPLOADS_DIR / upload_id


def save_upload_metadata(upload_id: str, data: Any) -> Path:
    path = get_upload_dir(upload_id) / "meta.json"
    _json_dump(path, data)
    return path


def load_upload_metadata(upload_id: str) -> Optional[dict[str, Any]]:
    data = _json_load(get_upload_dir(upload_id) / "meta.json")
    return data if isinstance(data, dict) else None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _upload_timestamp(upload_dir: Path) -> Optional[datetime]:
    meta = load_upload_metadata(upload_dir.name)
    if meta:
        for key in ("created_at", "uploaded_at", "createdAt", "timestamp"):
            ts = _parse_timestamp(meta.get(key))
            if ts:
                return ts

    meta_path = upload_dir / "meta.json"
    if meta_path.exists():
        return datetime.fromtimestamp(meta_path.stat().st_mtime)
    if upload_dir.exists():
        return datetime.fromtimestamp(upload_dir.stat().st_mtime)
    return None


def cleanup_expired_training_uploads(max_age_hours: int = 24) -> int:
    if not UPLOADS_DIR.exists():
        return 0

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    deleted = 0
    for upload_dir in UPLOADS_DIR.iterdir():
        if not upload_dir.is_dir():
            continue
        ts = _upload_timestamp(upload_dir)
        if ts is None or ts > cutoff:
            continue
        shutil.rmtree(upload_dir, ignore_errors=True)
        deleted += 1
    return deleted


def resolve_download_path(filename: str, allowed_suffix: str = ".pptx") -> Path:
    """安全查找生成的 PPTX 文件。"""
    from pathlib import Path as _Path

    if not filename or filename != _Path(filename).name or _Path(filename).suffix.lower() != allowed_suffix.lower():
        raise ValueError(f"文件名无效，只允许下载 {allowed_suffix} 文件")

    if PRESENTATIONS_DIR.exists():
        for f in PRESENTATIONS_DIR.rglob(filename):
            try:
                resolved = f.resolve()
                if OUTPUT_DIR.resolve() in resolved.parents and resolved.exists() and resolved.is_file():
                    return resolved
            except Exception:
                continue

    candidate = OUTPUT_DIR / filename
    if candidate.exists():
        return candidate.resolve()

    raise FileNotFoundError("文件不存在")


