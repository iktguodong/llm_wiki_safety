import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus,
  Database,
  FileText,
  Pencil,
  Trash2,
  Eye,
  Upload,
  ShieldCheck,
  X,
  Sparkles,
  FolderOpen,
} from 'lucide-react';
import { useApp } from '../../../lib/context';
import { kbApi, docApi, wikiApi } from '../../../lib/api';
import type { KnowledgeBase, DocumentInfo, WikiLintResult } from '../../../lib/types';

interface KnowledgeBasePageProps {
  openReader?: (kbId: string, docId: string, docName: string, page?: number) => void;
}

export default function KnowledgeBasePage({ openReader }: KnowledgeBasePageProps) {
  const { knowledgeBases, refreshKbs, currentKbId } = useApp();
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Record<string, DocumentInfo[]>>({});
  const [loadingDocs, setLoadingDocs] = useState<Record<string, boolean>>({});
  const [uploading, setUploading] = useState(false);
  const [lintResults, setLintResults] = useState<Record<string, { loading: boolean; result?: WikiLintResult; open: boolean }>>({});
  const [uploadGuides, setUploadGuides] = useState<Record<string, boolean>>({});
  const [pollVersion, setPollVersion] = useState(0);
  const loadingDocsRef = useRef<Record<string, boolean>>({});

  // silent=true：仅静默刷新数据，不切换 loadingDocs 状态，避免轮询导致整个文档列表反复闪“正在加载文档...”。
  const loadDocs = useCallback(async (kbId: string, silent: boolean = false) => {
    if (loadingDocsRef.current[kbId]) return null;
    loadingDocsRef.current[kbId] = true;
    if (!silent) {
      setLoadingDocs(prev => ({ ...prev, [kbId]: true }));
    }
    try {
      const res = await docApi.list(kbId);
      setDocuments(prev => ({ ...prev, [kbId]: res.items }));
      return res.items;
    } catch (err) {
      console.error('加载文档失败', err);
      return null;
    } finally {
      loadingDocsRef.current[kbId] = false;
      if (!silent) {
        setLoadingDocs(prev => ({ ...prev, [kbId]: false }));
      }
    }
  }, []);

  useEffect(() => {
    if (!knowledgeBases.length) {
      setSelectedKbId(null);
      return;
    }

    const selectedExists = selectedKbId ? knowledgeBases.some(kb => kb.id === selectedKbId) : false;
    if (selectedExists) return;

    const preferredKb = currentKbId && knowledgeBases.some(kb => kb.id === currentKbId)
      ? currentKbId
      : knowledgeBases[0]?.id ?? null;

    setSelectedKbId(preferredKb);
  }, [knowledgeBases, currentKbId, selectedKbId]);

  useEffect(() => {
    if (!selectedKbId) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    // 第一次拉取走非静默（首屏需要看到"正在加载"占位），之后的轮询全部静默，避免列表在 loading 态和内容态之间来回切换出现闪动。
    const tick = async (silent: boolean) => {
      const docs = await loadDocs(selectedKbId, silent);
      if (cancelled || !docs) return;

      const hasPending = docs.some(doc => doc.parse_status === 'pending' || doc.parse_status === 'parsing');
      if (!hasPending) {
        await refreshKbs();
        return;
      }

      timeoutId = setTimeout(() => {
        void tick(true);
      }, 3000);
    };

    void tick(false);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [selectedKbId, pollVersion, loadDocs, refreshKbs]);

  const selectedKb = selectedKbId ? knowledgeBases.find(kb => kb.id === selectedKbId) ?? null : null;
  const selectedDocs = selectedKb ? documents[selectedKb.id] ?? [] : [];
  const selectedLint = selectedKb ? lintResults[selectedKb.id] : undefined;
  const isDocsLoading = selectedKb ? loadingDocs[selectedKb.id] : false;

  const handleCreateKb = async () => {
    const name = prompt('请输入知识库名称');
    if (!name) return;
    try {
      const created = await kbApi.create({ name });
      await refreshKbs();
      setSelectedKbId(created.id);
    } catch (err) {
      alert('创建失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleRenameKb = async (kb: KnowledgeBase) => {
    const nextName = prompt('请输入新的知识库名称', kb.name)?.trim();
    if (!nextName || nextName === kb.name) return;

    try {
      await kbApi.update(kb.id, { name: nextName });
      await refreshKbs();
    } catch (err) {
      alert('修改失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleUpload = async (kbId: string, file: File) => {
    setUploading(true);
    try {
      await docApi.upload(kbId, file);
      await loadDocs(kbId);
      await refreshKbs();
      setPollVersion(v => v + 1);
      // 显示上传后的操作引导
      setUploadGuides(prev => ({ ...prev, [kbId]: true }));
      // 5秒后自动隐藏引导
      setTimeout(() => {
        setUploadGuides(prev => ({ ...prev, [kbId]: false }));
      }, 8000);
    } catch (err) {
      alert('上传失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  const handleLint = async (kbId: string) => {
    setLintResults(prev => ({ ...prev, [kbId]: { loading: true, open: true } }));
    try {
      const result = await wikiApi.lint(kbId);
      setLintResults(prev => ({ ...prev, [kbId]: { loading: false, result, open: true } }));
    } catch (err) {
      alert('检查失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setLintResults(prev => ({ ...prev, [kbId]: { loading: false, open: false } }));
    }
  };

  const closeLint = (kbId: string) => {
    setLintResults(prev => ({ ...prev, [kbId]: { ...prev[kbId], open: false } }));
  };

  const dismissGuide = (kbId: string) => {
    setUploadGuides(prev => ({ ...prev, [kbId]: false }));
  };

  const handleDeleteKb = async (kbId: string) => {
    if (!confirm('确定删除该知识库？此操作不可恢复。')) return;
    try {
      await kbApi.delete(kbId);
      setSelectedKbId(prev => (prev === kbId ? null : prev));
      await refreshKbs();
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleDeleteDoc = async (kbId: string, docId: string) => {
    if (!confirm('确定删除该文档？')) return;
    try {
      await docApi.delete(kbId, docId, true);
      await loadDocs(kbId);
      await refreshKbs();
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const formatDate = (value?: string) => value?.split('T')[0] || '未知';
  const formatDateTime = (value?: string) => value ? value.replace('T', ' ').slice(0, 19) : '未知';

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-slate-900">知识库管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">共 {knowledgeBases.length} 个知识库</p>
        </div>
        <button onClick={handleCreateKb} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">
          <Plus className="w-4 h-4" />
          创建知识库
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden px-8 py-6">
        <div className="h-full grid gap-6 grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)]">
          {/* Left column */}
          <aside className="min-h-0 overflow-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="relative border-b border-slate-200 px-5 py-4">
              <div className="pr-16">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                  <Database className="w-4 h-4 text-indigo-600" />
                  知识库列表
                </div>
              </div>
            </div>

            <div className="p-3 space-y-2">
              {knowledgeBases.length > 0 ? knowledgeBases.map((kb: KnowledgeBase) => {
                const isSelected = selectedKb?.id === kb.id;
                return (
                  <div
                    key={kb.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedKbId(kb.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedKbId(kb.id);
                      }
                    }}
                    className={`group relative w-full rounded-xl border px-4 py-3 pr-12 text-left transition-colors ${
                      isSelected
                        ? 'border-indigo-200 bg-indigo-50 shadow-sm'
                        : 'border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl ${
                        isSelected ? 'bg-indigo-600 text-white' : 'bg-indigo-50 text-indigo-600'
                      }`}>
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-slate-900">{kb.name}</span>
                          {currentKbId === kb.id && (
                            <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                              当前
                            </span>
                          )}
                        </div>
                        {kb.description ? (
                          <p className="mt-1 truncate text-xs text-slate-500">{kb.description}</p>
                        ) : null}
                        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                          <span>{kb.document_count} 文档</span>
                          <span>{kb.wiki_page_count} Wiki页</span>
                          <span>{kb.total_size_mb.toFixed(1)} MB</span>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleRenameKb(kb);
                      }}
                      title="修改知识库名称"
                      aria-label={`修改知识库名称：${kb.name}`}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg border border-slate-200 bg-white p-2 text-slate-500 opacity-0 shadow-sm transition-all hover:bg-slate-50 hover:text-slate-700 group-hover:opacity-100"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              }) : (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
                  <FolderOpen className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-3 text-sm font-medium text-slate-700">还没有知识库</p>
                  <p className="mt-1 text-xs text-slate-500">先创建一个知识库，再上传文档开始整理</p>
                </div>
              )}
            </div>
          </aside>

          {/* Right column */}
          <section className="min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {selectedKb ? (
              <div className="flex h-full min-h-0 flex-col">
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex min-w-0 items-start gap-4">
                      <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                        <Database className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="truncate text-xl font-semibold text-slate-900">{selectedKb.name}</h2>
                          {currentKbId === selectedKb.id && (
                            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                              当前知识库
                            </span>
                          )}
                        </div>
                        {selectedKb.description ? (
                          <p className="mt-1 text-sm text-slate-500">{selectedKb.description}</p>
                        ) : null}
                        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400">
                          <span>创建于 {formatDate(selectedKb.created_at)}</span>
                          <span>更新于 {formatDateTime(selectedKb.updated_at)}</span>
                          <span>ID: {selectedKb.id}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-xs text-slate-500">文档</div>
                      <div className="mt-1 text-lg font-semibold text-slate-900">{selectedKb.document_count}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-xs text-slate-500">Wiki页</div>
                      <div className="mt-1 text-lg font-semibold text-slate-900">{selectedKb.wiki_page_count}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-xs text-slate-500">总大小</div>
                      <div className="mt-1 text-lg font-semibold text-slate-900">{selectedKb.total_size_mb.toFixed(1)} MB</div>
                    </div>
                  </div>
                </div>

                <div className="flex-1 min-h-0 overflow-auto p-6">
                  <div className="space-y-6">
                    <div className="rounded-2xl border border-slate-200 bg-white">
                      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
                        <div>
                          <h3 className="text-sm font-medium text-slate-900">文档列表</h3>
                          <p className="mt-1 text-xs text-slate-500">
                            支持 PDF、Word（.doc/.docx）、TXT、Markdown；扫描版 PDF 不支持
                          </p>
                        </div>
                        <label
                          className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-indigo-600 transition-colors hover:bg-indigo-50 cursor-pointer ${
                            uploading ? 'opacity-50' : ''
                          }`}
                        >
                          <Upload className="h-3.5 w-3.5" />
                          添加文档
                          <input
                            type="file"
                            className="hidden"
                            accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                            disabled={uploading}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleUpload(selectedKb.id, file);
                              e.target.value = '';
                            }}
                          />
                        </label>
                      </div>

                      <div className="p-5">
                        {isDocsLoading ? (
                          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
                            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
                            <p className="mt-3 text-sm text-slate-500">正在加载文档...</p>
                          </div>
                        ) : selectedDocs.length > 0 ? (
                          <div className="space-y-3">
                            {selectedDocs.map((doc: DocumentInfo) => (
                              <div
                                key={doc.id}
                                className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition-colors hover:bg-slate-100"
                              >
                                <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 text-sm text-slate-800">
                                    <span className="truncate font-medium">{doc.file}</span>
                                    {doc.parse_status === 'parsing' && (
                                      <span className="flex-shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700 ring-1 ring-amber-100">解析中</span>
                                    )}
                                    {doc.parse_status === 'pending' && (
                                      <span className="flex-shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 ring-1 ring-slate-200">待解析</span>
                                    )}
                                    {doc.parse_status === 'failed' && (
                                      <span className="flex-shrink-0 rounded bg-red-50 px-1.5 py-0.5 text-[10px] text-red-700 ring-1 ring-red-100">解析失败</span>
                                    )}
                                    {doc.parse_status === 'completed' && (
                                      <span className="flex-shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700 ring-1 ring-emerald-100">已完成</span>
                                    )}
                                  </div>
                                  <div className="mt-0.5 text-xs text-slate-500">
                                    {doc.file_size_mb.toFixed(1)} MB · {doc.wiki_pages.length} 个 Wiki 页面 · 上传于 {formatDateTime(doc.uploaded_at)}
                                  </div>
                                  {doc.parse_status === 'failed' && doc.error_message && (
                                    <div className="mt-1 break-all text-xs text-red-600">失败原因：{doc.error_message}</div>
                                  )}
                                </div>
                                <div className="flex items-center gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100">
                                  <button
                                    onClick={() => openReader && openReader(selectedKb.id, doc.id, doc.file, 1)}
                                    title="查看原文"
                                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-indigo-50 hover:text-indigo-600"
                                  >
                                    <Eye className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteDoc(selectedKb.id, doc.id)}
                                    className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
                            <Upload className="mx-auto h-8 w-8 text-slate-300" />
                            <p className="mt-3 text-sm text-slate-600">暂无文档，点击“添加文档”上传</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {uploadGuides[selectedKb.id] && (
                      <div className="rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3">
                        <div className="flex items-start gap-3">
                          <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0 text-indigo-500" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-indigo-800">文档已上传</p>
                            <p className="mt-0.5 text-xs text-indigo-600">
                              系统正在自动解析生成 Wiki 页面。解析完成后，你可以前往「对话」页面基于知识库提问，或「检索」页面搜索原文。
                            </p>
                          </div>
                          <button onClick={() => dismissGuide(selectedKb.id)} className="text-indigo-400 transition-colors hover:text-indigo-600">
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        onClick={() => handleLint(selectedKb.id)}
                        disabled={lintResults[selectedKb.id]?.loading}
                        className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        {lintResults[selectedKb.id]?.loading ? '检查中...' : '检查 Wiki'}
                      </button>
                      <button
                        onClick={() => handleDeleteKb(selectedKb.id)}
                        className="rounded-lg border border-red-200 px-4 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                      >
                        删除知识库
                      </button>
                    </div>

                    {selectedLint?.open && selectedLint?.result && (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <h4 className="text-sm font-medium text-slate-800">Wiki 质量检查结果</h4>
                          <button onClick={() => closeLint(selectedKb.id)} className="text-slate-400 transition-colors hover:text-slate-600">
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <p className="mb-3 text-xs text-slate-500">{selectedLint.result.summary}</p>
                        {selectedLint.result.issues.length > 0 ? (
                          <div className="max-h-60 space-y-2 overflow-y-auto">
                            {selectedLint.result.issues.map((issue, idx) => (
                              <div
                                key={idx}
                                className={`rounded-xl border p-3 text-xs ${
                                  issue.severity === 'error'
                                    ? 'border-red-100 bg-red-50 text-red-800'
                                    : issue.severity === 'warning'
                                      ? 'border-amber-100 bg-amber-50 text-amber-800'
                                      : 'border-blue-100 bg-blue-50 text-blue-800'
                                }`}
                              >
                                <div className="mb-1 flex items-center gap-1.5">
                                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                                    issue.severity === 'error'
                                      ? 'bg-red-100 text-red-700'
                                      : issue.severity === 'warning'
                                        ? 'bg-amber-100 text-amber-700'
                                        : 'bg-blue-100 text-blue-700'
                                  }`}>
                                    {issue.severity === 'error' ? '错误' : issue.severity === 'warning' ? '警告' : '提示'}
                                  </span>
                                  <span className="font-medium">{issue.page}</span>
                                  <span className="text-slate-400">
                                    · {issue.type === 'format' ? '格式' : issue.type === 'link' ? '链接' : issue.type === 'orphan' ? '孤儿页' : issue.type === 'missing_source' ? '来源' : issue.type}
                                  </span>
                                </div>
                                <p className="text-slate-600">{issue.message}</p>
                                {issue.suggestion && <p className="mt-1 text-slate-400">建议：{issue.suggestion}</p>}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 rounded-xl bg-green-50 p-3 text-sm text-green-700">
                            <ShieldCheck className="h-4 w-4" />
                            Wiki 结构健康，未发现质量问题
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center p-10">
                <div className="max-w-md text-center">
                  <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                    <FolderOpen className="h-7 w-7" />
                  </div>
                  <h2 className="mt-5 text-xl font-semibold text-slate-900">
                    {knowledgeBases.length > 0 ? '从左侧选择一个知识库' : '还没有知识库'}
                  </h2>
                  <p className="mt-2 text-sm text-slate-500">
                    选中后，右侧会显示知识库详情、上传按钮、文档列表和 Wiki 检查入口。
                  </p>
                  <div className="mt-6">
                    <button
                      onClick={handleCreateKb}
                      className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white transition-colors hover:bg-indigo-700"
                    >
                      <Plus className="h-4 w-4" />
                      创建知识库
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
