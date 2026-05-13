from __future__ import annotations

import json
from pathlib import Path

from backend.services.document import doc_service
from backend.services.presentation.content_pack import build_content_pack
from backend.services.presentation.project_store import get_upload_dir, save_upload_metadata
from backend.config import get_kb_wiki_path, get_kb_raw_path, get_kb_doc_track_path


class PromptReq:
    sources = [{"type": "prompt", "prompt": "帮我生成一份危险化学品仓库火灾应急处置培训 PPT"}]
    topic = "危险化学品仓库火灾应急处置培训"
    audience = "一线员工"
    duration_minutes = 30


def test_prompt_only_content_pack_builds_prompt_chunk(isolated_training_env):
    pack = build_content_pack(PromptReq())
    assert len(pack.chunks) == 1
    assert pack.chunks[0].chunk_type == "prompt_generated"
    assert any("未绑定企业原文来源" in warning for warning in pack.warnings)


def test_content_pack_prefers_explicit_title_and_audience(isolated_training_env):
    pack = build_content_pack({
        "sources": [{"type": "prompt", "prompt": "请突出应急处置、报警流程和初期火灾扑救"}],
        "topic": "这是我公司的应急预案培训，培训对象为管理层，培训名字为：绥中港应急预案培训会",
        "audience": "",
        "duration_minutes": 30,
    })

    assert pack.title == "绥中港应急预案培训会"
    assert pack.audience == "管理层"


def test_temporary_upload_content_pack_builds_refs(isolated_training_env):
    upload_id = "upload-test-1"
    upload_dir = get_upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_file = upload_dir / "notes.txt"
    source_file.write_text("危险化学品仓库应急处置\n发现火情后立即报警。", encoding="utf-8")
    save_upload_metadata(upload_id, {
        "upload_id": upload_id,
        "filename": source_file.name,
        "path": str(source_file),
        "size": source_file.stat().st_size,
        "detected_type": "txt",
    })

    pack = build_content_pack({
        "sources": [{"type": "temporary_upload", "upload_id": upload_id}],
        "topic": "临时上传测试",
        "audience": "一线员工",
        "duration_minutes": 30,
    }, job_id="job-1")

    assert any(chunk.chunk_type == "temporary_upload" for chunk in pack.chunks)
    assert any(ref.upload_id == upload_id for chunk in pack.chunks for ref in chunk.source_refs)


def test_knowledge_base_and_document_sources_build_pack(isolated_training_env):
    kb_id = "kb-test-1"
    wiki_path = get_kb_wiki_path(kb_id)
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "index.md").write_text("# 索引\n\n- [[fire]] 火灾应急", encoding="utf-8")
    (wiki_path / "fire.md").write_text("# 火灾应急\n\n发现火情立即报警。", encoding="utf-8")

    # 通过文档服务建立 raw/文档追踪.json
    raw_file = get_kb_raw_path(kb_id)
    raw_file.mkdir(parents=True, exist_ok=True)
    doc = __import__("asyncio").run(doc_service.upload(kb_id, "raw.txt", "现场检查和应急处置".encode("utf-8")))

    pack = build_content_pack({
        "sources": [
            {"type": "knowledge_base", "kb_id": kb_id},
            {"type": "kb_document", "kb_id": kb_id, "document_id": doc.id},
        ],
        "topic": "知识库测试",
        "audience": "一线员工",
        "duration_minutes": 30,
    })

    assert pack.chunks
    assert any(ref.kb_id == kb_id for chunk in pack.chunks for ref in chunk.source_refs)
    assert any(ref.document_id == doc.id for chunk in pack.chunks for ref in chunk.source_refs)
