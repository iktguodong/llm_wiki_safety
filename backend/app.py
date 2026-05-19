"""
安牛后端主应用
FastAPI + 所有业务API
"""

import asyncio
import contextlib
import logging
import sys
import uuid
from pathlib import Path

# 支持从 backend/ 目录直接运行：将项目根目录加入路径
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Query
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import config, save_config, get_kb_path
from backend.logging_config import configure_logging
from backend.models import (
    ApiResponse, KnowledgeBaseCreate, KnowledgeBase, KnowledgeBaseListResponse,
    DocumentInfo, DocumentListResponse, DocumentDeleteRequest, DocumentDeletePreview,
    WikiPage, WikiPageContent, WikiPageListResponse, WikiLintResult,
    ChatRequest, ChatResponse,
    MessageDocxExportRequest,
    AssistantPromptOptimizeRequest, AssistantPromptOptimizeResponse,
    SearchRequest, SearchResult,
    ModelValidateRequest, ModelValidateResponse,
    AppConfig,
    TemporaryTrainingUploadResponse,
    TrainingHtmlGenerateRequest,
    TrainingHtmlGenerateResponse,
)
from backend.services.knowledge_base import kb_service
from backend.services.document import doc_service
from backend.services.wiki import wiki_service
from backend.services.chat import chat_service
from backend.services.search import search_service
from backend.services.training import training_service
from backend.services.training_ppt import training_payload_to_request, training_ppt_service
from backend.services.llm import llm_service
from backend.services.assistant_prompt import optimize_prompt as optimize_assistant_prompt
from backend.services.text_extraction import SUPPORTED_TEXT_EXTENSIONS, extract_document_pages
from backend.services.presentation.project_store import (
    cancel_running_job,
    cleanup_expired_training_uploads,
    cleanup_training_job,
    create_job,
    get_upload_dir,
    resolve_download_path,
    save_upload_metadata,
    register_running_job,
    unregister_running_job,
)
from backend.services.presentation.models import utc_now_str
from backend.services.message_export import build_message_docx_bytes
from backend.services.training_downloads import resolve_training_html_path

configure_logging()
logger = logging.getLogger(__name__)
_training_upload_cleanup_task: asyncio.Task | None = None

# 创建FastAPI应用
app = FastAPI(
    title="安牛API",
    description="企业安全知识库后端服务",
    version="1.0.0"
)

# 添加CORS中间件，支持前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def restore_document_parse_statuses():
    """将重启后停留在 parsing 的文档恢复到 pending，避免状态卡死。"""
    global _training_upload_cleanup_task
    reset_count = await doc_service.reset_stale_parse_statuses()
    deleted_count = cleanup_expired_training_uploads()
    logger.info(
        "startup maintenance completed: reset_parse_statuses=%s deleted_uploads=%s",
        reset_count,
        deleted_count,
    )
    _training_upload_cleanup_task = asyncio.create_task(_periodic_training_upload_cleanup())


@app.on_event("shutdown")
async def stop_background_tasks():
    global _training_upload_cleanup_task
    if _training_upload_cleanup_task is None:
        return
    _training_upload_cleanup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _training_upload_cleanup_task
    _training_upload_cleanup_task = None


async def _periodic_training_upload_cleanup(interval_seconds: int = 6 * 60 * 60):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            deleted_count = cleanup_expired_training_uploads()
            if deleted_count:
                logger.info("expired training uploads cleaned: deleted_uploads=%s", deleted_count)
        except Exception:
            logger.exception("failed to clean expired training uploads")


# ==================== 配置API ====================

@app.get("/api/config", response_model=ApiResponse)
async def get_config():
    """读取全局配置"""
    return ApiResponse(data=config)


@app.put("/api/config", response_model=ApiResponse)
async def update_config(data: dict):
    """更新全局配置"""
    config.update(data)
    save_config(config)
    return ApiResponse(message="配置已保存")


@app.post("/api/config/models/validate", response_model=ApiResponse)
async def validate_model(data: ModelValidateRequest):
    """验证模型服务连接"""
    result = await llm_service.validate(data.provider_id, data.api_key, data.base_url)
    return ApiResponse(data=result)


@app.get("/api/config/current-kb", response_model=ApiResponse)
async def get_current_kb_id():
    """获取当前知识库ID"""
    return ApiResponse(data={"id": config.get("current_kb_id")})


@app.post("/api/config/current-kb", response_model=ApiResponse)
async def set_current_kb_id(body: dict):
    """设置当前知识库"""
    config["current_kb_id"] = body.get("id")
    save_config(config)
    return ApiResponse(message="当前知识库已更新")


@app.get("/api/config/current-model", response_model=ApiResponse)
async def get_current_model_id():
    """获取当前模型ID"""
    return ApiResponse(data={"id": config.get("current_model_id", "deepseek-v4-flash")})


