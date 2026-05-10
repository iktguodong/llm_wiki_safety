import { useState, useRef, useEffect } from 'react';
import {
  Send,
  X,
  ChevronDown,
  Bot,
  User,
  Layers,
  History,
  Plus,
  Globe,
  Copy,
  RefreshCw,
  Download,
  MoreHorizontal,
  Eraser,
} from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import { useApp } from '../../../lib/context';
import { chatApi } from '../../../lib/api';
import type { KnowledgeBase } from '../../../lib/types';
import type { AssistantDefinition } from '../../data/assistants';

const initialMessages = [
  {
    role: 'assistant',
    content: `你好！我是安牛知识助手，可以帮助你查询企业安全知识。
你可以这样问我：
• 港口火灾应急响应流程是什么？
• 淹溺事故的现场处置方法有哪些？
• 应急预案的组织架构是怎样的？`,
    time: '09:30',
  },
];

function normalizeAssistantText(text: string) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/\(\s*来源:\s*([^)]+)\s*\)/g, '来源：$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const STORAGE_KEYS = {
  current: 'chat-current-state-v1',
  history: 'chat-history-v1',
};

type ChatSession = {
  id: string;
  messages: typeof initialMessages;
  selectedKbs: string[];
  modelId: string;
  useWebSearch: boolean;
  assistantId?: string | null;
  assistantName?: string;
  contextCleared: boolean;
  title: string;
  time: string;
};

interface ChatPageProps {
  activeAssistant?: AssistantDefinition | null;
}

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

