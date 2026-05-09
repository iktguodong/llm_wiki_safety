"""
Pydantic数据模型
定义所有API请求和响应的数据结构
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ==================== 通用模型 ====================

class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = 200
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


# ==================== 配置模型 ====================

class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    type: str = "chat"


class ModelProvider(BaseModel):
    """模型服务提供商"""
    id: str
    name: str
    base_url: str
    api_key: str = ""
    models: List[ModelInfo] = []


class ModelRoles(BaseModel):
    """模型用途分配"""
    doc_parse: str = "deepseek-chat"
    qa_chat: str = "deepseek-chat"
    ppt_gen: str = "deepseek-coder"


class AppConfig(BaseModel):
    """应用配置"""
    version: str = "1.0.0"
    app_name: str = "安牛"
    current_kb_id: Optional[str] = None
    current_model_id: str = "deepseek-chat"
    models: Dict[str, Any] = {}
    knowledge_bases: Dict[str, Any] = {}


# ==================== 知识库模型 ====================

class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")


class KnowledgeBase(BaseModel):
    """知识库信息"""
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    document_count: int = 0
    wiki_page_count: int = 0
    total_size_mb: float = 0.0


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""
    total: int
    items: List[KnowledgeBase]


# ==================== 文档模型 ====================

class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    file: str
    uploaded_at: str
    file_size_mb: float
    page_count: int = 0
    wiki_pages: List[str] = []
    parse_status: str = "pending"  # pending, parsing, completed, failed


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    items: List[DocumentInfo]


class DocumentDeleteRequest(BaseModel):
    """删除文档请求"""
    delete_wiki_pages: bool = False  # 是否同时删除关联的Wiki页面


class DocumentDeletePreview(BaseModel):
    """删除文档预览"""
    doc_id: str
    file: str
    wiki_pages_count: int
    referenced_pages: List[str] = []
    options: List[str] = ["仅删除文档", "删除文档及所有关联Wiki页面"]


# ==================== Wiki模型 ====================

class WikiPage(BaseModel):
    """Wiki页面信息"""
    name: str
    title: str
    summary: str = ""
    last_updated: str
    sources: List[str] = []


class WikiPageContent(WikiPage):
    """Wiki页面内容"""
    content: str


class WikiPageListResponse(BaseModel):
    """Wiki页面列表响应"""
    total: int
    items: List[WikiPage]


class WikiLintIssue(BaseModel):
    """Wiki检查问题项"""
    type: str  # format, link, orphan, outdated, contradiction, missing_source
    severity: str  # error, warning, info
    page: str
    message: str
    suggestion: str = ""


class WikiLintResult(BaseModel):
    """Wiki检查结果"""
    total_pages: int
    issues: List[WikiLintIssue]
    summary: str


# ==================== 对话模型 ====================

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # user, assistant
    content: str
    timestamp: str
    references: List[Dict[str, str]] = []


class ChatRequest(BaseModel):
    """对话请求"""
    model_config = ConfigDict(protected_namespaces=())
    
    question: str = Field(..., min_length=1, description="用户问题")
    knowledge_base_ids: List[str] = Field(..., min_length=1, description="引用的知识库ID列表")
    model_id: Optional[str] = None


class ChatResponse(BaseModel):
    """对话响应"""
    answer: str
    references: List[Dict[str, str]] = []
    confidence: str = "high"  # high, medium, low


# ==================== 检索模型 ====================

class SearchRequest(BaseModel):
    """检索请求"""
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    knowledge_base_ids: List[str] = Field(default=[], description="搜索范围知识库ID列表")
    mode: str = "fuzzy"  # fuzzy, exact, regex


class SearchMatch(BaseModel):
    """搜索结果匹配项"""
    file: str
    kb_id: str = ""  # 所属知识库ID
    page: int
    snippet: str
    score: float
    highlights: List[int] = []


class SearchResult(BaseModel):
    """检索结果"""
    query: str
    total_matches: int
    results: List[SearchMatch]
    results_grouped: Dict[str, List[SearchMatch]] = {}  # 按知识库ID分组的结果


# ==================== 培训模型 ====================

class TrainingSource(BaseModel):
    """培训数据来源"""
    type: str  # knowledge_base, uploaded_document, new_document
    ids: List[str] = []


class TrainingConfig(BaseModel):
    """培训配置"""
    model_config = ConfigDict(protected_namespaces=())
    
    topic: str = Field(..., min_length=1, description="培训主题")
    audience: str = "一线作业人员"
    duration: int = 60
    slide_count: int = 20
    focus_areas: List[str] = ["理论知识", "操作流程", "案例分析"]
    template: str = "公司标准模板"
    model_id: Optional[str] = None


class TrainingOutlineRequest(BaseModel):
    """生成大纲请求"""
    source: TrainingSource
    config: TrainingConfig


class TrainingOutline(BaseModel):
    """PPT大纲"""
    title: str
    chapters: List[Dict[str, Any]]
    total_slides: int
    estimated_duration: int


class TrainingGenerateRequest(BaseModel):
    """生成PPT请求"""
    source: TrainingSource
    config: TrainingConfig
    outline: TrainingOutline


class TrainingJob(BaseModel):
    """培训生成任务"""
    job_id: str
    status: str  # pending, extracting, generating, completed, failed
    progress: int = 0
    message: str = ""
    output_file: Optional[str] = None
    created_at: str


# ==================== 设置模型 ====================

class ModelValidateRequest(BaseModel):
    """验证模型请求"""
    provider_id: str
    api_key: str
    base_url: str


class ModelValidateResponse(BaseModel):
    """验证模型响应"""
    valid: bool
    message: str
    available_models: List[str] = []