@app.post("/api/config/current-model", response_model=ApiResponse)
async def set_current_model_id(body: dict):
    """设置当前模型"""
    config["current_model_id"] = body.get("id", "deepseek-v4-flash")
    save_config(config)
    return ApiResponse(message="当前模型已更新")


# ==================== 知识库API ====================

@app.get("/api/knowledge-bases", response_model=ApiResponse)
async def list_knowledge_bases():
    """列出所有知识库"""
    kbs = await kb_service.list_all()
    return ApiResponse(data=KnowledgeBaseListResponse(total=len(kbs), items=kbs))


@app.post("/api/knowledge-bases", response_model=ApiResponse)
async def create_knowledge_base(data: KnowledgeBaseCreate):
    """创建知识库"""
    kb = await kb_service.create(data)
    return ApiResponse(data=kb, message=f"知识库「{kb.name}」创建成功")


@app.put("/api/knowledge-bases/{kb_id}", response_model=ApiResponse)
async def update_knowledge_base(kb_id: str, data: KnowledgeBaseCreate):
    """更新知识库名称或描述"""
    kb = await kb_service.update(kb_id, data)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return ApiResponse(data=kb, message=f"知识库「{kb.name}」已更新")


@app.get("/api/knowledge-bases/{kb_id}", response_model=ApiResponse)
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    kb = await kb_service.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return ApiResponse(data=kb)


@app.delete("/api/knowledge-bases/{kb_id}", response_model=ApiResponse)
async def delete_knowledge_base(kb_id: str):
    """删除知识库"""
    success = await kb_service.delete(kb_id)
    if not success:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return ApiResponse(message="知识库已删除")


# ==================== 文档API ====================

@app.get("/api/knowledge-bases/{kb_id}/documents", response_model=ApiResponse)
async def list_documents(kb_id: str):
    """列出知识库中的所有文档"""
    docs = await doc_service.list_documents(kb_id)
    return ApiResponse(data=DocumentListResponse(total=len(docs), items=docs))


@app.post("/api/knowledge-bases/{kb_id}/documents", response_model=ApiResponse)
async def upload_document(kb_id: str, file: UploadFile = File(...)):
    """上传文档"""
    # 检查知识库是否存在
    kb = await kb_service.get(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 检查文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_TEXT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="暂不支持该文件类型，请上传 PDF、Word（.doc/.docx）、TXT 或 Markdown 文件"
        )
    
    # 读取文件内容
    content = await file.read()
    
    # 保存文档
    doc = await doc_service.upload(kb_id, file.filename, content)
    
    # 自动解析（如果配置允许）
    meta = config.get("knowledge_bases", {}).get(kb_id, {})
    if meta.get("auto_parse", True):
        # 异步解析（这里简化处理，实际应该用后台任务）
        import asyncio
        asyncio.create_task(wiki_service.parse_document(kb_id, doc.id))
    
    return ApiResponse(data=doc, message="文档上传成功")


@app.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/delete-preview", response_model=ApiResponse)
async def get_delete_preview(kb_id: str, doc_id: str):
    """获取删除文档预览"""
    preview = await doc_service.get_delete_preview(kb_id, doc_id)
    if not preview:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ApiResponse(data=preview)


