/**
 * 原文阅读器页面
 * 支持 PDF / Markdown 文档的分页阅读、文本选中高亮和关键词搜索
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Highlighter,
  Search as SearchIcon,
  X,
  FileText,
  ArrowLeft,
  Copy,
  Check,
} from 'lucide-react';
import { docApi } from '../../../lib/api';

interface ReaderPageProps {
  kbId: string;
  docId: string;
  docName: string;
  initialPage?: number;
  onBack?: () => void;
}

interface Highlight {
  id: string;
  text: string;
  page: number;
  color: string;
  createdAt: string;
}

const HIGHLIGHT_COLORS = [
  { label: '黄色', value: 'bg-yellow-200 text-yellow-900' },
  { label: '绿色', value: 'bg-green-200 text-green-900' },
  { label: '蓝色', value: 'bg-blue-200 text-blue-900' },
  { label: '粉色', value: 'bg-pink-200 text-pink-900' },
];

export default function ReaderPage({ kbId, docId, docName, initialPage = 1, onBack }: ReaderPageProps) {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [totalPages, setTotalPages] = useState(0);
  const [fileName, setFileName] = useState(docName);

  // 选中文本
  const [selectedText, setSelectedText] = useState('');
  const [selectedColor, setSelectedColor] = useState(HIGHLIGHT_COLORS[0].value);

  // 高亮标注
  const [highlights, setHighlights] = useState<Highlight[]>([]);

  // 关键词搜索
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searchVisible, setSearchVisible] = useState(false);

  // 复制状态
  const [copied, setCopied] = useState(false);

  const contentRef = useRef<HTMLDivElement>(null);

  const loadDocument = useCallback(async (page: number) => {
    try {
      setIsLoading(true);
      const res = await docApi.getContent(kbId, docId, page);
      setContent(res.content);
      setTotalPages(res.total_pages);
      setFileName(res.file_name || docName);
    } catch (err) {
      console.error('Failed to load document:', err);
      setContent('[文档加载失败，请检查文档是否存在]');
    } finally {
      setIsLoading(false);
    }
  }, [kbId, docId, docName]);

  const loadHighlights = useCallback(async () => {
    try {
      const res = await docApi.getHighlights(kbId, docId);
      setHighlights((res.highlights as Highlight[]) || []);
    } catch {
      // 忽略高亮加载错误
    }
  }, [kbId, docId]);

  useEffect(() => {
    setCurrentPage(initialPage);
  }, [initialPage, kbId, docId]);

  useEffect(() => {
    loadDocument(currentPage);
    loadHighlights();
  }, [currentPage, loadDocument, loadHighlights]);

  const handleTextSelection = () => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() || '';
    setSelectedText(text);
  };

  const handleHighlight = async () => {
    if (!selectedText) return;
    const newHighlight: Highlight = {
      id: `hl-${Date.now()}`,
      text: selectedText,
      page: currentPage,
      color: selectedColor,
      createdAt: new Date().toISOString(),
    };
    const updated = [...highlights, newHighlight];
    setHighlights(updated);
    setSelectedText('');
    // 清除选区
    window.getSelection()?.removeAllRanges();
    // 持久化到后端
    try {
      await docApi.saveHighlights(kbId, docId, updated);
    } catch {
      // 不影响本地操作
    }
  };

  const handleRemoveHighlight = async (id: string) => {
    const updated = highlights.filter(h => h.id !== id);
    setHighlights(updated);
    try {
      await docApi.saveHighlights(kbId, docId, updated);
    } catch {
      // 忽略
    }
  };

  const handleCopySnippet = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /** 在显示内容中高亮搜索关键词 */
  const renderContent = () => {
    let text = content;

    // 高亮已标注的词（当前页）
    const pageHighlights = highlights.filter(h => h.page === currentPage);
    pageHighlights.forEach(h => {
      const escaped = h.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(
        new RegExp(escaped, 'g'),
        `<mark class="${h.color} rounded px-0.5">${h.text}</mark>`
      );
    });

    // 高亮搜索关键词
    if (searchKeyword.trim()) {
      const escaped = searchKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(
        new RegExp(escaped, 'gi'),
        match => `<mark class="bg-orange-300 text-orange-900 rounded px-0.5 ring-1 ring-orange-400">${match}</mark>`
      );
    }

    // 将换行转为 <br>
    return text.replace(/\n/g, '<br />');
  };

  const isPdf = fileName.toLowerCase().endsWith('.pdf');

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* 顶部工具栏 */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3">
        {onBack && (
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            title="返回"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
        )}

        <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <span className="font-medium text-slate-800 text-sm truncate flex-1">{fileName}</span>

        {/* 搜索按钮 */}
        <button
          onClick={() => setSearchVisible(v => !v)}
          className={`p-1.5 rounded-lg transition-colors ${
            searchVisible ? 'bg-indigo-100 text-indigo-600' : 'text-slate-500 hover:bg-slate-100'
          }`}
          title="文档内搜索"
        >
          <SearchIcon className="w-4 h-4" />
        </button>

        {/* 分页控制 */}
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-slate-500 w-20 text-center">
            {currentPage} / {totalPages || '--'}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 搜索栏（可收起） */}
      {searchVisible && (
        <div className="flex-shrink-0 bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2">
          <SearchIcon className="w-3.5 h-3.5 text-amber-500" />
          <input
            type="text"
            value={searchKeyword}
            onChange={e => setSearchKeyword(e.target.value)}
            placeholder="在当前页中搜索..."
            className="flex-1 text-sm bg-transparent outline-none text-amber-900 placeholder-amber-400"
            autoFocus
          />
          {searchKeyword && (
            <button onClick={() => setSearchKeyword('')} className="text-amber-400 hover:text-amber-600">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* 正文区域 */}
        <div
          ref={contentRef}
          className="flex-1 overflow-auto p-6"
          onMouseUp={handleTextSelection}
        >
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-slate-400">
                <div className="w-8 h-8 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm">加载中...</p>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto">
              {isPdf ? (
                /* PDF 以预格式化文本展示 */
                <pre
                  className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
                  dangerouslySetInnerHTML={{ __html: renderContent() }}
                />
              ) : (
                /* Markdown 等其他格式 */
                <div
                  className="prose prose-slate max-w-none bg-white rounded-xl border border-slate-200 p-6 shadow-sm text-sm leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: renderContent() }}
                />
              )}
            </div>
          )}
        </div>

        {/* 右侧高亮面板 */}
        <div className="w-64 flex-shrink-0 border-l border-slate-200 bg-white overflow-auto">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
              高亮标注
            </h3>

            {/* 颜色选择 */}
            <div className="flex gap-1.5 mb-3">
              {HIGHLIGHT_COLORS.map(c => (
                <button
                  key={c.value}
                  title={c.label}
                  onClick={() => setSelectedColor(c.value)}
                  className={`w-5 h-5 rounded-full border-2 transition-all ${
                    selectedColor === c.value
                      ? 'border-slate-600 scale-110'
                      : 'border-transparent'
                  } ${c.value.split(' ')[0]}`}
                />
              ))}
            </div>

            {/* 添加高亮按钮 */}
            <button
              onClick={handleHighlight}
              disabled={!selectedText}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <Highlighter className="w-3.5 h-3.5" />
              {selectedText ? `高亮选中文字` : '请先选中文字'}
            </button>

            {selectedText && (
              <p className="mt-2 text-xs text-slate-500 bg-slate-50 rounded p-2 line-clamp-2">
                "{selectedText}"
              </p>
            )}
          </div>

          {/* 高亮列表 */}
          <div className="p-3 space-y-2">
            {highlights.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">
                暂无高亮标注
                <br />
                选中文字后点击高亮
              </p>
            ) : (
              highlights
                .filter(h => h.page === currentPage)
                .map(h => (
                  <div
                    key={h.id}
                    className={`rounded-lg p-2.5 text-xs ${h.color} group relative`}
                  >
                    <p className="line-clamp-3 leading-relaxed">{h.text}</p>
                    <div className="flex items-center justify-between mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleCopySnippet(h.text)}
                        className="flex items-center gap-1 text-current opacity-60 hover:opacity-100"
                      >
                        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        复制
                      </button>
                      <button
                        onClick={() => handleRemoveHighlight(h.id)}
                        className="text-current opacity-60 hover:opacity-100"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
            )}
            {highlights.filter(h => h.page !== currentPage).length > 0 && (
              <p className="text-xs text-slate-400 text-center pt-2">
                其他页还有 {highlights.filter(h => h.page !== currentPage).length} 条高亮
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 底部状态栏 */}
      <div className="flex-shrink-0 bg-white border-t border-slate-200 px-4 py-1.5 flex items-center justify-between text-xs text-slate-400">
        <span>
          第 {currentPage} 页，共 {totalPages} 页
          {isPdf && ' · PDF 文档'}
        </span>
        <span>
          当前页高亮 {highlights.filter(h => h.page === currentPage).length} 条
          · 全文共 {highlights.length} 条
        </span>
      </div>
    </div>
  );
}
