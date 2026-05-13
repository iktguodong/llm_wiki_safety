import { useEffect, useState } from 'react';
import { Search as SearchIcon, X, FileText, Clock, ChevronDown, Layers, History } from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import { useApp } from '../../../lib/context';
import { searchApi } from '../../../lib/api';
import type { SearchResult, SearchMatch } from '../../../lib/types';

interface SearchPageProps {
  openReader?: (kbId: string, docId: string, docName: string, page?: number) => void;
}

const PAGE_SIZE = 10;
const STORAGE_KEYS = {
  state: 'search-page-state-v1',
  history: 'search-page-history-v1',
};

type SearchState = {
  query: string;
  selectedKbs: string[];
  results: SearchResult | null;
  showResults: boolean;
  currentPage: number;
};

type SearchHistoryItem = {
  id: string;
  query: string;
  selectedKbs: string[];
  totalMatches: number;
  time: string;
};

function readLocal<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : fallback;
  } catch {
    return fallback;
  }
}

function writeLocal<T>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore
  }
}

export default function SearchPage({ openReader }: SearchPageProps) {
  const { knowledgeBases } = useApp();
  const [selectedKbs, setSelectedKbs] = useState<string[]>(() => readLocal<SearchState>(STORAGE_KEYS.state, {
    query: '',
    selectedKbs: [],
    results: null,
    showResults: false,
    currentPage: 1,
  }).selectedKbs);
  const [query, setQuery] = useState(() => readLocal<SearchState>(STORAGE_KEYS.state, {
    query: '',
    selectedKbs: [],
    results: null,
    showResults: false,
    currentPage: 1,
  }).query);
  const [results, setResults] = useState<SearchResult | null>(() => readLocal<SearchState>(STORAGE_KEYS.state, {
    query: '',
    selectedKbs: [],
    results: null,
    showResults: false,
    currentPage: 1,
  }).results);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(() => readLocal<SearchState>(STORAGE_KEYS.state, {
    query: '',
    selectedKbs: [],
    results: null,
    showResults: false,
    currentPage: 1,
  }).showResults);
  const [currentPage, setCurrentPage] = useState(() => readLocal<SearchState>(STORAGE_KEYS.state, {
    query: '',
    selectedKbs: [],
    results: null,
    showResults: false,
    currentPage: 1,
  }).currentPage);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>(
    () => readLocal<SearchHistoryItem[]>(STORAGE_KEYS.history, [])
  );

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  useEffect(() => {
    if (selectedKbs.length === 0) {
      setShowResults(false);
      setResults(null);
      setCurrentPage(1);
    }
  }, [selectedKbs.length]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.state, { query, selectedKbs, results, showResults, currentPage });
  }, [query, selectedKbs, results, showResults, currentPage]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.history, searchHistory);
  }, [searchHistory]);

  const handleSearch = async () => {
    if (!query.trim() || selectedKbs.length === 0) return;
    setLoading(true);
    setShowResults(true);
    setCurrentPage(1);
    try {
      const res = await searchApi.search({
        keyword: query,
        knowledge_base_ids: selectedKbs,
      });
      setResults(res);
      setSearchHistory(prev => {
        const next = [
          {
            id: `${Date.now()}`,
            query,
            selectedKbs: [...selectedKbs],
            totalMatches: res.total_matches,
            time: new Date().toLocaleString(),
          },
          ...prev.filter(item => item.query !== query || item.selectedKbs.join(',') !== selectedKbs.join(',')),
        ];
        return next.slice(0, 12);
      });
    } catch (err) {
      setResults({ query: '', total_matches: 0, results: [], results_grouped: {} });
    } finally {
      setLoading(false);
    }
  };

  const restoreHistory = async (item: SearchHistoryItem) => {
    setSelectedKbs(item.selectedKbs);
    setQuery(item.query);
    setShowResults(true);
    setCurrentPage(1);
    setHistoryOpen(false);
    try {
      const res = await searchApi.search({
        keyword: item.query,
        knowledge_base_ids: item.selectedKbs,
      });
      setResults(res);
    } catch {
      // keep current state
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
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-slate-900">原文检索</h1>
          <p className="text-sm text-slate-500 mt-0.5">在选定知识库文档中搜索原文内容</p>
        </div>
        <Popover.Root open={historyOpen} onOpenChange={setHistoryOpen}>
          <Popover.Trigger asChild>
            <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors">
              <History className="w-4 h-4" />
              历史记录
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              align="end"
              sideOffset={8}
              className="z-50 w-96 rounded-xl border border-slate-200 bg-white p-3 shadow-lg"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-slate-800">搜索历史</div>
                <button
                  onClick={() => setSearchHistory([])}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  清空
                </button>
              </div>
              <div className="max-h-72 overflow-auto space-y-2">
                {searchHistory.length > 0 ? searchHistory.map(item => {
                  const kbNames = item.selectedKbs
                    .map(id => knowledgeBases.find(k => k.id === id)?.name || id)
                    .join('、');
                  return (
                    <button
                      key={item.id}
                      onClick={() => restoreHistory(item)}
                      className="w-full text-left rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50 transition-colors"
                    >
                      <div className="text-sm text-slate-800 truncate">{item.query}</div>
                      <div className="mt-1 text-xs text-slate-400 flex items-center justify-between gap-2">
                        <span className="truncate">{kbNames || '未选择知识库'}</span>
                        <span className="flex-shrink-0">{item.totalMatches} 条 · {item.time}</span>
                      </div>
                    </button>
                  );
                }) : (
                  <div className="py-8 text-center text-sm text-slate-400">暂无搜索历史</div>
                )}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {/* Search panel */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 shadow-sm">
          {/* Search input */}
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入关键词搜索，如：应急响应流程"
                className="w-full pl-11 pr-10 py-3.5 border border-slate-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-700 placeholder-slate-400"
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
            <button
              onClick={handleSearch}
              disabled={!query.trim() || selectedKbs.length === 0}
              className="flex h-12 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40 transition-colors md:shrink-0"
            >
              <SearchIcon className="w-3.5 h-3.5" />
              搜索
            </button>
          </div>

          {/* Search scope */}
          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-4">
            <div className="flex flex-col gap-3">
              <div className="text-sm text-slate-700" style={{ fontWeight: 500 }}>搜索范围</div>
              <div className="flex flex-wrap items-center gap-2">
                <Popover.Root>
                  <Popover.Trigger asChild>
                    <button className="flex h-10 w-fit items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 text-sm text-indigo-600 transition-colors hover:bg-indigo-50">
                      <Layers className="w-4 h-4" />
                      选择知识库
                      <ChevronDown className="w-3.5 h-3.5 text-indigo-400" />
                    </button>
                  </Popover.Trigger>
                  <Popover.Portal>
                    <Popover.Content
                      sideOffset={8}
                      align="start"
                      className="z-50 w-72 rounded-xl border border-slate-200 bg-white p-2 shadow-lg"
                    >
                      {knowledgeBases.length > 0 ? (
                        <div className="max-h-64 overflow-auto">
                          {knowledgeBases.map(kb => {
                            const isSelected = selectedKbs.includes(kb.id);
                            return (
                              <button
                                key={kb.id}
                                onClick={() => toggleKb(kb.id)}
                                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                                  isSelected ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50 text-slate-700'
                                }`}
                              >
                                <span className={`w-2 h-2 rounded-full ${isSelected ? 'bg-indigo-500' : 'bg-slate-300'}`} />
                                <span className="flex-1 text-sm">{kb.name}</span>
                                <span className="text-xs text-slate-400">{kb.document_count}</span>
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="px-3 py-4 text-center text-sm text-slate-400">暂无可选知识库</div>
                      )}
                    </Popover.Content>
                  </Popover.Portal>
                </Popover.Root>

                {selectedKbs.length > 0 ? (
                  selectedKbs.map(kbId => {
                    const kb = knowledgeBases.find(item => item.id === kbId);
                    return kb ? (
                      <button
                        key={kb.id}
                        onClick={() => toggleKb(kb.id)}
                        className="flex h-10 items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-100/90 px-3 text-sm text-indigo-700 shadow-sm transition-colors hover:bg-indigo-100"
                      >
                        <span className="w-2 h-2 rounded-full bg-indigo-500" />
                        {kb.name}
                        <X className="w-3.5 h-3.5" />
                      </button>
                    ) : null;
                  })
                ) : (
                  <div className="text-xs text-slate-400">当前未选择知识库，请先选择范围后再搜索。</div>
                )}
              </div>
            </div>
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
                          onClick={() => openReader && openReader(result.kb_id, result.doc_id, result.file, result.page)}
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
