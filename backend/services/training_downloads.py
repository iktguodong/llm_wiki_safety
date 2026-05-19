"""Download path helpers for generated training materials."""

from __future__ import annotations

from pathlib import Path

from backend.config import OUTPUT_DIR


def output_dir() -> Path:
    return OUTPUT_DIR


def resolve_training_html_path(filename: str) -> Path:
    if not filename or filename != Path(filename).name or Path(filename).suffix.lower() != ".html":
        raise ValueError("文件名无效，只允许下载 HTML 文件")

    file_path = (output_dir() / filename).resolve()
    output_root = output_dir().resolve()
    if output_root not in file_path.parents and file_path.parent != output_root:
        raise ValueError("文件名无效")
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("文件不存在")
    return file_path
