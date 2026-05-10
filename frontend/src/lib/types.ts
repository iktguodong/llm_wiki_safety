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
export interface ChatRequest {
  question: string;
  knowledge_base_ids: string[];
  model_id?: string;
  use_web_search?: boolean;
  assistant_id?: string;
  assistant_prompt?: string;
}

export interface ChatResponse {
  answer: string;
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

export interface TrainingOutline {
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
