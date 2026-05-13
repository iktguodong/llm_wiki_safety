import { useState, useRef, useEffect } from 'react';
import {
  Send,
  X,
  ChevronDown,
  User,
  Layers,
  Plus,
  Globe,
  Copy,
  RefreshCw,
  Download,
  MoreHorizontal,
  Eraser,
  MessageSquare,
  Trash2,
  Upload,
} from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import { useApp } from '../../../lib/context';
import { chatApi, docApi } from '../../../lib/api';
import { buildChatMemory } from '../../lib/chat-memory';
import {
  acquireConversationLock,
  isConversationLocked as isConversationLockedNow,
  useConversationLock,
} from '../../lib/conversation-lock';
import { normalizeAssistantText, renderAssistantBubble } from '../../lib/chat-render';
import LogoMark from '../LogoMark';
import type { KnowledgeBase } from '../../../lib/types';

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

const STORAGE_KEYS = {
  current: 'chat-current-state-v1',
  history: 'chat-history-v2',
};

type ChatSession = {
  id: string;
  messages: typeof initialMessages;
  selectedKbs: string[];
  modelId: string;
  useWebSearch: boolean;
  contextCleared: boolean;
  title: string;
  time: string;
};

const CURRENT_SESSION_ID = 'current';
const CONTEXT_RESET_MESSAGE = '已清除当前上下文。接下来的回答将从新的上下文开始。';

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

function getConversationTitle(messages: Array<{ role: string; content: string }>, fallback = '当前对话') {
  let startIndex = 0;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === 'assistant' && message.content.includes(CONTEXT_RESET_MESSAGE)) {
      startIndex = i + 1;
      break;
    }
  }

  const firstUserMessage = messages.slice(startIndex).find(message => message.role === 'user' && message.content.trim());
  return preview(firstUserMessage?.content || fallback);
}

