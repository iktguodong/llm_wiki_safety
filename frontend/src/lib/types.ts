/**
 * 前后端共享类型定义
 * 与 backend/models.py 保持一致
 */

export interface ApiResponse<T = unknown> {
  code: number;
  success: boolean;
  message: string;
  data: T;
}

export type TrainingSourceType = 'knowledge_base' | 'wiki_page' | 'kb_document' | 'temporary_upload' | 'prompt';
export type TrainingStyle = 'standard_training' | 'management_briefing' | 'frontline_shift_training';
export type SlideType =
  | 'cover'
  | 'agenda'
  | 'toc'
  | 'section_divider'
  | 'content'
  | 'risk_scene'
  | 'legal_requirement'
  | 'workflow'
  | 'control_measures'
  | 'case_discussion'
  | 'checklist'
  | 'quiz'
  | 'summary';
export type VisualType = 'none' | 'cards' | 'two_column' | 'risk_matrix' | 'process_flow' | 'checklist' | 'qa' | 'table';
export type SafetyLevel = 'normal' | 'attention' | 'warning' | 'critical';
export type QualityLevel = 'info' | 'warning' | 'error';

// 知识库
export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  wiki_page_count: number;
  total_size_mb: number;
}

export interface KnowledgeBaseCreate {
  name: string;
  description?: string;
}

export interface KnowledgeBaseListResponse {
  total: number;
  items: KnowledgeBase[];
}

// 文档
export interface DocumentInfo {
  id: string;
  file: string;
  uploaded_at: string;
  file_size_mb: number;
  page_count: number;
  wiki_pages: string[];
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed';
  error_message?: string | null;
}

export interface DocumentListResponse {
  total: number;
  items: DocumentInfo[];
}

export interface DocumentDeletePreview {
  doc_id: string;
  file: string;
  wiki_pages_count: number;
  referenced_pages: string[];
  options: string[];
}

// Wiki
export interface WikiPage {
  name: string;
  title: string;
  summary: string;
  last_updated: string;
  sources: string[];
}

export interface WikiPageContent extends WikiPage {
  content: string;
}

export interface WikiPageListResponse {
  total: number;
  items: WikiPage[];
}

export interface WikiLintIssue {
  type: string;
  severity: 'error' | 'warning' | 'info';
  page: string;
  message: string;
  suggestion: string;
}

export interface WikiLintResult {
  total_pages: number;
  issues: WikiLintIssue[];
  summary: string;
}

// 对话
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  references?: Record<string, string>[];
}

export interface ChatRequest {
  question: string;
  messages?: ChatMessage[];
  knowledge_base_ids: string[];
  model_id?: string;
  use_web_search?: boolean;
  assistant_id?: string;
  assistant_prompt?: string;
}

export interface ChatResponse {
  answer: string;
}

export interface AssistantPromptOptimizeRequest {
  name: string;
  description?: string;
  system_prompt: string;
  model_id?: string;
}

export interface AssistantPromptOptimizeResponse {
  optimized_prompt: string;
}

// 检索
export interface SearchRequest {
  keyword: string;
  knowledge_base_ids?: string[];
}

export interface SearchMatch {
  file: string;
  doc_id: string;  // 文档ID
  kb_id: string;  // 所属知识库ID
  page: number;
  snippet: string;
  score: number;
  highlights: number[];
}

export interface SearchResult {
  query: string;
  total_matches: number;
  results: SearchMatch[];
  results_grouped: Record<string, SearchMatch[]>;  // 按知识库ID分组
}

// 培训
export interface TrainingConfig {
  topic: string;
  audience: string;
  duration: number;
  slide_count: number;
  focus_areas: string[];
  template?: string;
  model_id?: string;
}