function preview(text: string, max = 28) {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

export default function ChatPage({ activeAssistant }: ChatPageProps) {
  const { knowledgeBases, providers, currentModelId } = useApp();
  const [selectedKbs, setSelectedKbs] = useState<string[]>(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
  }).selectedKbs);
  const [selectedModelId, setSelectedModelId] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).modelId || currentModelId);
  const [modelOpen, setModelOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).messages || initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatSession[]>(() => readLocal(STORAGE_KEYS.history, []));
  const [useWebSearch, setUseWebSearch] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).useWebSearch ?? false);
  const [contextCleared, setContextCleared] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
    contextCleared: false,
  }).contextCleared ?? false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef(messages);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    messagesRef.current = messages;
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

  useEffect(() => {
    writeLocal(STORAGE_KEYS.current, {
      messages,
      selectedKbs,
      modelId: selectedModelId,
      useWebSearch,
      assistantId: activeAssistant?.id ?? null,
      contextCleared,
    });
  }, [messages, selectedKbs, selectedModelId, useWebSearch, activeAssistant, contextCleared]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.history, chatHistory);
  }, [chatHistory]);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const newConversation = () => {
    setMessages(initialMessages);
    setInput('');
    setContextCleared(false);
    setHistoryOpen(false);
  };

  const clearContext = () => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    setContextCleared(true);
    setMessages(prev => [
      ...prev,
      {
        role: 'assistant',
        content: '已清除当前上下文。接下来的回答将从新的上下文开始。',
        time,
      },
    ]);
  };

  const restoreSession = (session: ChatSession) => {
    setMessages(session.messages);
    setSelectedKbs(session.selectedKbs);
    setSelectedModelId(session.modelId || currentModelId);
    setUseWebSearch(session.useWebSearch ?? false);
    setContextCleared(session.contextCleared ?? false);
    setHistoryOpen(false);
  };

  useEffect(() => {
    if (!activeAssistant) return;
    if (activeAssistant.default_model_id) {
      setSelectedModelId(activeAssistant.default_model_id);
    }
    if (activeAssistant.default_knowledge_base_ids.length > 0) {
      setSelectedKbs(activeAssistant.default_knowledge_base_ids);
    }
    setUseWebSearch(activeAssistant.use_web_search);
  }, [activeAssistant]);

  const handleSend = (questionOverride?: string) => {
    const question = (questionOverride ?? input).trim();
    if (!question || isLoading) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    setMessages(prev => [...prev, { role: 'user', content: question, time }]);
    if (!questionOverride) setInput('');
    setIsLoading(true);

    // 添加助手占位消息
    setMessages(prev => [...prev, { role: 'assistant', content: '', time }]);

    chatApi.ask(
      {
        question,
        knowledge_base_ids: selectedKbs,
        model_id: selectedModelId,
        use_web_search: useWebSearch,
        assistant_id: activeAssistant?.id,
        assistant_prompt: activeAssistant?.system_prompt,
      },
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
      },
      () => {
        setTimeout(() => {
          const snapshotMessages = messagesRef.current;
          setChatHistory(prev => {
            const snapshot: ChatSession = {
              id: `${Date.now()}`,
              messages: snapshotMessages,
              selectedKbs: [...selectedKbs],
              modelId: selectedModelId,
              useWebSearch,
              assistantId: activeAssistant?.id ?? null,
              assistantName: activeAssistant?.name,
              contextCleared,
              title: preview(question),
              time,
            };
            const next = [
              snapshot,
              ...prev.filter(item => item.title !== snapshot.title || item.time !== snapshot.time),
            ];
            return next.slice(0, 12);
          });
        }, 0);
      }
    );
    // 一秒后恢复发送能力（流式输出不阻止输入）
    setTimeout(() => setIsLoading(false), 1000);
  };

  const copyMessage = (text: string) => {
    navigator.clipboard?.writeText(normalizeAssistantText(text));
  };

  const exportMessage = (text: string, idx: number) => {
    const blob = new Blob([normalizeAssistantText(text)], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `安牛回答-${idx + 1}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const regenerateMessage = (idx: number) => {
    for (let i = idx - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.role === 'user') {
        handleSend(msg.content);
        return;
      }
    }
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
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <Popover.Root>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Layers className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-500">引用知识库</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap min-w-0">
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

          <div className="h-4 w-px bg-slate-200 flex-shrink-0"></div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <Bot className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-500">助手</span>
            <span className="px-2.5 py-1 text-xs rounded-md bg-slate-50 border border-slate-200 text-slate-700">
              {activeAssistant?.name || '默认助手'}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-200 flex-shrink-0"></div>

          <div ref={modelRef} className="relative flex items-center gap-2 flex-shrink-0">
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
              <div className="h-4 w-px bg-slate-200 flex-shrink-0"></div>
              <span className="text-xs text-slate-400 flex-shrink-0">共 {totalPages} 个知识页面</span>
            </>
          )}
        </div>

        <Popover.Root open={historyOpen} onOpenChange={setHistoryOpen}>
          <Popover.Trigger asChild>
            <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors flex-shrink-0">
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
                <div className="text-sm font-medium text-slate-800">对话历史</div>
                <button
                  onClick={() => setChatHistory([])}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  清空
                </button>
              </div>
              <div className="max-h-72 overflow-auto space-y-2">
                {chatHistory.length > 0 ? chatHistory.map(session => (
                  <button
                    key={session.id}
                    onClick={() => restoreSession(session)}
                    className="w-full text-left rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50 transition-colors"
                  >
                    <div className="text-sm text-slate-800 truncate">{session.title}</div>
                    <div className="mt-1 text-xs text-slate-400 flex items-center justify-between gap-2">
                      <span className="truncate">
                        {[
                          session.assistantName || '默认助手',
                          session.selectedKbs.map(id => knowledgeBases.find(k => k.id === id)?.name || id).join('、') || '纯模型问答',
                          session.useWebSearch ? '联网搜索' : '',
                        ].filter(Boolean).join(' · ')}
                      </span>
                      <span className="flex-shrink-0">{session.time}</span>
                    </div>
                  </button>
                )) : (
                  <div className="py-8 text-center text-sm text-slate-400">暂无对话历史</div>
                )}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
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
                {msg.role === 'assistant' ? normalizeAssistantText(msg.content) : msg.content}
              </div>
              <div className="flex items-center gap-1 text-slate-400">
                <button
                  onClick={() => copyMessage(msg.content)}
                  title="复制"
                  className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                {msg.role === 'assistant' && idx > 0 && (
                  <button
                    onClick={() => regenerateMessage(idx)}
                    title="重新生成"
                    className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                )}
                {msg.role === 'assistant' && (
                  <button
                    onClick={() => exportMessage(msg.content, idx)}
                    title="导出"
                    className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  title="更多"
                  className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors"
                >
                  <MoreHorizontal className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 px-6 pb-6">
        <div className="mb-2 text-xs text-slate-400">
          {selectedKbs.length === 0
            ? (useWebSearch ? '已开启联网搜索，Shift + Enter 换行' : '直接使用模型问答，Shift + Enter 换行')
            : (useWebSearch ? '基于知识库并结合联网搜索，Shift + Enter 换行' : '基于知识库问答，Shift + Enter 换行')}
        </div>
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
          <div className="px-3 pb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
              <button
                onClick={() => setUseWebSearch(prev => !prev)}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  useWebSearch
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                    : 'text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                <Globe className="w-3.5 h-3.5" />
                联网搜索
              </button>
              <button
                onClick={newConversation}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                新建对话
              </button>
              <button
                onClick={clearContext}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <Eraser className="w-3.5 h-3.5" />
                清除上下文
              </button>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                title={isLoading ? '正在生成中...' : ''}
                className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                发送
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