export default function ChatPage() {
  const { knowledgeBases, providers, currentModelId } = useApp();
  const isConversationLocked = useConversationLock();
  const [draftSelectedKbs, setDraftSelectedKbs] = useState<string[]>(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
  }).selectedKbs);
  const [draftSelectedModelId, setDraftSelectedModelId] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).modelId || currentModelId);
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
  const [draftMessages, setDraftMessages] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).messages || initialMessages);
  const [messages, setMessages] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).messages || initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatSession[]>(() => readLocal(STORAGE_KEYS.history, []));
  const [draftSessionTitle, setDraftSessionTitle] = useState(() => getConversationTitle(readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
    contextCleared: false,
  }).messages || initialMessages));
  const [currentSessionTitle, setCurrentSessionTitle] = useState(() => getConversationTitle(readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
    contextCleared: false,
  }).messages || initialMessages));
  const [activeSessionId, setActiveSessionId] = useState<string>(CURRENT_SESSION_ID);
  const [draftUseWebSearch, setDraftUseWebSearch] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).useWebSearch ?? false);
  const [useWebSearch, setUseWebSearch] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
  }).useWebSearch ?? false);
  const [draftContextCleared, setDraftContextCleared] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
    contextCleared: false,
  }).contextCleared ?? false);
  const [contextCleared, setContextCleared] = useState(() => readLocal(STORAGE_KEYS.current, {
    messages: initialMessages,
    selectedKbs: [],
    modelId: currentModelId,
    useWebSearch: false,
    contextCleared: false,
  }).contextCleared ?? false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const messagesRef = useRef(messages);
  const releaseSendLockRef = useRef<null | (() => void)>(null);

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
    setDraftSelectedModelId(currentModelId);
  }, [currentModelId]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.current, {
      messages: draftMessages,
      selectedKbs: draftSelectedKbs,
      modelId: draftSelectedModelId,
      useWebSearch: draftUseWebSearch,
      contextCleared: draftContextCleared,
    });
  }, [draftMessages, draftSelectedKbs, draftSelectedModelId, draftUseWebSearch, draftContextCleared]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.history, chatHistory);
  }, [chatHistory]);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev => {
      const next = prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId];
      if (activeSessionId === CURRENT_SESSION_ID) {
        setDraftSelectedKbs(next);
      }
      return next;
    });
  };

  const handleUploadDocument = async (file?: File | null) => {
    const targetKbId = selectedKbs[0];
    if (!targetKbId) {
      window.alert('请先在顶部选择一个知识库，再上传文档。');
      return;
    }
    if (!file) return;
    try {
      await docApi.upload(targetKbId, file);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : '上传失败');
    } finally {
      if (uploadInputRef.current) {
        uploadInputRef.current.value = '';
      }
    }
  };

  const openCurrentConversation = () => {
    setMessages(draftMessages);
    setSelectedKbs(draftSelectedKbs);
    setSelectedModelId(draftSelectedModelId);
    setUseWebSearch(draftUseWebSearch);
    setContextCleared(draftContextCleared);
    setCurrentSessionTitle(draftSessionTitle);
    setActiveSessionId(CURRENT_SESSION_ID);
  };

  const resetCurrentConversation = () => {
    setDraftMessages(initialMessages);
    setDraftSelectedKbs([]);
    setDraftSelectedModelId(currentModelId);
    setDraftUseWebSearch(false);
    setDraftContextCleared(false);
    setDraftSessionTitle('当前对话');
    setMessages(initialMessages);
    setSelectedKbs([]);
    setSelectedModelId(currentModelId);
    setUseWebSearch(false);
    setContextCleared(false);
    setCurrentSessionTitle('当前对话');
    setInput('');
    setIsLoading(false);
    setActiveSessionId(CURRENT_SESSION_ID);
  };

  const newConversation = () => {
    const hasUserMessage = draftMessages.some(message => message.role === 'user');
    if (hasUserMessage) {
      const lastMessage = [...draftMessages].reverse().find(message => message.role === 'assistant' || message.role === 'user');
      const sessionTitle = draftSessionTitle !== '当前对话'
        ? draftSessionTitle
        : getConversationTitle(draftMessages);
      const snapshot: ChatSession = {
        id: `${Date.now()}`,
        messages: [...draftMessages],
        selectedKbs: [...draftSelectedKbs],
        modelId: draftSelectedModelId,
        useWebSearch: draftUseWebSearch,
        contextCleared: draftContextCleared,
        title: sessionTitle,
        time: lastMessage?.time || `${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`,
      };
      setChatHistory(prev => [
        snapshot,
        ...prev.filter(item => item.id !== snapshot.id),
      ].slice(0, 12));
    }
    resetCurrentConversation();
  };

  const deleteSession = (sessionId: string) => {
    setChatHistory(prev => prev.filter(session => session.id !== sessionId));
    if (activeSessionId === sessionId) {
      openCurrentConversation();
    }
  };

  const clearContext = () => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    setContextCleared(true);
    setMessages(prev => [
      ...prev,
      {
        role: 'assistant',
        content: CONTEXT_RESET_MESSAGE,
        time,
      },
    ]);
    if (activeSessionId === CURRENT_SESSION_ID) {
      setDraftContextCleared(true);
      setDraftMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: CONTEXT_RESET_MESSAGE,
          time,
        },
      ]);
      setCurrentSessionTitle('当前对话');
      setDraftSessionTitle('当前对话');
    }
  };

  const restoreSession = (session: ChatSession) => {
    setMessages(session.messages);
    setSelectedKbs(session.selectedKbs);
    setSelectedModelId(session.modelId || currentModelId);
    setUseWebSearch(session.useWebSearch ?? false);
    setContextCleared(session.contextCleared ?? false);
    setCurrentSessionTitle(session.title === '当前对话' ? getConversationTitle(session.messages) : session.title);
    setActiveSessionId(session.id);
  };

  const handleSend = (questionOverride?: string) => {
    const question = (questionOverride ?? input).trim();
    if (!question || isLoading || isConversationLockedNow()) return;
    const sessionIdAtSend = activeSessionId;
    const updateActiveConversation = (
      updater: Parameters<typeof setMessages>[0],
      draftUpdater?: Parameters<typeof setDraftMessages>[0]
    ) => {
      setMessages(updater);
      if (sessionIdAtSend === CURRENT_SESSION_ID) {
        setDraftMessages(draftUpdater || updater);
      }
    };
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const historyMessages = buildChatMemory(messagesRef.current, {
      resetMarkers: [CONTEXT_RESET_MESSAGE],
    });
    updateActiveConversation(prev => [...prev, { role: 'user', content: question, time }]);
    const titleSeed = currentSessionTitle !== '当前对话'
      ? currentSessionTitle
      : getConversationTitle([
        ...messagesRef.current,
        { role: 'user', content: question, time },
      ]);
    setCurrentSessionTitle(titleSeed);
    if (sessionIdAtSend === CURRENT_SESSION_ID) {
      setDraftSessionTitle(titleSeed);
    }
    if (!questionOverride) setInput('');
    const releaseLock = acquireConversationLock();
    releaseSendLockRef.current = releaseLock;
    setIsLoading(true);

    // 添加助手占位消息
    updateActiveConversation(prev => [...prev, { role: 'assistant', content: '', time }]);

    chatApi.ask(
      {
        question,
        messages: historyMessages,
        knowledge_base_ids: selectedKbs,
        model_id: selectedModelId,
        use_web_search: useWebSearch,
      },
      (chunk) => {
        updateActiveConversation(prev => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
          }
          return prev;
        });
      },
      (err) => {
        updateActiveConversation(prev => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: `请求失败: ${err.message}` }];
          }
          return prev;
        });
        if (sessionIdAtSend !== CURRENT_SESSION_ID) {
          setChatHistory(prev => prev.map(session => session.id === sessionIdAtSend ? {
            ...session,
            messages: [...messagesRef.current],
            selectedKbs: [...selectedKbs],
            modelId: selectedModelId,
            useWebSearch,
            contextCleared,
            title: currentSessionTitle,
            time,
          } : session));
        }
        releaseSendLockRef.current?.();
        releaseSendLockRef.current = null;
        setIsLoading(false);
      },
      () => {
        if (sessionIdAtSend !== CURRENT_SESSION_ID) {
          setChatHistory(prev => prev.map(session => session.id === sessionIdAtSend ? {
            ...session,
            messages: [...messagesRef.current],
            selectedKbs: [...selectedKbs],
            modelId: selectedModelId,
            useWebSearch,
            contextCleared,
            title: currentSessionTitle,
            time,
          } : session));
        }
        releaseSendLockRef.current?.();
        releaseSendLockRef.current = null;
        setIsLoading(false);
      }
    );
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
  const currentSessionTime = (() => {
    const lastMessage = [...draftMessages].reverse().find(message => message.role === 'assistant' || message.role === 'user');
    return lastMessage?.time || `${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`;
  })();
  const currentSessionSummary = draftSelectedKbs.length > 0 ? '知识库问答' : '纯模型问答';
  const sessionList = [
    {
      id: CURRENT_SESSION_ID,
      title: draftSessionTitle,
      time: currentSessionTime,
      summary: currentSessionSummary,
      isCurrent: true,
    },
    ...chatHistory,
  ];

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
                    onClick={() => {
                      setSelectedModelId(m.id);
                      if (activeSessionId === CURRENT_SESSION_ID) {
                        setDraftSelectedModelId(m.id);
                      }
                      setModelOpen(false);
                    }}
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

      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 flex">
        <aside className="w-64 flex-shrink-0 border-r border-slate-200 bg-white/70 px-3 py-4 overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-slate-800">会话</div>
            <button
              onClick={newConversation}
              title="新建对话"
              className="w-8 h-8 inline-flex items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-1">
            {sessionList.map(session => (
              <div
                key={session.id}
                className={`group w-full text-left rounded-lg px-3 py-2 transition-colors ${
                  activeSessionId === session.id
                    ? 'bg-indigo-50 border border-indigo-100'
                    : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (session.id === CURRENT_SESSION_ID) {
                        openCurrentConversation();
                        return;
                      }
                      restoreSession(session);
                    }}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className={`text-sm truncate ${activeSessionId === session.id ? 'text-indigo-700' : 'text-slate-700'}`}>
                      {session.title}
                    </div>
                    <div className={`mt-1 text-xs flex items-center justify-between gap-2 ${
                      activeSessionId === session.id ? 'text-indigo-400' : 'text-slate-400'
                    }`}>
                      <span className="truncate">
                        {'isCurrent' in session && session.isCurrent
                          ? session.summary
                          : session.selectedKbs.map(id => knowledgeBases.find(k => k.id === id)?.name || id).join('、') || '纯模型问答'}
                      </span>
                      <span className="flex-shrink-0">{session.time}</span>
                    </div>
                  </button>
                  {session.id !== CURRENT_SESSION_ID ? (
                    <button
                      type="button"
                      onClick={() => deleteSession(session.id)}
                      title="删除会话"
                      className="opacity-0 group-hover:opacity-100 inline-flex items-center justify-center w-7 h-7 rounded-md text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors flex-shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  ) : (
                    <div className="w-7 h-7 flex-shrink-0" />
                  )}
                </div>
              </div>
            ))}
            {chatHistory.length === 0 && activeSessionId === CURRENT_SESSION_ID && (
              <div className="px-3 py-6 text-center text-xs text-slate-400">暂无历史会话</div>
            )}
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{
                    background: msg.role === 'assistant' ? '#EEF2FF' : '#4F46E5',
                  }}
                >
                  {msg.role === 'assistant' ? (
                    <LogoMark
                      className="w-full h-full rounded-full overflow-hidden flex items-center justify-center"
                      imageClassName="w-full h-full object-contain scale-110"
                    />
                  ) : (
                    <User className="w-4 h-4 text-white" />
                  )}
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
                    {msg.role === 'assistant' ? renderAssistantBubble(msg.content) : msg.content}
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
                        disabled={isLoading || isConversationLocked}
                        className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
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
                    onClick={() => uploadInputRef.current?.click()}
                    className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                    title="上传文档"
                    aria-label="上传文档"
                  >
                    <Upload className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      setUseWebSearch(prev => {
                        const next = !prev;
                        if (activeSessionId === CURRENT_SESSION_ID) {
                          setDraftUseWebSearch(next);
                        }
                        return next;
                      });
                    }}
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
                    disabled={!input.trim() || isLoading || isConversationLocked}
                    title={isLoading || isConversationLocked ? '前一个回答仍在生成中' : ''}
                    className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
                  >
                    <Send className="w-3.5 h-3.5" />
                    发送
                  </button>
                </div>
              </div>
            </div>
            <input
              ref={uploadInputRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                void handleUploadDocument(e.target.files?.[0] ?? null);
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