export interface TrainingSourceInput {
  type: TrainingSourceType;
  kb_id?: string | null;
  page_name?: string | null;
  document_id?: string | null;
  upload_id?: string | null;
  prompt?: string | null;
  title?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TrainingSourceRef {
  source_type: string;
  source_id?: string | null;
  kb_id?: string | null;
  document_id?: string | null;
  page_name?: string | null;
  upload_id?: string | null;
  title?: string | null;
  locator?: string | null;
  excerpt?: string | null;
  confidence: number;
}

export interface TrainingContentChunk {
  id: string;
  title: string;
  text: string;
  source_refs: TrainingSourceRef[];
  keywords: string[];
  chunk_type: 'wiki' | 'raw_document' | 'temporary_upload' | 'prompt_generated';
}

export interface TrainingContentPack {
  id: string;
  title: string;
  topic: string;
  audience: string;
  duration_minutes: number;
  sources: TrainingSourceInput[];
  chunks: TrainingContentChunk[];
  warnings: string[];
}

export interface TrainingOutlineSection {
  id: string;
  title: string;
  goal: string;
  key_points: string[];
  estimated_minutes: number;
  source_refs: TrainingSourceRef[];
}

export interface TrainingOutlineSlide {
  id: string;
  slide_no: number;
  title: string;
  key_points: string[];
  notes?: string | null;
  layout_hint?: string | null;
  slide_type:
    | 'cover'
    | 'agenda'
    | 'content'
    | 'workflow'
    | 'risk_scene'
    | 'legal_requirement'
    | 'control_measures'
    | 'case_discussion'
    | 'checklist'
    | 'quiz'
    | 'summary';
  source_refs: TrainingSourceRef[];
  visual_type?: VisualType | null;
  safety_level?: SafetyLevel | null;
}

export interface TrainingOutline {
  id: string;
  title: string;
  topic: string;
  audience: string;
  duration_minutes: number;
  style: TrainingStyle;
  slides: TrainingOutlineSlide[];
  sections: TrainingOutlineSection[];
  warnings: string[];
}

export interface SlideSpec {
  id: string;
  slide_no: number;
  slide_type: SlideType;
  title: string;
  subtitle?: string | null;
  key_message?: string | null;
  bullets: string[];
  notes?: string | null;
  visual_type?: VisualType | null;
  source_refs: TrainingSourceRef[];
  safety_level?: SafetyLevel | null;
}

export interface PresentationSpec {
  id: string;
  title: string;
  topic: string;
  audience: string;
  duration_minutes: number;
  style: TrainingStyle;
  template_id: string;
  slides: SlideSpec[];
  quality_warnings: string[];
}

export interface QualityIssue {
  level: QualityLevel;
  code: string;
  message: string;
  slide_id?: string | null;
  suggestion?: string | null;
}

export interface QualityReport {
  passed: boolean;
  issues: QualityIssue[];
  summary: string;
}

export interface PresentationJob {
  job_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  source_mode: string;
  content_pack_path?: string | null;
  outline_path?: string | null;
  spec_path?: string | null;
  pptx_path?: string | null;
  quality_report_path?: string | null;
  download_url?: string | null;
}

export interface TrainingOutlineResponse {
  job_id: string;
  outline: TrainingOutline;
  content_pack_summary: Record<string, unknown>;
  warnings: string[];
}

export interface TrainingGenerateResponse {
  job_id: string;
  status: string;
  presentation: PresentationSpec;
  quality_report: QualityReport;
  download_url: string;
  filename: string;
  notes_download_url?: string | null;
  notes_filename?: string | null;
}

export interface TrainingHtmlGenerateRequest {
  job_id?: string;
  kb_id?: string | null;
  title: string;
  report_date?: string | null;
  presenter?: string | null;
  audience?: string | null;
  requirements?: string | null;
  sources?: TrainingSourceInput[];
  document_ids: string[];
  page_count: number;
}

export interface TrainingHtmlGenerateResponse {
  title: string;
  filename: string;
  download_url: string;
  preview_url?: string | null;
  html: string;
  slide_count: number;
}

export interface TemporaryTrainingUploadResponse {
  upload_id: string;
  filename: string;
  size: number;
  detected_type: string;
  text_preview: string;
  warnings: string[];
}

export interface TrainingOutlineRequest {
  sources: TrainingSourceInput[];
  topic: string;
  audience: string;
  duration_minutes: number;
  slide_count: number;
  style: TrainingStyle;
  focus_areas: string[];
  include_quiz: boolean;
  include_speaker_notes: boolean;
  job_id?: string;
}

export interface TrainingGenerateRequest {
  job_id?: string;
  sources: TrainingSourceInput[];
  outline?: TrainingOutline | null;
  template_id: string;
  include_quiz: boolean;
  include_speaker_notes: boolean;
  topic: string;
  audience: string;
  duration_minutes: number;
  slide_count: number;
  style: TrainingStyle;
  focus_areas: string[];
}

export interface TrainingOutlineLegacyResponse {
  title: string;
  chapters: {
    title: string;
    pages: number;
    points: string[];
  }[];
}

// 配置
export interface ModelProvider {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  models: {
    id: string;
    name: string;
    type: string;
  }[];
}

export interface AppConfig {
  version: string;
  app_name: string;
  current_kb_id: string | null;
  current_model_id: string;
  models: {
    providers: ModelProvider[];
    model_roles: Record<string, string>;
  };
  knowledge_bases: Record<string, unknown>;
  ui: {
    theme: string;
    sidebar_collapsed: boolean;
    last_opened_page: string;
  };
}

export interface ModelValidateRequest {
  provider_id: string;
  api_key: string;
  base_url?: string;
}

export interface ModelValidateResponse {
  valid: boolean;
  message: string;
  models?: string[];
}
