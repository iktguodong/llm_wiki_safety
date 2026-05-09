"""
安牛后端主应用
FastAPI + 所有业务API
"""

import sys
from pathlib import Path

# 支持从 backend/ 目录直接运行：将项目根目录加入路径
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import config, save_config, get_kb_path
from backend.models import (
    ApiResponse, KnowledgeBaseCreate, KnowledgeBase, KnowledgeBaseListResponse,
    DocumentInfo, DocumentListResponse, DocumentDeleteRequest, DocumentDeletePreview,
    WikiPage, WikiPageContent, WikiPageListResponse, WikiLintResult,
    ChatRequest, ChatResponse,
    SearchRequest, SearchResult,
    TrainingOutline, TrainingConfig,
    ModelValidateRequest, ModelValidateResponse,
    AppConfig
)
from backend.services.knowledge_base import kb_service
from backend.services.document import doc_service
from backend.services.wiki import wiki_service
from backend.services.chat import chat_service
from backend.services.search import search_service
from backend.services.training import training_service
from backend.services.llm import llm_service

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


# ==================== 对话API ====================

@app.post("/api/chat")
async def chat(data: ChatRequest):
    """知识问答（流式输出）"""
    async def generate():
        async for chunk in chat_service.ask(
            data.question,
            data.knowledge_base_ids,
            data.model_id
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/chat/sync", response_model=ApiResponse)
async def chat_sync(data: ChatRequest):
    """知识问答（同步返回）"""
    answer = await chat_service.ask_sync(
        data.question,
        data.knowledge_base_ids,
        data.model_id
    )
    return ApiResponse(data=ChatResponse(answer=answer))


# ==================== 检索API ====================

@app.post("/api/search", response_model=ApiResponse)
async def search(data: SearchRequest):
    """原文检索"""
    result = await search_service.search(data)
    return ApiResponse(data=result)


# ==================== 培训API ====================

@app.post("/api/training/outline", response_model=ApiResponse)
async def generate_training_outline(
    source_type: str,
    source_ids: List[str],
    config: TrainingConfig
):
    """生成培训大纲"""
    outline = await training_service.generate_outline(
        source_type=source_type,
        source_ids=source_ids,
        topic=config.topic,
        audience=config.audience,
        duration=config.duration,
        slide_count=config.slide_count,
        focus_areas=config.focus_areas,
        model_id=config.model_id
    )
    return ApiResponse(data=outline)


@app.post("/api/training/generate")
async def generate_training_ppt(
    source_type: str,
    source_ids: List[str],
    config: TrainingConfig,
    outline: dict
):
    """生成培训PPT"""
    file_path = await training_service.generate_ppt(
        outline=outline,
        topic=config.topic,
        audience=config.audience,
        template=config.template,
        model_id=config.model_id
    )
    return ApiResponse(data={"file_path": file_path})


@app.get("/api/training/download/{filename}")
async def download_training_ppt(filename: str):
    """下载生成的PPT"""
    from backend.config import OUTPUT_DIR
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), filename=filename)


# ==================== 启动入口 ====================

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
