import { useState, useEffect, useCallback } from 'react';
import { Plus, ChevronDown, FileText, Trash2, Eye, Upload, ShieldCheck, X, Sparkles } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { kbApi, docApi, wikiApi } from '../../../lib/api';
import type { KnowledgeBase, DocumentInfo } from '../../../lib/types';

export default function KnowledgeBasePage() {
  const { knowledgeBases, refreshKbs } = useApp();
  const [expandedKb, setExpandedKb] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Record<string, DocumentInfo[]>>({});
  const [loadingDocs, setLoadingDocs] = useState<Record<string, boolean>>({});
  const [uploading, setUploading] = useState(false);
  const [lintResults, setLintResults] = useState<Record<string, { loading: boolean; result?: import('../../../lib/types').WikiLintResult; open: boolean }>>({});
  const [uploadGuides, setUploadGuides] = useState<Record<string, boolean>>({});

  const loadDocs = useCallback(async (kbId: string) => {
    if (loadingDocs[kbId]) return;
    setLoadingDocs(prev => ({ ...prev, [kbId]: true }));
    try {
      const res = await docApi.list(kbId);
      setDocuments(prev => ({ ...prev, [kbId]: res.items }));
    } catch (err) {
      console.error('加载文档失败', err);
    } finally {
      setLoadingDocs(prev => ({ ...prev, [kbId]: false }));
    }
  }, [loadingDocs]);

  useEffect(() => {
    if (expandedKb) {
      loadDocs(expandedKb);
    }
  }, [expandedKb, loadDocs]);

  const handleCreateKb = async () => {
    const name = prompt('请输入知识库名称');
    if (!name) return;
    try {
      await kbApi.create({ name });
      await refreshKbs();
    } catch (err) {
      alert('创建失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleUpload = async (kbId: string, file: File) => {
    setUploading(true);
    try {
      await docApi.upload(kbId, file);
      await loadDocs(kbId);
      await refreshKbs();
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
      <div className="flex-1 overflow-auto px-8 py-6 space-y-4">
        {knowledgeBases.map((kb: KnowledgeBase) => {
          const isExpanded = expandedKb === kb.id;
          const kbDocs = documents[kb.id] ?? [];
          return (
            <div key={kb.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              {/* KB Header */}
              <div
                className="px-6 py-4 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => setExpandedKb(isExpanded ? null : kb.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(79,70,229,0.1)' }}
                    >
                      <FileText className="w-4 h-4 text-indigo-600" />
                    </div>
                    <div>
                      <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>{kb.name}</div>
                      <div className="text-xs text-slate-400 mt-0.5">创建于 {kb.created_at?.split('T')[0]}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                      <div className="flex items-center gap-6 text-sm text-slate-600 mr-4">
                        <div className="text-center">
                          <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.document_count}</div>
                          <div className="text-xs text-slate-400">文档</div>
                        </div>
                        <div className="text-center">
                          <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.wiki_page_count}</div>
                          <div className="text-xs text-slate-400">Wiki页</div>
                        </div>
                        <div className="text-center">
                          <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.total_size_mb.toFixed(1)} MB</div>
                          <div className="text-xs text-slate-400">大小</div>
                        </div>
                      </div>
                    <ChevronDown
                      className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
                        isExpanded ? 'rotate-180' : ''
                      }`}
                    />
                  </div>
                </div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className="border-t border-slate-100 px-6 py-5">
                  {/* Document list header */}
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-sm text-slate-600">文档列表（{kbDocs.length}）</span>
                    <label className={`flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer ${uploading ? 'opacity-50' : ''}`}>
                      <Upload className="w-3.5 h-3.5" />
                      添加文档
                      <input
                        type="file"
                        className="hidden"
                        accept=".pdf,.doc,.docx,.txt,.md"
                        disabled={uploading}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleUpload(kb.id, file);
                          e.target.value = '';
                        }}
                      />
                    </label>
                  </div>

                  {kbDocs.length > 0 ? (
                    <div className="space-y-2 mb-5">
                          {kbDocs.map((doc: DocumentInfo) => (
                        <div
                          key={doc.id}
                          className="flex items-center gap-3 px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 hover:bg-slate-100 transition-colors group"
                        >
                          <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-slate-800 truncate">{doc.file}</div>
                            <div className="text-xs text-slate-400 mt-0.5">
                              {doc.file_size_mb.toFixed(1)} MB · {doc.wiki_pages.length} 个 Wiki 页面 · 上传于 {doc.uploaded_at?.split('T')[0]}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors">
                              <Eye className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteDoc(kb.id, doc.id)}
                              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 text-slate-400 mb-5">
                      <Upload className="w-8 h-8 mb-2 text-slate-300" />
                      <p className="text-sm">暂无文档，点击"添加文档"上传</p>
                    </div>
                  )}

                  {/* 上传后操作引导 */}
                  {uploadGuides[kb.id] && (
                    <div className="mb-4 p-3 bg-indigo-50 border border-indigo-100 rounded-lg flex items-start gap-3">
                      <Sparkles className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1">
                        <p className="text-sm text-indigo-800 font-medium">文档已上传</p>
                        <p className="text-xs text-indigo-600 mt-0.5">系统正在自动解析生成Wiki页面。解析完成后，你可以前往「对话」页面基于知识库提问，或「检索」页面搜索原文。</p>
                      </div>
                      <button onClick={() => dismissGuide(kb.id)} className="text-indigo-400 hover:text-indigo-600">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                    <button
                      onClick={() => handleLint(kb.id)}
                      disabled={lintResults[kb.id]?.loading}
                      className="flex items-center gap-1.5 px-4 py-2 text-sm text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {lintResults[kb.id]?.loading ? '检查中...' : '检查Wiki'}
                    </button>
                    <button
                      onClick={() => handleDeleteKb(kb.id)}
                      className="px-4 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                    >
                      删除知识库
                    </button>
                  </div>

                  {/* Lint 结果面板 */}
                  {lintResults[kb.id]?.open && lintResults[kb.id]?.result && (
                    <div className="mt-4 p-4 bg-slate-50 border border-slate-200 rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-slate-800">Wiki 质量检查结果</h4>
                        <button onClick={() => closeLint(kb.id)} className="text-slate-400 hover:text-slate-600">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-xs text-slate-500 mb-3">{lintResults[kb.id].result!.summary}</p>
                      {lintResults[kb.id].result!.issues.length > 0 ? (
                        <div className="space-y-2 max-h-60 overflow-y-auto">
                          {lintResults[kb.id].result!.issues.map((issue, idx) => (
                            <div key={idx} className={`p-2.5 rounded-lg text-xs border ${
                              issue.severity === 'error'
                                ? 'bg-red-50 border-red-100 text-red-800'
                                : issue.severity === 'warning'
                                ? 'bg-amber-50 border-amber-100 text-amber-800'
                                : 'bg-blue-50 border-blue-100 text-blue-800'
                            }`}>
                              <div className="flex items-center gap-1.5 mb-1">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                  issue.severity === 'error'
                                    ? 'bg-red-100 text-red-700'
                                    : issue.severity === 'warning'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-blue-100 text-blue-700'
                                }`}>
                                  {issue.severity === 'error' ? '错误' : issue.severity === 'warning' ? '警告' : '提示'}
                                </span>
                                <span className="font-medium">{issue.page}</span>
                                <span className="text-slate-400">· {issue.type === 'format' ? '格式' : issue.type === 'link' ? '链接' : issue.type === 'orphan' ? '孤儿页' : issue.type === 'missing_source' ? '来源' : issue.type}</span>
                              </div>
                              <p className="text-slate-600">{issue.message}</p>
                              {issue.suggestion && (
                                <p className="text-slate-400 mt-1">建议：{issue.suggestion}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 p-3 rounded-lg">
                          <ShieldCheck className="w-4 h-4" />
                          Wiki 结构健康，未发现质量问题
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
