"""
Pydantic数据模型
定义所有API请求和响应的数据结构
"""

from typing import List, Optional, Dict, Any, Literal
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
    doc_parse: str = "deepseek-v4-flash"
    qa_chat: str = "deepseek-v4-flash"
    ppt_gen: str = "deepseek-v4-pro"


class AppConfig(BaseModel):
    """应用配置"""
    version: str = "1.0.0"
    app_name: str = "安牛"
    current_kb_id: Optional[str] = None
    current_model_id: str = "deepseek-v4-flash"
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
    error_message: Optional[str] = None  # 解析失败时的错误信息


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
    messages: List[ChatMessage] = Field(default_factory=list, description="当前会话历史消息")
    knowledge_base_ids: List[str] = Field(default_factory=list, description="引用的知识库ID列表")
    model_id: Optional[str] = None
    use_web_search: bool = False
    assistant_id: Optional[str] = None
    assistant_prompt: Optional[str] = None


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


class SearchMatch(BaseModel):
    """搜索结果匹配项"""
    file: str
    doc_id: str = ""  # 文档ID
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


# ==================== 新版 PPT 工作流模型 ====================

class TrainingSourceInput(BaseModel):
    type: Literal["knowledge_base", "wiki_page", "kb_document", "temporary_upload", "prompt"]
    kb_id: Optional[str] = None
    page_name: Optional[str] = None
    document_id: Optional[str] = None
    upload_id: Optional[str] = None
    prompt: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrainingSourceRef(BaseModel):
    source_type: str
    source_id: Optional[str] = None
    kb_id: Optional[str] = None
    document_id: Optional[str] = None
    page_name: Optional[str] = None
    upload_id: Optional[str] = None
    title: Optional[str] = None
    locator: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: float = 0.0


class TrainingContentChunk(BaseModel):
    id: str
    title: str
    text: str
    source_refs: List[TrainingSourceRef] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    chunk_type: Literal["wiki", "raw_document", "temporary_upload", "prompt_generated"]


class TrainingContentPack(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    sources: List[TrainingSourceInput] = Field(default_factory=list)
    chunks: List[TrainingContentChunk] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TrainingOutlineSectionV2(BaseModel):
    id: str
    title: str
    goal: str
    key_points: List[str] = Field(default_factory=list)
    estimated_minutes: int = 0
    source_refs: List[TrainingSourceRef] = Field(default_factory=list)


class TrainingOutlineV2(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"]
    sections: List[TrainingOutlineSectionV2] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SlideSpec(BaseModel):
    id: str
    slide_no: int
    slide_type: Literal[
        "cover",
        "toc",
        "section_divider",
        "content",
        "risk_scene",
        "legal_requirement",
        "workflow",
        "control_measures",
        "case_discussion",
        "checklist",
        "quiz",
        "summary",
    ]
    title: str
    subtitle: Optional[str] = None
    key_message: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    visual_type: Optional[Literal["none", "cards", "two_column", "risk_matrix", "process_flow", "checklist", "qa", "table"]] = None
    source_refs: List[TrainingSourceRef] = Field(default_factory=list)
    safety_level: Optional[Literal["normal", "attention", "warning", "critical"]] = None


class PresentationSpec(BaseModel):
    id: str
    title: str
    topic: str
    audience: str
    duration_minutes: int
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"]
    template_id: str
    slides: List[SlideSpec] = Field(default_factory=list)
    quality_warnings: List[str] = Field(default_factory=list)


class QualityIssue(BaseModel):
    level: Literal["info", "warning", "error"]
    code: str
    message: str
    slide_id: Optional[str] = None
    suggestion: Optional[str] = None


class QualityReport(BaseModel):
    passed: bool
    issues: List[QualityIssue] = Field(default_factory=list)
    summary: str


class PresentationJob(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    source_mode: str
    content_pack_path: Optional[str] = None
    outline_path: Optional[str] = None
    spec_path: Optional[str] = None
    pptx_path: Optional[str] = None
    quality_report_path: Optional[str] = None
    download_url: Optional[str] = None


class TrainingOutlineRequestV2(BaseModel):
    sources: List[TrainingSourceInput] = Field(default_factory=list)
    topic: str = ""
    audience: str = "一线员工"
    duration_minutes: int = 60
    slide_count: int = 12
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"] = "standard_training"
    focus_areas: List[str] = Field(default_factory=list)
    include_quiz: bool = True
    include_speaker_notes: bool = True
    job_id: Optional[str] = None
    # legacy compatibility
    source_type: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    config: Optional[TrainingConfig] = None


class TrainingOutlineResponse(BaseModel):
    job_id: str
    outline: TrainingOutlineV2
    content_pack_summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class TrainingGenerateRequestV2(BaseModel):
    job_id: Optional[str] = None
    sources: List[TrainingSourceInput] = Field(default_factory=list)
    outline: Optional[TrainingOutlineV2] = None
    template_id: str = "standard_training"
    include_quiz: bool = True
    include_speaker_notes: bool = True
    topic: str = ""
    audience: str = "一线员工"
    duration_minutes: int = 60
    slide_count: int = 12
    style: Literal["standard_training", "management_briefing", "frontline_shift_training"] = "standard_training"
    focus_areas: List[str] = Field(default_factory=list)
    # legacy compatibility
    source_type: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    config: Optional[TrainingConfig] = None


class TrainingGenerateResponse(BaseModel):
    job_id: str
    status: str
    presentation: PresentationSpec
    quality_report: QualityReport
    download_url: str
    filename: str


class TemporaryTrainingUploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int
    detected_type: str
    text_preview: str
    warnings: List[str] = Field(default_factory=list)


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
