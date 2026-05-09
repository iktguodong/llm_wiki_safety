import { useState } from 'react';
import { Search as SearchIcon, X, FileText, Clock } from 'lucide-react';

const knowledgeBases = [
  { id: 'kb1', name: '港口安全知识库', docs: 12 },
  { id: 'kb2', name: '安全生产制度库', docs: 8 },
  { id: 'kb3', name: '消防法规库', docs: 5 },
];

const mockResults = [
  {
    kb: '港口安全知识库',
    file: '绥中港应急预案.pdf',
    page: 15,
    relevance: 95,
    snippet: '...发现火情后，立即启动应急响应程序。第一发现人应当在1分钟内向值班室报告，同时使用就近的灭火器材进行初期扑救。应急指挥小组应当在5分钟内到达现场，组织应急响应...',
  },
  {
    kb: '港口安全知识库',
    file: '绥中港应急预案.pdf',
    page: 18,
    relevance: 88,
    snippet: '...三级应急响应分级标准：一级响应（特别重大）、二级响应（重大）、三级响应（较大）。各级响应的具体启动条件由应急指挥小组根据实际情况判定...',
  },
  {
    kb: '安全生产制度库',
    file: '消防安全管理制度.docx',
    page: 8,
    relevance: 82,
    snippet: '...公司建立应急响应机制，明确各部门职责。生产部门负责现场处置，安全部门负责监督响应执行情况...',
  },
];

type SearchMode = 'fuzzy' | 'exact' | 'regex';

const searchModes: { value: SearchMode; label: string }[] = [
  { value: 'fuzzy', label: '模糊匹配' },
  { value: 'exact', label: '精确匹配' },
  { value: 'regex', label: '正则' },
];

export default function SearchPage() {
  const [selectedKbs, setSelectedKbs] = useState(['kb1', 'kb2']);
  const [searchMode, setSearchMode] = useState<SearchMode>('fuzzy');
  const [query, setQuery] = useState('');
  const [showResults, setShowResults] = useState(false);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const handleSearch = () => {
    if (query.trim()) setShowResults(true);
  };

  const highlightText = (text: string) => {
    if (!query.trim()) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return text.replace(
      new RegExp(escaped, 'gi'),
      match => `<mark class="bg-yellow-200 text-slate-900 rounded-sm">${match}</mark>`
    );
  };

  const grouped = mockResults.reduce((acc, r) => {
    if (!acc[r.kb]) acc[r.kb] = [];
    acc[r.kb].push(r);
    return acc;
  }, {} as Record<string, typeof mockResults>);

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
                    {kb.docs}
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

          {/* Search mode + button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
              {searchModes.map(mode => (
                <button
                  key={mode.value}
                  onClick={() => setSearchMode(mode.value)}
                  className={`px-3 py-1 rounded-md text-sm transition-all ${
                    searchMode === mode.value
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
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
              找到 <span className="font-medium text-slate-900">23</span> 处匹配，耗时 0.15 秒
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
                              style={{ width: `${result.relevance}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400">{result.relevance}%</span>
                        </div>
                      </div>
                      <div
                        className="text-sm text-slate-600 leading-relaxed bg-slate-50 rounded-lg px-4 py-3 border border-slate-100 mb-3"
                        dangerouslySetInnerHTML={{ __html: highlightText(result.snippet) }}
                      />
                      <div className="flex gap-4">
                        <button className="text-xs text-indigo-600 hover:text-indigo-700 transition-colors">
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
            <div className="flex items-center justify-center gap-1 pt-2">
              <button className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors">
                上一页
              </button>
              {[1, 2, 3].map(p => (
                <button
                  key={p}
                  className={`w-8 h-8 text-sm rounded-lg transition-colors ${
                    p === 1
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  {p}
                </button>
              ))}
              <button className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors">
                下一页
              </button>
            </div>
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
