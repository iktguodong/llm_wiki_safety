"""工作目录与产物存储。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.config import OUTPUT_DIR
from .models import PresentationJob, utc_now_str


PRESENTATIONS_DIR = OUTPUT_DIR / "presentations"
UPLOADS_DIR = PRESENTATIONS_DIR / "_uploads"


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    root: Path
    source_uploads: Path
    pptx_dir: Path
    content_pack_path: Path
    outline_path: Path
    spec_path: Path
    quality_report_path: Path
    speaker_notes_path: Path
    speaker_notes_docx_path: Path


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
        content_pack_path=root / "content_pack.json",
        outline_path=root / "outline.json",
        spec_path=root / "spec.json",
        quality_report_path=root / "quality_report.json",
        speaker_notes_path=root / "speaker_notes.md",
        speaker_notes_docx_path=root / "speaker_notes.docx",
    )


def create_job(source_mode: str, job_id: Optional[str] = None) -> PresentationJob:
    PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = job_id or f"ppt-{uuid.uuid4().hex[:10]}"
    paths = get_job_paths(job_id)
    paths.source_uploads.mkdir(parents=True, exist_ok=True)
    paths.pptx_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now_str()
    return PresentationJob(
        job_id=job_id,
        status="created",
        created_at=now,
        updated_at=now,
        source_mode=source_mode,
        content_pack_path=str(paths.content_pack_path),
        outline_path=str(paths.outline_path),
        spec_path=str(paths.spec_path),
        pptx_path=str(paths.pptx_dir / "training_deck.pptx"),
        quality_report_path=str(paths.quality_report_path),
        download_url=f"/api/training/download/training_deck.pptx",
    )


def save_content_pack(job_id: str, data: Any) -> Path:
    path = get_job_paths(job_id).content_pack_path
    _json_dump(path, data)
    return path


def save_outline(job_id: str, data: Any) -> Path:
    path = get_job_paths(job_id).outline_path
    _json_dump(path, data)
    return path


def save_spec(job_id: str, data: Any) -> Path:
    path = get_job_paths(job_id).spec_path
    _json_dump(path, data)
    return path


def save_quality_report(job_id: str, data: Any) -> Path:
    path = get_job_paths(job_id).quality_report_path
    _json_dump(path, data)
    return path


def save_speaker_notes(job_id: str, text: str) -> Path:
    path = get_job_paths(job_id).speaker_notes_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def save_speaker_notes_docx(job_id: str, document) -> Path:
    path = get_job_paths(job_id).speaker_notes_docx_path
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))
    return path


def get_upload_dir(upload_id: str) -> Path:
    return UPLOADS_DIR / upload_id


def save_upload_metadata(upload_id: str, data: Any) -> Path:
    path = get_upload_dir(upload_id) / "meta.json"
    _json_dump(path, data)
    return path


def load_upload_metadata(upload_id: str) -> Optional[dict[str, Any]]:
    data = _json_load(get_upload_dir(upload_id) / "meta.json")
    return data if isinstance(data, dict) else None


def resolve_download_path(filename: str, allowed_suffix: str = ".pptx") -> Path:
    from pathlib import Path as _Path

    if not filename or filename != _Path(filename).name or _Path(filename).suffix.lower() != allowed_suffix.lower():
        raise ValueError(f"文件名无效，只允许下载 {allowed_suffix} 文件")

    candidates = [
        OUTPUT_DIR / filename,
    ]

    if PRESENTATIONS_DIR.exists():
        candidates.extend(PRESENTATIONS_DIR.rglob(filename))

    valid = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if OUTPUT_DIR.resolve() in resolved.parents or resolved.parent == OUTPUT_DIR.resolve() or resolved == OUTPUT_DIR.resolve():
                if resolved.exists() and resolved.is_file() and resolved.suffix.lower() == allowed_suffix.lower():
                    valid.append(resolved)
        except Exception:
            continue

    if not valid:
        raise FileNotFoundError("文件不存在")

    valid.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return valid[0]
