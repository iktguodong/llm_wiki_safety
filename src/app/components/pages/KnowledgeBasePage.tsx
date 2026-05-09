import { useState } from 'react';
import { Plus, ChevronDown, FileText, Trash2, Eye, Upload, MoreHorizontal } from 'lucide-react';

const mockKnowledgeBases = [
  {
    id: 'kb1',
    name: '港口安全知识库',
    created: '2026-05-09',
    docCount: 12,
    wikiPages: 45,
    size: '128 MB',
    documents: [
      { id: 'doc1', name: '绥中港应急预案.pdf', pages: 45, wikiPages: 12, uploaded: '2026-05-09' },
      { id: 'doc2', name: '安全生产管理制度.docx', pages: 32, wikiPages: 8, uploaded: '2026-05-08' },
    ],
  },
  {
    id: 'kb2',
    name: '安全生产制度库',
    created: '2026-05-08',
    docCount: 8,
    wikiPages: 28,
    size: '85 MB',
    documents: [],
  },
  {
    id: 'kb3',
    name: '消防法规库',
    created: '2026-05-07',
    docCount: 5,
    wikiPages: 18,
    size: '52 MB',
    documents: [],
  },
];

export default function KnowledgeBasePage() {
  const [expandedKb, setExpandedKb] = useState<string | null>('kb1');

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-slate-900">知识库管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">共 {mockKnowledgeBases.length} 个知识库</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">
          <Plus className="w-4 h-4" />
          创建知识库
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6 space-y-4">
        {mockKnowledgeBases.map(kb => {
          const isExpanded = expandedKb === kb.id;
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
                      <div className="text-xs text-slate-400 mt-0.5">创建于 {kb.created}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-6 text-sm text-slate-600 mr-4">
                      <div className="text-center">
                        <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.docCount}</div>
                        <div className="text-xs text-slate-400">文档</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.wikiPages}</div>
                        <div className="text-xs text-slate-400">Wiki页</div>
                      </div>
                      <div className="text-center">
                        <div className="text-slate-900" style={{ fontWeight: 600 }}>{kb.size}</div>
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
                    <span className="text-sm text-slate-600">文档列表（{kb.documents.length}）</span>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors">
                      <Upload className="w-3.5 h-3.5" />
                      添加文档
                    </button>
                  </div>

                  {kb.documents.length > 0 ? (
                    <div className="space-y-2 mb-5">
                      {kb.documents.map(doc => (
                        <div
                          key={doc.id}
                          className="flex items-center gap-3 px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 hover:bg-slate-100 transition-colors group"
                        >
                          <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-slate-800 truncate">{doc.name}</div>
                            <div className="text-xs text-slate-400 mt-0.5">
                              {doc.pages} 页 · {doc.wikiPages} 个 Wiki 页面 · 上传于 {doc.uploaded}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors">
                              <Eye className="w-3.5 h-3.5" />
                            </button>
                            <button className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
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

                  {/* Actions */}
                  <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                    <button className="px-4 py-2 text-sm text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors">
                      进入管理
                    </button>
                    <button className="px-4 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
                      删除知识库
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