@app.delete("/api/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=ApiResponse)
async def delete_document(kb_id: str, doc_id: str, delete_wiki: bool = False):
    """删除文档"""
    success = await doc_service.delete(kb_id, doc_id, delete_wiki_pages=delete_wiki)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ApiResponse(message="文档已删除")


@app.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/content", response_model=ApiResponse)
async def get_document_content(kb_id: str, doc_id: str, page: int = 1):
    """获取文档内容（分页）"""
    from backend.config import get_kb_raw_path

    raw_path = get_kb_raw_path(kb_id)
    # 通过文档追踪找到文件名
    track = doc_service._load_doc_track(kb_id)
    doc_info = track.get("documents", {}).get(doc_id)
    doc_file = raw_path / doc_info["file"] if doc_info else None
    
    if not doc_file or not doc_file.exists():
        raise HTTPException(status_code=404, detail="文档不存在")
    
    pages = extract_document_pages(doc_file)
    total_pages = len(pages)
    
    if page < 1 or page > total_pages:
        raise HTTPException(status_code=400, detail="页码超出范围")
    
    page_data = pages[page - 1]
    return ApiResponse(data={
        "content": page_data["text"],
        "current_page": page,
        "total_pages": total_pages,
        "file_name": doc_file.name
    })


@app.post("/api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights", response_model=ApiResponse)
async def save_highlights(kb_id: str, doc_id: str, highlights: List[dict]):
    """保存文档高亮标注"""
    import json
    from backend.config import get_kb_path
    highlights_file = get_kb_path(kb_id) / f"highlights_{doc_id}.json"
    with open(highlights_file, "w", encoding="utf-8") as f:
        json.dump(highlights, f, ensure_ascii=False, indent=2)
    return ApiResponse(message="高亮已保存")


@app.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/highlights", response_model=ApiResponse)
async def get_highlights(kb_id: str, doc_id: str):
    """获取文档高亮标注"""
    import json
    from backend.config import get_kb_path
    highlights_file = get_kb_path(kb_id) / f"highlights_{doc_id}.json"
    if not highlights_file.exists():
        return ApiResponse(data={"highlights": []})
    with open(highlights_file, "r", encoding="utf-8") as f:
        highlights = json.load(f)
    return ApiResponse(data={"highlights": highlights})


# ==================== Wiki API ====================

@app.get("/api/knowledge-bases/{kb_id}/wiki-pages", response_model=ApiResponse)
async def list_wiki_pages(kb_id: str):
    """列出知识库的所有Wiki页面"""
    pages = await wiki_service.list_wiki_pages(kb_id)
    return ApiResponse(data=WikiPageListResponse(total=len(pages), items=[
        WikiPage(**p) for p in pages
    ]))


@app.get("/api/knowledge-bases/{kb_id}/wiki-pages/{page_name}", response_model=ApiResponse)
async def get_wiki_page(kb_id: str, page_name: str):
    """获取Wiki页面内容"""
    # 防止路径遍历攻击：拒绝不安全的页面名称
    if ".." in page_name or "/" in page_name or "\\" in page_name or page_name.startswith("."):
        raise HTTPException(status_code=400, detail="无效的页面名称")
    
    page = await wiki_service.get_wiki_page(kb_id, page_name)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki页面不存在")
    return ApiResponse(data=WikiPageContent(**page))


@app.post("/api/knowledge-bases/{kb_id}/documents/{doc_id}/parse", response_model=ApiResponse)
async def parse_document(kb_id: str, doc_id: str, model_id: Optional[str] = None):
    """手动触发文档解析"""
    import asyncio
    asyncio.create_task(wiki_service.parse_document(kb_id, doc_id, model_id))
    return ApiResponse(message="文档解析任务已启动")


@app.post("/api/knowledge-bases/{kb_id}/wiki-lint", response_model=ApiResponse)
async def lint_wiki(kb_id: str):
    """检查Wiki知识库质量问题"""
    result = await wiki_service.lint_wiki(kb_id)
    return ApiResponse(data=WikiLintResult(**result))


# ==================== 助手API ====================

@app.post("/api/assistants/optimize-prompt", response_model=ApiResponse)
async def optimize_prompt(data: AssistantPromptOptimizeRequest):
    """优化助手提示词"""
    try:
        optimized_prompt = await optimize_assistant_prompt(
            data.name,
            data.description,
            data.system_prompt,
            data.model_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return ApiResponse(data=AssistantPromptOptimizeResponse(optimized_prompt=optimized_prompt))

# ==================== 对话API ====================

@app.post("/api/chat")
async def chat(data: ChatRequest):
    """知识问答（流式输出）"""
    async def generate():
        async for chunk in chat_service.ask(
            data.question,
            data.knowledge_base_ids,
            data.messages,
            data.model_id,
            data.use_web_search,
            data.assistant_prompt,
            data.temporary_upload_ids,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/chat/sync", response_model=ApiResponse)
async def chat_sync(data: ChatRequest):
    """知识问答（同步返回）"""
    answer = await chat_service.ask_sync(
        data.question,
        data.knowledge_base_ids,
        data.messages,
        data.model_id,
        data.use_web_search,
        data.assistant_prompt,
        data.temporary_upload_ids,
    )
    return ApiResponse(data=ChatResponse(answer=answer))


@app.post("/api/chat/export-docx")
async def export_chat_message_docx(data: MessageDocxExportRequest):
    """将助手消息导出为 Word DOCX。"""
    docx_bytes = build_message_docx_bytes(data.title, data.content)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="message.docx"'},
    )


# ==================== 检索API ====================

@app.post("/api/search", response_model=ApiResponse)
async def search(data: SearchRequest):
    """原文检索"""
    result = await search_service.search(data)
    return ApiResponse(data=result)


# ==================== 培训API ====================

@app.post("/api/training/uploads", response_model=ApiResponse)
async def upload_training_document(file: UploadFile = File(...)):
    """上传临时训练文档，不进入知识库。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_TEXT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="暂不支持该文件类型，请上传 PDF、Word（.doc/.docx）、TXT 或 Markdown 文件")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    import uuid

    upload_id = f"upload-{uuid.uuid4().hex[:10]}"
    upload_dir = get_upload_dir(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / Path(file.filename).name
    file_path.write_bytes(content)

    pages = extract_document_pages(file_path)
    preview = ""
    warnings: list[str] = []
    detected_type = suffix.lstrip(".")
    for page in pages:
        text = str(page.get("text", "")).strip()
        if text:
            preview = text[:500]
            break

    joined_text = "\n".join(str(page.get("text", "")) for page in pages).strip()
    if not joined_text:
        raise HTTPException(status_code=400, detail="临时上传文档未提取到可读文本，不支持 OCR")
    if joined_text.startswith("[PDF扫描版:") or "无法提取可读文本" in joined_text or "解析错误" in joined_text:
        raise HTTPException(status_code=400, detail="临时上传文档无法提取可读文本，不支持 OCR")

    if not preview:
        preview = joined_text[:500]

    save_upload_metadata(upload_id, {
        "upload_id": upload_id,
        "filename": file_path.name,
        "original_filename": file.filename,
        "size": len(content),
        "detected_type": detected_type,
        "path": str(file_path),
        "created_at": utc_now_str(),
    })

    return ApiResponse(data=TemporaryTrainingUploadResponse(
        upload_id=upload_id,
        filename=file_path.name,
        size=len(content),
        detected_type=detected_type,
        text_preview=preview,
        warnings=warnings,
    ))


@app.post("/api/training/outline", response_model=ApiResponse)
async def generate_training_outline(payload: dict = Body(...)):
    """生成培训大纲。支持新旧两种请求格式。"""
    request = training_payload_to_request(payload)
    job = create_job("outline", job_id=request.get("job_id"))
    task = asyncio.current_task()
    if task is not None:
        register_running_job(job.job_id, task)
    try:
        response = await training_ppt_service.generate_outline(payload, job_id=job.job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except asyncio.CancelledError:
        cleanup_training_job(job.job_id)
        raise
    finally:
        if task is not None:
            unregister_running_job(job.job_id, task)
    return ApiResponse(data=response)


@app.post("/api/training/generate", response_model=ApiResponse)
async def generate_training_ppt(payload: dict = Body(...)):
    """生成培训PPT。支持确认后的大纲继续生成。"""
    request = training_payload_to_request(payload)
    job = create_job("generate", job_id=request.get("job_id"))
    task = asyncio.current_task()
    if task is not None:
        register_running_job(job.job_id, task)
    try:
        response = await training_ppt_service.generate_ppt(payload, job_id=job.job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except asyncio.CancelledError:
        cleanup_training_job(job.job_id)
        raise
    finally:
        if task is not None:
            unregister_running_job(job.job_id, task)
    return ApiResponse(data=response)


@app.post("/api/training/html", response_model=ApiResponse)
async def generate_training_html(payload: TrainingHtmlGenerateRequest):
    """生成单文件 HTML 汇报展示材料，不复用 PPT/旧 HTML Deck 链路。"""
    if not payload.job_id:
        payload.job_id = f"html-{uuid.uuid4().hex[:10]}"
    task = asyncio.current_task()
    if task is not None:
        register_running_job(payload.job_id, task)
    try:
        result = await training_service.generate_html_material(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except asyncio.CancelledError:
        cleanup_training_job(payload.job_id)
        raise
    finally:
        if task is not None:
            unregister_running_job(payload.job_id, task)

    response = TrainingHtmlGenerateResponse(**result)
    return ApiResponse(data=response)


@app.post("/api/training/cancel/{job_id}")
async def cancel_training_job(job_id: str):
    """取消进行中的培训生成任务并清理中间产物。"""
    cancelled = cancel_running_job(job_id)
    cleanup_training_job(job_id)
    return ApiResponse(data={"job_id": job_id, "cancelled": cancelled})


@app.post("/api/training/cleanup-uploads")
async def cleanup_training_uploads():
    """清理过期的临时训练上传文件。"""
    deleted_count = cleanup_expired_training_uploads()
    return ApiResponse(data={"deleted_count": deleted_count})


@app.get("/api/training/download/{filename}")
async def download_training_ppt(filename: str):
    """安全下载生成的 PPTX。"""
    try:
        file_path = resolve_download_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), filename=file_path.name)


@app.get("/api/training/download-html/{filename}")
async def download_training_html(filename: str, download_name: Optional[str] = Query(default=None)):
    """安全下载生成的 HTML 文件。"""
    try:
        file_path = resolve_training_html_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), filename=download_name or file_path.name, media_type="text/html")


@app.get("/api/training/preview-html/{filename}")
async def preview_training_html(filename: str):
    """安全预览生成的 HTML 文件。"""
    try:
        file_path = resolve_training_html_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    return Response(content=file_path.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")


@app.get("/api/training/download-notes/{filename}")
async def download_training_notes(filename: str):
    """安全下载生成的讲稿备注 DOCX。"""
    try:
        file_path = resolve_download_path(filename, ".docx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), filename=file_path.name)


# ==================== 启动入口 ====================

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
