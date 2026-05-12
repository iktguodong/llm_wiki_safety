from __future__ import annotations

import asyncio

from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation.outline_builder import generate_outline
from backend.services.document import doc_service
from backend.config import get_kb_wiki_path, get_kb_raw_path


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30
    slide_count = 15
    style = "standard_training"
    focus_areas = ["应急处置", "报警流程"]
    include_quiz = True
    include_speaker_notes = True


def test_prompt_only_outline_falls_back_to_default_sections(isolated_training_env):
    pack = build_content_pack(PromptReq())
    outline = asyncio.run(generate_outline(pack, PromptReq()))
    assert len(outline.slides) >= 3
    assert len(outline.sections) >= 1
    assert any("未绑定企业原文来源" in warning for warning in outline.warnings)


def test_temporary_upload_outline(isolated_training_env):
    from backend.services.presentation.project_store import get_upload_dir, save_upload_metadata

    upload_id = "upload-outline-1"
    upload_dir = get_upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_file = upload_dir / "guide.md"
    source_file.write_text("# 现场处置\n\n发现异常后立即上报。", encoding="utf-8")
    save_upload_metadata(upload_id, {
        "upload_id": upload_id,
        "filename": source_file.name,
        "path": str(source_file),
        "size": source_file.stat().st_size,
        "detected_type": "md",
    })

    req = {
        "sources": [{"type": "temporary_upload", "upload_id": upload_id}],
        "topic": "临时上传培训",
        "audience": "班组",
        "duration_minutes": 20,
        "slide_count": 10,
        "style": "frontline_shift_training",
        "focus_areas": ["异常上报"],
        "include_quiz": False,
        "include_speaker_notes": True,
    }
    outline = asyncio.run(generate_outline(build_content_pack(req, job_id="job-outline"), req))
    assert outline.slides
    assert outline.style == "frontline_shift_training"


def test_knowledge_base_outline(isolated_training_env):
    kb_id = "kb-outline-1"
    wiki_path = get_kb_wiki_path(kb_id)
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "index.md").write_text("# 索引\n\n- [[fire]] 火灾应急", encoding="utf-8")
    (wiki_path / "fire.md").write_text("# 火灾应急\n\n发现火情立即报警。", encoding="utf-8")

    raw_path = get_kb_raw_path(kb_id)
    raw_path.mkdir(parents=True, exist_ok=True)
    doc = asyncio.run(doc_service.upload(kb_id, "raw.txt", "检查清单与职责".encode("utf-8")))

    req = {
        "sources": [
            {"type": "knowledge_base", "kb_id": kb_id},
            {"type": "kb_document", "kb_id": kb_id, "document_id": doc.id},
        ],
        "topic": "知识库生成测试",
        "audience": "管理层",
        "duration_minutes": 40,
        "slide_count": 12,
        "style": "management_briefing",
        "focus_areas": ["职责", "流程"],
        "include_quiz": True,
        "include_speaker_notes": True,
    }
    outline = asyncio.run(generate_outline(build_content_pack(req), req))
    assert len(outline.slides) >= 4
    assert outline.style == "management_briefing"
