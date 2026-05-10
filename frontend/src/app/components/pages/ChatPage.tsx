import { useState, useRef, useEffect } from 'react';
import { Send, X, ChevronDown, Bot, User, Layers } from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import { useApp } from '../../../lib/context';
import { chatApi } from '../../../lib/api';
import type { KnowledgeBase } from '../../../lib/types';

const initialMessages = [
  {
    role: 'assistant',
    content: `你好！我是安牛知识助手，可以帮助你查询企业安全知识。

**工作机制**：基于知识库提问时，我会优先读取 wiki/index.md 索引了解知识库结构，再结合相关 Wiki 页面为你回答。

你可以这样问我：
• 港口火灾应急响应流程是什么？
• 淹溺事故的现场处置方法有哪些？
• 应急预案的组织架构是怎样的？`,
    time: '09:30',
  },
];

export default function ChatPage() {
  const { knowledgeBases, providers, currentModelId } = useApp();
  const [selectedKbs, setSelectedKbs] = useState<string[]>([]);
  const [selectedModelId, setSelectedModelId] = useState(currentModelId);
  const [modelOpen, setModelOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState(initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) setModelOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    setSelectedModelId(currentModelId);
  }, [currentModelId]);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const handleSend = () => {
    if (!input.trim() || selectedKbs.length === 0 || isLoading) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const question = input;
    setMessages(prev => [...prev, { role: 'user', content: question, time }]);
    setInput('');
    setIsLoading(true);

    // 添加助手占位消息
    setMessages(prev => [...prev, { role: 'assistant', content: '', time }]);

    chatApi.ask(
      { question, knowledge_base_ids: selectedKbs, model_id: selectedModelId },
      (chunk) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
          }
          return prev;
        });
      },
      (err) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: `请求失败: ${err.message}` }];
          }
          return prev;
        });
        setIsLoading(false);
      }
    );
    // 一秒后恢复发送能力（流式输出不阻止输入）
    setTimeout(() => setIsLoading(false), 1000);
  };

  const allModels = providers.flatMap(p => p.models);
  const currentModelName = allModels.find(m => m.id === selectedModelId)?.name || selectedModelId || '默认模型';
  const totalPages = selectedKbs.reduce((sum, id) => {
    const kb = knowledgeBases.find((k: KnowledgeBase) => k.id === id);
    return sum + (kb?.wiki_page_count ?? 0);
  }, 0);

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Top config bar */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-4">
        {/* Knowledge base selector */}
        <Popover.Root>
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-500">引用知识库</span>
          </div>
          <div className="flex items-center gap-2">
            {selectedKbs.map(kbId => {
              const kb = knowledgeBases.find(k => k.id === kbId);
              return kb ? (
                <div
                  key={kbId}
                  className="flex items-center gap-1.5 px-2.5 py-1 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-md text-xs"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0"></span>
                  <span>{kb.name}</span>
                  <button
                    onClick={() => toggleKb(kbId)}
                    className="ml-0.5 text-indigo-400 hover:text-indigo-600 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : null;
            })}
            <Popover.Trigger className="px-2.5 py-1 text-xs text-slate-500 border border-dashed border-slate-300 rounded-md hover:border-indigo-400 hover:text-indigo-600 transition-colors">
              + 添加
            </Popover.Trigger>
          </div>
          <Popover.Portal>
            <Popover.Content
              align="start"
              sideOffset={6}
              className="bg-white rounded-xl shadow-lg border border-slate-200 p-1.5 w-52 z-50"
            >
              {knowledgeBases.map(kb => (
                <label
                  key={kb.id}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 rounded-lg cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedKbs.includes(kb.id)}
                    onChange={() => toggleKb(kb.id)}
                    className="w-3.5 h-3.5 rounded accent-indigo-600"
                  />
                  <span className="flex-1 text-sm text-slate-700">{kb.name}</span>
                  <span className="text-xs text-slate-400">{kb.wiki_page_count}页</span>
                </label>
              ))}
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>

        <div className="h-4 w-px bg-slate-200"></div>

        {/* Model selector */}
        <div ref={modelRef} className="relative flex items-center gap-2">
          <span className="text-sm text-slate-500">模型</span>
          <button
            onClick={() => setModelOpen(!modelOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs border border-slate-200 rounded-md hover:border-slate-300 text-slate-700 transition-colors"
          >
            <span>{currentModelName}</span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>
          {modelOpen && (
            <div className="absolute top-full mt-1.5 left-0 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-50 min-w-[180px]">
              {allModels.map((m) => (
                <button
                  key={m.id}
                  onClick={() => { setSelectedModelId(m.id); setModelOpen(false); }}
                  className={`w-full text-left px-3 py-1.5 text-sm transition-colors hover:bg-slate-50 ${
                    m.id === selectedModelId ? 'text-indigo-600' : 'text-slate-700'
                  }`}
                >
                  {m.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {selectedKbs.length > 0 && (
          <>
            <div className="h-4 w-px bg-slate-200"></div>
            <span className="text-xs text-slate-400">共 {totalPages} 个知识页面</span>
          </>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{
                background: msg.role === 'assistant' ? '#EEF2FF' : '#4F46E5',
              }}
            >
              {msg.role === 'assistant'
                ? <Bot className="w-4 h-4 text-indigo-600" />
                : <User className="w-4 h-4 text-white" />
              }
            </div>
            <div className={`max-w-2xl ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">
                  {msg.role === 'assistant' ? '安牛助手' : '我'}
                </span>
                <span className="text-xs text-slate-300">{msg.time}</span>
              </div>
              <div
                className={`px-4 py-3 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                }`}
              >
                {msg.content}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 px-6 pb-6">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden transition-shadow hover:shadow-md focus-within:shadow-md focus-within:border-indigo-300">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入问题，按 Enter 发送..."
            className="w-full px-4 pt-4 pb-2 resize-none outline-none text-sm text-slate-700 placeholder-slate-400 bg-transparent"
            rows={2}
          />
          <div className="px-3 pb-3 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              {selectedKbs.length === 0
                ? '← 请先在顶部选择知识库再发送'
                : 'Shift + Enter 换行'}
            </span>
            <button
              onClick={handleSend}
              disabled={!input.trim() || selectedKbs.length === 0 || isLoading}
              title={selectedKbs.length === 0 ? '请先选择至少一个知识库' : (isLoading ? '正在生成中...' : '')}
              className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
            >
              <Send className="w-3.5 h-3.5" />
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}