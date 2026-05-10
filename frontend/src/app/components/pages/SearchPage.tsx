import { useState } from 'react';
import { Search as SearchIcon, X, FileText, Clock } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { searchApi } from '../../../lib/api';
import type { SearchResult, SearchMatch } from '../../../lib/types';

interface SearchPageProps {
  openReader?: (kbId: string, docId: string, docName: string) => void;
}

const PAGE_SIZE = 10;

export default function SearchPage({ openReader }: SearchPageProps) {
  const { knowledgeBases } = useApp();
  const [selectedKbs, setSelectedKbs] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setShowResults(true);
    setCurrentPage(1);
    try {
      const res = await searchApi.search({
        keyword: query,
        knowledge_base_ids: selectedKbs.length ? selectedKbs : undefined,
      });
      setResults(res);
    } catch (err) {
      setResults({ query: '', total_matches: 0, results: [], results_grouped: {} });
    } finally {
      setLoading(false);
    }
  };

  const highlightText = (text: string) => {
    if (!query.trim()) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return text.replace(
      new RegExp(escaped, 'gi'),
      match => `<mark class="bg-yellow-200 text-slate-900 rounded-sm">${match}</mark>`
    );
  };

  // 基于扁平列表做分页，然后再按 kb_id 分组展示
  const flatResults = results?.results ?? [];
  const totalPages = Math.max(1, Math.ceil(flatResults.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const pageStart = (safePage - 1) * PAGE_SIZE;
  const pageItems = flatResults.slice(pageStart, pageStart + PAGE_SIZE);

  const grouped = pageItems.reduce<Record<string, SearchMatch[]>>((acc, match) => {
    const kbName = knowledgeBases.find(k => k.id === match.kb_id)?.name || match.kb_id || '未知知识库';
    if (!acc[kbName]) acc[kbName] = [];
    acc[kbName].push(match);
    return acc;
  }, {});

  // 计算分页按钮窗口（最多显示 5 个页码）
  const pageNumbers: number[] = [];
  const windowSize = 5;
  let winStart = Math.max(1, safePage - Math.floor(windowSize / 2));
  const winEnd = Math.min(totalPages, winStart + windowSize - 1);
  winStart = Math.max(1, winEnd - windowSize + 1);
  for (let i = winStart; i <= winEnd; i++) pageNumbers.push(i);

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5">
        <h1 className="text-slate-900">原文检索</h1>
        <p className="text-sm text-slate-500 mt-0.5">在知识库文档中精确搜索原文内容</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {/* Search panel */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 shadow-sm">
          {/* KB selection */}
          <div className="mb-5">
            <div className="text-sm text-slate-600 mb-3">搜索范围</div>
            <div className="flex flex-wrap gap-2">
              {knowledgeBases.map(kb => (
                <button
                  key={kb.id}
                  onClick={() => toggleKb(kb.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-all ${
                    selectedKbs.includes(kb.id)
                      ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      selectedKbs.includes(kb.id) ? 'bg-indigo-500' : 'bg-slate-300'
                    }`}
                  />
                  {kb.name}
                  <span className={`text-xs ${selectedKbs.includes(kb.id) ? 'text-indigo-400' : 'text-slate-400'}`}>
                    {kb.document_count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Search input */}
          <div className="relative mb-5">
            <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="输入关键词搜索，如：应急响应流程"
              className="w-full pl-10 pr-10 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-700 placeholder-slate-400"
            />
            {query && (
              <button
                onClick={() => { setQuery(''); setShowResults(false); }}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Search action */}
          <div className="flex items-center justify-end">
            <button
              onClick={handleSearch}
              disabled={!query.trim()}
              className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <SearchIcon className="w-3.5 h-3.5" />
              搜索
            </button>
          </div>
        </div>

        {/* Results */}
        {showResults && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              找到 <span className="font-medium text-slate-900">{results?.total_matches ?? 0}</span> 处匹配
              {loading && <span className="text-xs text-slate-400">搜索中...</span>}
            </div>

            {Object.entries(grouped).map(([kbName, results]) => (
              <div key={kbName}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 bg-indigo-500 rounded-full"></div>
                  <h3 className="text-slate-800">{kbName}</h3>
                  <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{results.length} 条</span>
                </div>
                <div className="space-y-3">
                  {results.map((result, idx) => (
                    <div key={idx} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-slate-400" />
                          <span className="text-sm text-slate-900">{result.file}</span>
                          <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">第 {result.page} 页</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-500 rounded-full"
                              style={{ width: `${Math.round((result.score ?? 0) * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400">{Math.round((result.score ?? 0) * 100)}%</span>
                        </div>
                      </div>
                      <div
                        className="text-sm text-slate-600 leading-relaxed bg-slate-50 rounded-lg px-4 py-3 border border-slate-100 mb-3"
                        dangerouslySetInnerHTML={{ __html: highlightText(result.snippet) }}
                      />
                      <div className="flex gap-4">
                        <button
                          onClick={() => openReader && openReader(result.kb_id, result.doc_id, result.file)}
                          disabled={!result.doc_id}
                          className="text-xs text-indigo-600 hover:text-indigo-700 transition-colors disabled:text-slate-300 disabled:cursor-not-allowed"
                        >
                          查看原文
                        </button>
                        <button className="text-xs text-slate-500 hover:text-slate-700 transition-colors">
                          复制片段
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Pagination */}
            {flatResults.length > PAGE_SIZE && (
              <div className="flex items-center justify-center gap-1 pt-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors disabled:text-slate-300 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                >
                  上一页
                </button>
                {pageNumbers.map(p => (
                  <button
                    key={p}
                    onClick={() => setCurrentPage(p)}
                    className={`w-8 h-8 text-sm rounded-lg transition-colors ${
                      p === safePage
                        ? 'bg-indigo-600 text-white'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors disabled:text-slate-300 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                >
                  下一页
                </button>
              </div>
            )}
          </div>
        )}

        {!showResults && (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400">
            <SearchIcon className="w-10 h-10 mb-3 text-slate-300" />
            <p className="text-sm">输入关键词，在知识库中搜索原文内容</p>
          </div>
        )}
      </div>
    </div>
  );
}
