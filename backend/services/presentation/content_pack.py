"""把不同来源统一转换为 ContentPack。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from backend.config import get_kb_path, get_kb_raw_path, get_kb_wiki_path
from backend.services.document import doc_service
from backend.services.text_extraction import extract_document_pages, extract_document_text
from .models import ContentChunk, ContentPack, SourceInput, SourceRef
from .project_store import get_job_paths, load_upload_metadata

MAX_CHUNK_CHARS = 1200
MAX_PACK_CHARS = 12000


def _as_dict(request: Any) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return dict(request.model_dump())
    if isinstance(request, dict):
        return dict(request)
    return dict(getattr(request, "__dict__", {}))


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if parts:
        return parts
    if text.strip():
        return [text.strip()]
    return []


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
            continue
        candidate = current + "\n\n" + para
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def _short_excerpt(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _derive_title(topic: str) -> str:
    text = re.sub(r"\s+", "", str(topic or "")).strip()
    if not text:
        return "安全生产培训"

    explicit_patterns = [
        r"(?:培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是)[:：]([^，,。；;]+)",
        r"(?:培训名字为|培训名称为|培训名为|标题为|题目为|名称为|主题为|名字为|标题是|题目是|名称是|主题是)([^，,。；;]+)",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text)
        if match:
            explicit = match.group(1).strip("：:，,。.;；/\\ ")
            if explicit:
                return explicit[:24]

    text = re.sub(r"^(请|请您|请重点|请突出|请围绕|围绕|关于|针对|以|以.*为主题|主题[:：])+", "", text)
    text = re.sub(r"^(生成|制作|输出|整理|汇总)(一个|一份|一套)?", "", text)
    text = text.strip("：:，,。.;；/\\")
    fragments = [frag for frag in re.split(r"[。！？!?]", text) if frag]
    if fragments:
        text = fragments[0]
    for prefix in (
        "这是我公司的",
        "这是我们公司的",
        "这是本公司的",
        "这是公司的",
        "我公司的",
        "我们公司的",
        "本公司的",
        "公司的",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    parts = [part for part in re.split(r"[、，,；;和与及/]+", text) if part]
    parts = [part for part in parts if not re.search(r"(面向|针对|适用于|培训对象)", part)]
    if parts:
        # 优先保留最有信息量的前两到三段，避免变成整句需求
        title = "、".join(parts[:3])
    else:
        title = text

    title = re.sub(r"^(开展|进行|组织|实施|举办|召开|学习)+", "", title)
    title = re.sub(r"(方案|内容|材料|网页|页面|课件)$", "", title)
    title = title.strip("：:，,。.;；/\\")
    title = re.sub(r"(，|,).*?(培训对象|培训名字为|名称为|标题为|题目为|面向|针对|适用于).*", "", title)
    title = title.strip("：:，,。.;；/\\")
    if not title:
        title = text[:18] or "安全生产培训"
    if len(title) > 24:
        title = title[:24].rstrip("、，,") + "…"
    return title


def _derive_audience(explicit: str | None, topic: str) -> str:
    text = str(explicit or "").strip()
    if text:
        return text
    source = re.sub(r"\s+", "", str(topic or ""))
    patterns = [
        r"培训对象(?:是|为|：|:)?([^，,。；;、/]+)",
        r"面向([^，,。；;、/]+)",
        r"适用于([^，,。；;、/]+)",
        r"针对([^，,。；;、/]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            audience = match.group(1).strip("：:，,。.;；/\\")
            if audience:
                return audience[:20]
    for token in ("一线员工", "管理层", "班组长", "新员工", "全员", "特种作业人员", "维修人员", "仓库人员", "中层管理者"):
        if token in source:
            return token
    return "相关岗位人员"


def _keywords(text: str) -> list[str]:
    candidates = [
        "应急", "风险", "隐患", "作业", "制度", "职责", "流程", "处置", "检查",
        "培训", "防护", "报警", "疏散", "灭火", "事故", "危化品", "仓库", "许可",
    ]
    found = [kw for kw in candidates if kw in text]
    return found[:6]


def _make_ref(
    source_type: str,
    source_id: str | None = None,
    kb_id: str | None = None,
    document_id: str | None = None,
    page_name: str | None = None,
    upload_id: str | None = None,
    title: str | None = None,
    locator: str | None = None,
    excerpt: str | None = None,
    confidence: float = 0.0,
) -> SourceRef:
    return SourceRef(
        source_type=source_type,
        source_id=source_id,
        kb_id=kb_id,
        document_id=document_id,
        page_name=page_name,
        upload_id=upload_id,
        title=title,
        locator=locator,
        excerpt=excerpt,
        confidence=confidence,
    )


def _append_chunks(
    content_chunks: list[ContentChunk],
    *,
    title: str,
    chunk_type: str,
    text: str,
    refs: list[SourceRef],
) -> None:
    for piece in _chunk_text(text):
        if not piece.strip():
            continue
        content_chunks.append(
            ContentChunk(
                id=f"chunk-{uuid.uuid4().hex[:8]}",
                title=title,
                text=piece[:MAX_CHUNK_CHARS],
                source_refs=refs,
                keywords=_keywords(piece),
                chunk_type=chunk_type,  # type: ignore[arg-type]
            )
        )


def _read_wiki_page(page_path: Path, kb_id: str, page_name: str | None = None) -> tuple[str, str]:
    text = page_path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else (page_path.stem if page_name else page_path.stem)
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if line.startswith("**Sources**"):
            continue
        summary_match = re.match(r"^\*\*Summary\*\*:\s*(.*)$", line, re.IGNORECASE)
        if summary_match:
            summary_text = summary_match.group(1).strip()
            summary_text = re.sub(r"\(source:[^)]+\)", "", summary_text, flags=re.IGNORECASE).strip()
            if summary_text:
                cleaned_lines.append(summary_text)
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = line.replace("**", "")
        line = re.sub(r"\(source:[^)]+\)", "", line, flags=re.IGNORECASE)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    return title, cleaned or text


def _load_wiki_sources(kb_id: str, page_name: str | None, pack: ContentPack) -> None:
    wiki_path = get_kb_wiki_path(kb_id)
    if not wiki_path.exists():
        pack.warnings.append(f"知识库 {kb_id} 暂无可用内容")
        return

    pages: list[Path]
    if page_name:
        page_file = wiki_path / page_name
        if not page_file.exists():
            pack.warnings.append(f"知识库 {kb_id} 未找到对应内容 {page_name}")
            return
        pages = [page_file]
    else:
        pages = [p for p in sorted(wiki_path.glob("*.md")) if p.name not in {"index.md", "log.md"}]
        index_file = wiki_path / "index.md"
        if index_file.exists():
            title, text = _read_wiki_page(index_file, kb_id, "index.md")
            ref = _make_ref("wiki_page", source_id="index.md", kb_id=kb_id, page_name="index.md", title=title, locator="index.md", excerpt=_short_excerpt(text), confidence=0.8)
            _append_chunks(pack.chunks, title=title, chunk_type="wiki", text=text[:MAX_PACK_CHARS], refs=[ref])

    for page_file in pages:
        title, text = _read_wiki_page(page_file, kb_id, page_file.name)
        ref = _make_ref("wiki_page", source_id=page_file.name, kb_id=kb_id, page_name=page_file.name, title=title, locator=page_file.name, excerpt=_short_excerpt(text), confidence=0.85)
        _append_chunks(pack.chunks, title=title, chunk_type="wiki", text=text[:MAX_PACK_CHARS], refs=[ref])


def _load_document_sources(
    kb_id: str,
    document_id: str | None,
    pack: ContentPack,
    *,
    prefer_wiki_pages: bool = False,
) -> None:
    track = doc_service._load_doc_track(kb_id)
    docs = track.get("documents", {})
    if document_id:
        targets = [(document_id, docs.get(document_id))]
    else:
        targets = list(docs.items())

    raw_path = get_kb_raw_path(kb_id)
    for doc_id, doc_info in targets:
        if not doc_info:
            pack.warnings.append(f"知识库 {kb_id} 未找到文档 {doc_id}")
            continue

        file_path = raw_path / doc_info.get("file", "")
        if not file_path.exists():
            pack.warnings.append(f"文档文件不存在：{file_path.name}")
            continue

        # HTML 训练页优先使用该文档关联的 wiki 页面，让输出更像已经整理过的讲稿，
        # 避免直接把原始 PDF 段落铺到页面上。
        if prefer_wiki_pages and doc_info.get("wiki_pages"):
            wiki_pages = [
                str(page_name)
                for page_name in doc_info.get("wiki_pages", [])
                if str(page_name).strip() and str(page_name) not in {"index.md", "log.md"}
            ]
            if wiki_pages:
                for page_name in wiki_pages:
                    _load_wiki_sources(kb_id, page_name, pack)
                continue

        pages = extract_document_pages(file_path)
        if len(pages) == 1 and isinstance(pages[0].get("text"), str):
            text = str(pages[0]["text"])
            if text.startswith("[PDF扫描版:") or text.startswith("[PDF解析错误:") or text.startswith("[Word解析错误:") or text.startswith("[文本读取错误:"):
                raise ValueError(f"文档 {file_path.name} 无法提取可读文本：{text.strip('[]')}")

        ref_base = _make_ref(
            "kb_document",
            source_id=doc_id,
            kb_id=kb_id,
            document_id=doc_id,
            title=file_path.name,
            locator=file_path.name,
            excerpt=_short_excerpt(extract_document_text(file_path)),
            confidence=0.9,
        )
        page_texts = []
        for page in pages:
            page_no = int(page.get("page", 1))
            text = str(page.get("text", "")).strip()
            if not text:
                continue
            page_texts.append((page_no, text))
        if not page_texts:
            raise ValueError(f"文档 {file_path.name} 未提取到可读文本，不支持 OCR")
        for page_no, text in page_texts:
            page_ref = ref_base.model_copy(update={"locator": f"page {page_no}", "excerpt": _short_excerpt(text)})
            _append_chunks(pack.chunks, title=file_path.name, chunk_type="raw_document", text=text[:MAX_PACK_CHARS], refs=[page_ref])


def _load_temporary_upload(upload_id: str, pack: ContentPack, job_id: str | None) -> None:
    meta = load_upload_metadata(upload_id)
    if not meta:
        raise ValueError(f"临时上传 {upload_id} 不存在")

    filename = str(meta.get("filename") or meta.get("original_name") or "")
    upload_dir = get_job_paths(job_id).source_uploads if job_id else None
    source_path: Path | None = None
    if upload_dir and (upload_dir / filename).exists():
        source_path = upload_dir / filename
    else:
        candidate = meta.get("path")
        if candidate:
            source_path = Path(candidate)
    if not source_path or not source_path.exists():
        raise ValueError(f"临时上传文件不存在：{filename or upload_id}")

    pages = extract_document_pages(source_path)
    if len(pages) == 1 and isinstance(pages[0].get("text"), str):
        text = str(pages[0]["text"])
        if text.startswith("[PDF扫描版:") or text.startswith("[PDF解析错误:") or text.startswith("[Word解析错误:") or text.startswith("[文本读取错误:"):
            raise ValueError("临时上传文档无法提取可读文本，不支持 OCR")

    texts = [str(page.get("text", "")).strip() for page in pages if str(page.get("text", "")).strip()]
    if not texts:
        raise ValueError("临时上传文档未提取到可读文本，不支持 OCR")

    ref = _make_ref(
        "temporary_upload",
        source_id=upload_id,
        upload_id=upload_id,
        title=filename,
        locator=filename,
        excerpt=_short_excerpt("\n\n".join(texts)),
        confidence=0.85,
    )
    for page in pages:
        text = str(page.get("text", "")).strip()
        if not text:
            continue
        locator = f"page {int(page.get('page', 1))}"
        page_ref = ref.model_copy(update={"locator": locator, "excerpt": _short_excerpt(text)})
        _append_chunks(pack.chunks, title=filename, chunk_type="temporary_upload", text=text[:MAX_PACK_CHARS], refs=[page_ref])


def _add_prompt_source(prompt: str, pack: ContentPack) -> None:
    text = prompt.strip()
    if not text:
        pack.warnings.append("提示词来源为空")
        return
    pack.warnings.append("该内容主要由模型生成，未绑定企业原文来源")
    ref = _make_ref("prompt", source_id="prompt", title="自由提示词", locator="prompt", excerpt=_short_excerpt(text), confidence=0.2)
    _append_chunks(pack.chunks, title="自由提示词", chunk_type="prompt_generated", text=text, refs=[ref])


def normalize_sources(payload: dict[str, Any]) -> list[SourceInput]:
    sources = payload.get("sources")
    if sources:
        normalized: list[SourceInput] = []
        for item in sources:
            if hasattr(item, "model_dump"):
                data = item.model_dump()
            else:
                data = dict(item)
            normalized.append(SourceInput(**data))
        return normalized

    source_type = payload.get("source_type") or payload.get("sourceType")
    source_ids = payload.get("source_ids") or payload.get("sourceIds") or []
    normalized = []
    if source_type == "knowledge_base":
        for kb_id in source_ids:
            normalized.append(SourceInput(type="knowledge_base", kb_id=kb_id))
    elif source_type == "wiki_page":
        for item in source_ids:
            if isinstance(item, dict):
                normalized.append(SourceInput(type="wiki_page", kb_id=item.get("kb_id"), page_name=item.get("page_name")))
            else:
                normalized.append(SourceInput(type="wiki_page", kb_id=payload.get("kb_id"), page_name=str(item)))
    elif source_type == "kb_document":
        for item in source_ids:
            if isinstance(item, dict):
                normalized.append(SourceInput(type="kb_document", kb_id=item.get("kb_id"), document_id=item.get("document_id")))
            else:
                normalized.append(SourceInput(type="kb_document", kb_id=payload.get("kb_id"), document_id=str(item)))
    elif source_type == "temporary_upload":
        for item in source_ids:
            normalized.append(SourceInput(type="temporary_upload", upload_id=str(item)))
    elif source_type == "prompt":
        normalized.append(SourceInput(type="prompt", prompt=str(payload.get("prompt") or payload.get("topic") or "")))
    return normalized


def build_content_pack(request: Any, job_id: str | None = None) -> ContentPack:
    payload = _as_dict(request)
    sources = normalize_sources(payload)
    topic = str(payload.get("topic") or payload.get("prompt") or "安全生产培训")
    title = _derive_title(topic)
    audience = _derive_audience(payload.get("audience"), topic)
    duration_minutes = int(payload.get("duration_minutes") or payload.get("duration") or 60)
    prefer_wiki_pages = bool(payload.get("prefer_wiki_pages"))
    pack = ContentPack(
        id=f"cp-{uuid.uuid4().hex[:10]}",
        title=title,
        topic=topic,
        audience=audience,
        duration_minutes=duration_minutes,
        sources=sources,
    )

    if not sources:
        _add_prompt_source(topic, pack)
        return pack

    for source in sources:
        if source.type == "knowledge_base":
            if not source.kb_id:
                pack.warnings.append("知识库内容来源缺少 kb_id")
                continue
            _load_wiki_sources(source.kb_id, None, pack)
        elif source.type == "wiki_page":
            if not source.kb_id or not source.page_name:
                pack.warnings.append("知识库内容来源缺少 kb_id 或内容标识")
                continue
            _load_wiki_sources(source.kb_id, source.page_name, pack)
        elif source.type == "kb_document":
            if not source.kb_id:
                pack.warnings.append("知识库文档来源缺少 kb_id")
                continue
            _load_document_sources(source.kb_id, source.document_id, pack, prefer_wiki_pages=prefer_wiki_pages)
        elif source.type == "temporary_upload":
            if not source.upload_id:
                raise ValueError("temporary_upload 来源缺少 upload_id")
            _load_temporary_upload(source.upload_id, pack, job_id)
        elif source.type == "prompt":
            _add_prompt_source(source.prompt or topic, pack)

    if not pack.chunks:
        pack.warnings.append("未提取到可用内容，将使用提示词式通用安全培训结构")
        _add_prompt_source(topic, pack)

    return pack
