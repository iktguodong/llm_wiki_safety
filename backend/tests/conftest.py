from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import backend.config as config_module
import backend.services.presentation.project_store as project_store


@pytest.fixture(autouse=True)
def isolated_training_env(monkeypatch, tmp_path):
    kb_root = tmp_path / "knowledge-bases"
    output_dir = tmp_path / "output"
    kb_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config_module, "KB_ROOT", kb_root)
    monkeypatch.setattr(config_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(project_store, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(project_store, "PRESENTATIONS_DIR", output_dir / "presentations")
    monkeypatch.setattr(project_store, "UPLOADS_DIR", output_dir / "presentations" / "_uploads")

    models_backup = deepcopy(config_module.config.get("models", {}))
    monkeypatch.setitem(config_module.config["models"], "providers", [])
    monkeypatch.setitem(config_module.config["models"], "model_roles", {
        "doc_parse": "",
        "qa_chat": "",
        "ppt_gen": "",
    })

    yield {
        "kb_root": kb_root,
        "output_dir": output_dir,
    }

    config_module.config["models"] = models_backup
