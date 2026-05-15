import { useState, useRef, useEffect } from 'react';
import {
  Send,
  X,
  ChevronDown,
  User,
  Layers,
  Plus,
  Globe,
  Eraser,
  Trash2,
  Upload,
  Pencil,
  Square,
} from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import { useApp } from '../../../lib/context';
import { chatApi, trainingApi } from '../../../lib/api';
import { buildChatMemory } from '../../lib/chat-memory';
import {
  normalizeAssistantText,
  renderAssistantBubble,
  shouldExpandMessageLayout,
} from '../../lib/chat-render';
import { MessageActionBar } from '../MessageActionBar';
import LogoMark from '../LogoMark';
import type { KnowledgeBase, TemporaryTrainingUploadResponse } from '../../../lib/types';

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  time: string;
};

const initialMessages: ChatMessage[] = [
  {
    role: 'assistant',
    content: '你好！我是你的“安牛助手”，可以帮助你查询个人知识库，或者进行知识问答。',
    time: '09:30',
  },
];

const STORAGE_KEYS = {
  current: 'chat-current-state-v1',
  history: 'chat-history-v2',
};

type ChatSession = {
  id: string;
  messages: ChatMessage[];
  selectedKbs: string[];
  modelId: string;
  temporaryUploads: TemporaryTrainingUploadResponse[];
  useWebSearch: boolean;
  contextCleared: boolean;
  title: string;
  time: string;
};

const CURRENT_SESSION_ID = 'current';
const CONTEXT_RESET_MESSAGE = '已清除当前上下文。接下来的回答将从新的上下文开始。';
type CurrentSessionSummary = {
  id: string;
  title: string;
  time: string;
  summary: string;
  isCurrent: true;
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

function preview(text: string, max = 28) {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

function getConversationTitle(messages: ChatMessage[], fallback = '当前对话') {
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

function getConversationTime(messages: ChatMessage[]) {
  const lastMessage = [...messages].reverse().find(message => message.role === 'assistant' || message.role === 'user');
  return lastMessage?.time || `${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`;
}

function hasContextResetMessage(messages: ChatMessage[]) {
  return messages.some(message => message.role === 'assistant' && message.content.includes(CONTEXT_RESET_MESSAGE));
}

function buildMessageExportName(role: ChatMessage['role'], index: number, format: 'md' | 'txt' | 'docx') {
  const prefix = role === 'assistant' ? '安牛助手回答' : '我的提问';
  return `${prefix}-${index + 1}.${format}`;
}

function buildDocxExportName(role: ChatMessage['role'], text: string) {
  const fallback = role === 'assistant' ? '安牛助手回答' : '我的提问';
  const normalized = normalizeAssistantText(text).replace(/\s+/g, ' ').trim();
  const lead = normalized.split(/[。！？!?；;\n]/)[0]?.trim() || normalized;
  const cleaned = lead.replace(/[\\/:*?"<>|\r\n\t]+/g, '_').replace(/\s+/g, ' ').trim();
  return `${(cleaned || fallback).slice(0, 40)}.docx`;
}

function dropTrailingAssistantMessage(messages: ChatMessage[]) {
  const last = messages[messages.length - 1];
  if (last?.role !== 'assistant') return messages;
  return messages.slice(0, -1);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function createCurrentSessionFallback(modelId: string) {
  return {
    messages: initialMessages,
    selectedKbs: [],
    modelId,
    useWebSearch: false,
    contextCleared: false,
    temporaryUploads: [] as TemporaryTrainingUploadResponse[],
  };
}

export default function ChatPage() {
  const { knowledgeBases, providers, defaultChatModelId } = useApp();
  const currentSessionStorage = readLocal(STORAGE_KEYS.current, createCurrentSessionFallback(defaultChatModelId));
  const [draftSelectedKbs, setDraftSelectedKbs] = useState<string[]>(() => currentSessionStorage.selectedKbs);
  const [draftSelectedModelId, setDraftSelectedModelId] = useState(() => currentSessionStorage.modelId || defaultChatModelId);
  const [draftTemporaryUploads, setDraftTemporaryUploads] = useState<TemporaryTrainingUploadResponse[]>(() => currentSessionStorage.temporaryUploads || []);
  const [selectedKbs, setSelectedKbs] = useState<string[]>(() => currentSessionStorage.selectedKbs);
  const [selectedModelId, setSelectedModelId] = useState(() => currentSessionStorage.modelId || defaultChatModelId);
  const [modelOpen, setModelOpen] = useState(false);
  const [input, setInput] = useState('');
  const [draftMessages, setDraftMessages] = useState(() => currentSessionStorage.messages || initialMessages);
  const [messages, setMessages] = useState(() => currentSessionStorage.messages || initialMessages);
  const [temporaryUploads, setTemporaryUploads] = useState<TemporaryTrainingUploadResponse[]>(() => currentSessionStorage.temporaryUploads || []);
  const [chatHistory, setChatHistory] = useState<ChatSession[]>(() => readLocal(STORAGE_KEYS.history, []));
  const [draftSessionTitle, setDraftSessionTitle] = useState(() => getConversationTitle(currentSessionStorage.messages || initialMessages));
  const [currentSessionTitle, setCurrentSessionTitle] = useState(() => getConversationTitle(currentSessionStorage.messages || initialMessages));
  const [activeSessionId, setActiveSessionId] = useState<string>(CURRENT_SESSION_ID);
  const [draftUseWebSearch, setDraftUseWebSearch] = useState(() => currentSessionStorage.useWebSearch ?? false);
  const [useWebSearch, setUseWebSearch] = useState(() => currentSessionStorage.useWebSearch ?? false);
  const [draftContextCleared, setDraftContextCleared] = useState(() => currentSessionStorage.contextCleared ?? false);
  const [contextCleared, setContextCleared] = useState(() => currentSessionStorage.contextCleared ?? false);
  const [loadingSessionIds, setLoadingSessionIds] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesScrollRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const messagesRef = useRef<ChatMessage[]>(messages);
  const activeSessionIdRef = useRef(activeSessionId);
  const loadingSessionIdsRef = useRef<Record<string, boolean>>({});
  const generationRef = useRef<{ id: string; controller: AbortController; sessionId: string } | null>(null);
  const autoScrollEnabledRef = useRef(true);
  const currentSessionLoading = !!loadingSessionIds[activeSessionId];
  const currentConversationLoading = !!loadingSessionIds[CURRENT_SESSION_ID];

  const scrollMessagesToBottom = (behavior: ScrollBehavior = 'auto') => {
    const container = messagesScrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior });
  };

  const syncAutoScrollState = () => {
    const container = messagesScrollRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    autoScrollEnabledRef.current = distanceFromBottom < 96;
  };

  useEffect(() => {
    autoScrollEnabledRef.current = true;
    scrollMessagesToBottom('auto');
  }, [activeSessionId]);

  useEffect(() => {
    if (!autoScrollEnabledRef.current) return;
    scrollMessagesToBottom('auto');
  }, [messages]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) setModelOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.current, {
      messages: draftMessages,
      selectedKbs: draftSelectedKbs,
      modelId: draftSelectedModelId,
      useWebSearch: draftUseWebSearch,
      contextCleared: draftContextCleared,
      temporaryUploads: draftTemporaryUploads,
    });
  }, [draftMessages, draftSelectedKbs, draftSelectedModelId, draftUseWebSearch, draftContextCleared, draftTemporaryUploads]);

  useEffect(() => {
    writeLocal(STORAGE_KEYS.history, chatHistory);
  }, [chatHistory]);

  useEffect(() => {
    loadingSessionIdsRef.current = loadingSessionIds;
  }, [loadingSessionIds]);

  const setSessionLoading = (sessionId: string, loading: boolean) => {
    loadingSessionIdsRef.current = {
      ...loadingSessionIdsRef.current,
      [sessionId]: loading,
    };
    setLoadingSessionIds(prev => {
      const next = { ...prev };
      if (loading) {
        next[sessionId] = true;
      } else {
        delete next[sessionId];
      }
      return next;
    });
  };

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev => {
      const next = prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId];
      if (activeSessionId === CURRENT_SESSION_ID) {
        setDraftSelectedKbs(next);
      }
      return next;
    });
  };

  const syncSessionTemporaryUploads = (sessionId: string, nextUploads: TemporaryTrainingUploadResponse[]) => {
    if (sessionId === CURRENT_SESSION_ID) {
      setTemporaryUploads(nextUploads);
      setDraftTemporaryUploads(nextUploads);
      return;
    }

    setTemporaryUploads(nextUploads);
    setChatHistory(prev => prev.map(session => session.id === sessionId ? {
      ...session,
      temporaryUploads: [...nextUploads],
    } : session));
  };

  const handleUploadDocument = async (file?: File | null) => {
    if (!file) return;
    try {
      const uploaded = await trainingApi.uploadTemporary(file);
      const nextUploads = [...temporaryUploads.filter(item => item.upload_id !== uploaded.upload_id), uploaded];
      syncSessionTemporaryUploads(activeSessionId, nextUploads);
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
    setTemporaryUploads(draftTemporaryUploads);
    setUseWebSearch(draftUseWebSearch);
    setContextCleared(draftContextCleared);
    setCurrentSessionTitle(draftSessionTitle);
    setActiveSessionId(CURRENT_SESSION_ID);
  };

  const resetCurrentConversation = () => {
    setSessionLoading(CURRENT_SESSION_ID, false);
    setDraftMessages(initialMessages);
    setDraftSelectedKbs([]);
    setDraftSelectedModelId(defaultChatModelId);
    setDraftTemporaryUploads([]);
    setDraftUseWebSearch(false);
    setDraftContextCleared(false);
    setDraftSessionTitle('当前对话');
    setMessages(initialMessages);
    setSelectedKbs([]);
    setSelectedModelId(defaultChatModelId);
    setTemporaryUploads([]);
    setUseWebSearch(false);
    setContextCleared(false);
    setCurrentSessionTitle('当前对话');
    setInput('');
    setActiveSessionId(CURRENT_SESSION_ID);
  };

  const newConversation = () => {
    if (currentConversationLoading) return;
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
        temporaryUploads: [...draftTemporaryUploads],
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

  const renameSession = (sessionId: string, currentTitle: string) => {
    const nextTitle = window.prompt('请输入新的会话标题', currentTitle)?.trim();
    if (!nextTitle) return;

    if (sessionId === CURRENT_SESSION_ID) {
      setDraftSessionTitle(nextTitle);
      if (activeSessionId === CURRENT_SESSION_ID) {
        setCurrentSessionTitle(nextTitle);
      }
      return;
    }

    setChatHistory(prev => prev.map(session => session.id === sessionId ? {
      ...session,
      title: nextTitle,
    } : session));

    if (activeSessionId === sessionId) {
      setCurrentSessionTitle(nextTitle);
    }
  };

  const clearContext = () => {
    if (currentConversationLoading) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const nextMessages = [
      ...messagesRef.current,
      {
        role: 'assistant',
        content: CONTEXT_RESET_MESSAGE,
        time,
      },
    ];
    syncConversationMessages(nextMessages, { preserveTitle: true });
    setContextCleared(true);
  };

  const restoreSession = (session: ChatSession) => {
    setMessages(session.messages);
    setSelectedKbs(session.selectedKbs);
    setSelectedModelId(session.modelId || defaultChatModelId);
    setTemporaryUploads(session.temporaryUploads || []);
    setUseWebSearch(session.useWebSearch ?? false);
    setContextCleared(session.contextCleared ?? false);
    setCurrentSessionTitle(session.title === '当前对话' ? getConversationTitle(session.messages) : session.title);
    setActiveSessionId(session.id);
  };

  const syncConversationMessages = (nextMessages: ChatMessage[], options?: { preserveTitle?: boolean }) => {
    const nextTitle = options?.preserveTitle
      ? (activeSessionId === CURRENT_SESSION_ID ? draftSessionTitle : currentSessionTitle)
      : getConversationTitle(nextMessages);
    const nextTime = getConversationTime(nextMessages);
    const nextContextCleared = hasContextResetMessage(nextMessages);

    setMessages(nextMessages);
    setCurrentSessionTitle(nextTitle);
    setContextCleared(nextContextCleared);

    if (activeSessionId === CURRENT_SESSION_ID) {
      setDraftMessages(nextMessages);
      setDraftSessionTitle(nextTitle);
      setDraftContextCleared(nextContextCleared);
      return;
    }

    setChatHistory(prev => prev.map(session => session.id === activeSessionId ? {
      ...session,
      messages: [...nextMessages],
      title: nextTitle,
      time: nextTime,
      contextCleared: nextContextCleared,
      temporaryUploads: [...(session.temporaryUploads || [])],
    } : session));
  };

  const deleteMessage = (idx: number) => {
    const currentMessages = messagesRef.current;
    const target = currentMessages[idx];
    if (!target) return;

    if (currentSessionLoading && idx === currentMessages.length - 1 && target.role === 'assistant' && !target.content.trim()) {
      return;
    }

    const nextMessages = currentMessages.filter((_, index) => index !== idx);
    syncConversationMessages(nextMessages);
  };

  const stopCurrentGeneration = () => {
    const current = generationRef.current;
    if (!current) return;
    generationRef.current = null;
    current.controller.abort();
    const nextMessages = dropTrailingAssistantMessage(messagesRef.current);
    syncConversationMessages(nextMessages);
    setSessionLoading(current.sessionId, false);
  };

  const handleSend = (questionOverride?: string) => {
    const question = (questionOverride ?? input).trim();
    if (!question || currentSessionLoading) return;
    const sessionIdAtSend = activeSessionId;
    const isCurrentSession = sessionIdAtSend === CURRENT_SESSION_ID;
    const sourceMessages = isCurrentSession ? draftMessages : messages;
    const sourceSelectedKbs = isCurrentSession ? draftSelectedKbs : selectedKbs;
    const sourceModelId = isCurrentSession ? draftSelectedModelId : selectedModelId;
    const sourceTemporaryUploads = isCurrentSession ? draftTemporaryUploads : temporaryUploads;
    const sourceUseWebSearch = isCurrentSession ? draftUseWebSearch : useWebSearch;
    const sourceTitle = isCurrentSession ? draftSessionTitle : currentSessionTitle;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const historyMessages = buildChatMemory(sourceMessages, {
      resetMarkers: [CONTEXT_RESET_MESSAGE],
    });
    let workingMessages = [
      ...sourceMessages,
      { role: 'user', content: question, time },
      { role: 'assistant', content: '', time },
    ] as ChatMessage[];
    const titleSeed = sourceTitle !== '当前对话'
      ? sourceTitle
      : getConversationTitle(workingMessages);
    const commitSessionState = (nextMessages: ChatMessage[]) => {
      const nextTitle = titleSeed;
      const nextTime = getConversationTime(nextMessages);
      const nextContextCleared = hasContextResetMessage(nextMessages);

      const activeSessionIdNow = activeSessionIdRef.current;

      if (isCurrentSession) {
        setDraftMessages([...nextMessages]);
        setDraftSelectedKbs([...sourceSelectedKbs]);
        setDraftSelectedModelId(sourceModelId);
        setDraftTemporaryUploads([...sourceTemporaryUploads]);
        setDraftUseWebSearch(sourceUseWebSearch);
        setDraftContextCleared(nextContextCleared);
        setDraftSessionTitle(nextTitle);
        if (activeSessionIdNow === CURRENT_SESSION_ID) {
          setMessages([...nextMessages]);
          setSelectedKbs([...sourceSelectedKbs]);
          setSelectedModelId(sourceModelId);
          setTemporaryUploads([...sourceTemporaryUploads]);
          setUseWebSearch(sourceUseWebSearch);
          setContextCleared(nextContextCleared);
          setCurrentSessionTitle(nextTitle);
        }
        return;
      }

      setChatHistory(prev => prev.map(session => session.id === sessionIdAtSend ? {
        ...session,
        messages: [...nextMessages],
        selectedKbs: [...sourceSelectedKbs],
        modelId: sourceModelId,
        temporaryUploads: [...sourceTemporaryUploads],
        useWebSearch: sourceUseWebSearch,
        contextCleared: nextContextCleared,
        title: nextTitle,
        time: nextTime,
      } : session));

      if (activeSessionIdNow === sessionIdAtSend) {
        setMessages([...nextMessages]);
        setSelectedKbs([...sourceSelectedKbs]);
        setSelectedModelId(sourceModelId);
        setTemporaryUploads([...sourceTemporaryUploads]);
        setUseWebSearch(sourceUseWebSearch);
        setContextCleared(nextContextCleared);
        setCurrentSessionTitle(nextTitle);
      }
    };

    commitSessionState(workingMessages);
    if (!questionOverride) setInput('');
    setSessionLoading(sessionIdAtSend, true);
    let settled = false;
    const generationId = `${sessionIdAtSend}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const controller = new AbortController();
    generationRef.current = { id: generationId, controller, sessionId: sessionIdAtSend };
    const finish = () => {
      if (settled) return;
      settled = true;
      if (generationRef.current?.id === generationId) {
        generationRef.current = null;
      }
      setSessionLoading(sessionIdAtSend, false);
    };

    chatApi.ask(
      {
        question,
        messages: historyMessages,
        knowledge_base_ids: sourceSelectedKbs,
        temporary_upload_ids: sourceTemporaryUploads.map(item => item.upload_id),
        model_id: sourceModelId,
        use_web_search: sourceUseWebSearch,
      },
      // 流式输出时将每个 chunk 追加到当前会话
      (chunk) => {
        if (generationRef.current?.id !== generationId || controller.signal.aborted) return;
        const last = workingMessages[workingMessages.length - 1];
        if (last?.role === 'assistant') {
          workingMessages = [...workingMessages.slice(0, -1), { ...last, content: last.content + chunk }];
          commitSessionState(workingMessages);
        }
      },
      (err) => {
        if (generationRef.current?.id !== generationId || controller.signal.aborted) return;
        const last = workingMessages[workingMessages.length - 1];
        if (last?.role === 'assistant') {
          workingMessages = [...workingMessages.slice(0, -1), { ...last, content: `请求失败: ${err.message}` }];
          commitSessionState(workingMessages);
        }
        finish();
      },
      () => {
        if (generationRef.current?.id !== generationId || controller.signal.aborted) return;
        commitSessionState(workingMessages);
        finish();
      },
      controller.signal
    );
  };

  const copyMessage = async (role: ChatMessage['role'], text: string) => {
    await navigator.clipboard.writeText(role === 'assistant' ? normalizeAssistantText(text) : text);
  };

  const exportMessage = async (role: ChatMessage['role'], text: string, idx: number, format: 'md' | 'txt' | 'docx') => {
    try {
      const filename = buildMessageExportName(role, idx, format);
      if (format === 'docx') {
        const docxFilename = buildDocxExportName(role, text);
        const blob = await chatApi.exportMessageDocx({
          title: docxFilename.replace(/\.docx$/i, ''),
          content: text,
        });
        downloadBlob(blob, docxFilename);
        return;
      }

      const content = format === 'txt' ? normalizeAssistantText(text) : text;
      const blob = new Blob([content], {
        type: format === 'txt' ? 'text/plain;charset=utf-8' : 'text/markdown;charset=utf-8',
      });
      downloadBlob(blob, filename);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : '导出失败');
    }
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

  const allModels = providers.flatMap(p =>
    p.models.map(m => ({ ...m, providerName: p.name, label: `${p.name} / ${m.name}` })),
  );
  const currentModelName = allModels.find(m => m.id === selectedModelId)?.label || selectedModelId || '默认模型';
  const totalPages = selectedKbs.reduce((sum, id) => {
    const kb = knowledgeBases.find((k: KnowledgeBase) => k.id === id);
    return sum + (kb?.wiki_page_count ?? 0);
  }, 0);
  const currentSessionTime = (() => {
    const lastMessage = [...draftMessages].reverse().find(message => message.role === 'assistant' || message.role === 'user');
    return lastMessage?.time || `${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`;
  })();
  const activeTemporaryUploads = activeSessionId === CURRENT_SESSION_ID ? draftTemporaryUploads : temporaryUploads;
  const currentSessionSummary = draftTemporaryUploads.length > 0
    ? (draftSelectedKbs.length > 0 ? '知识库 + 临时附件' : '临时附件问答')
    : (draftSelectedKbs.length > 0 ? '知识库问答' : '纯模型问答');
  const sessionList: Array<ChatSession | CurrentSessionSummary> = [
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
                    {m.label}
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
                className={`group w-full text-left rounded-lg px-3 py-2 transition-colors border ${
                  activeSessionId === session.id
                    ? 'bg-indigo-50 border-indigo-100 shadow-sm'
                    : 'bg-white/80 border-slate-100 hover:bg-slate-50'
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
                      if ('selectedKbs' in session) {
                        restoreSession(session);
                      }
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
                        {'selectedKbs' in session
                          ? (() => {
                            const kbSummary = session.selectedKbs.map(id => knowledgeBases.find(k => k.id === id)?.name || id).join('、');
                            if (session.temporaryUploads?.length) {
                              return kbSummary ? `${kbSummary} + 临时附件` : '临时附件问答';
                            }
                            return kbSummary || '纯模型问答';
                          })()
                          : session.summary}
                      </span>
                      <span className="flex-shrink-0">{session.time}</span>
                    </div>
                  </button>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => renameSession(session.id, session.title)}
                      title="修改标题"
                      className="opacity-0 group-hover:opacity-100 inline-flex items-center justify-center w-7 h-7 rounded-md text-slate-300 hover:text-indigo-600 hover:bg-indigo-50 transition-colors flex-shrink-0"
                    >
                      <Pencil className="w-3.5 h-3.5" />
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
              </div>
            ))}
            {chatHistory.length === 0 && activeSessionId === CURRENT_SESSION_ID && (
              <div className="px-3 py-6 text-center text-xs text-slate-400">暂无历史会话</div>
            )}
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">
          <div
            ref={messagesScrollRef}
            onScroll={syncAutoScrollState}
            className="flex-1 overflow-y-auto px-6 py-6 space-y-6"
          >
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
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
                <div
                  className={`flex min-w-0 flex-col gap-1 ${
                    msg.role === 'user' ? 'items-end' : 'items-start'
                  } ${shouldExpandMessageLayout(msg.content) ? 'flex-1' : 'max-w-2xl'}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                      {msg.role === 'assistant' ? '安牛助手' : '我'}
                    </span>
                    <span className="text-xs text-slate-300">{msg.time}</span>
                  </div>
                  <div
                    className={`px-4 py-3 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed w-full ${
                      shouldExpandMessageLayout(msg.content) ? 'max-w-none' : 'max-w-full'
                    } ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-tr-sm'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                    }`}
                  >
                    {msg.role === 'assistant' ? renderAssistantBubble(msg.content) : msg.content}
                  </div>
                    <MessageActionBar
                      onCopy={() => copyMessage(msg.role, msg.content)}
                      onExport={(format) => exportMessage(msg.role, msg.content, idx, format)}
                      onDelete={() => deleteMessage(idx)}
                      onRegenerate={
                        msg.role === 'user'
                          ? () => handleSend(msg.content)
                          : (msg.role === 'assistant' && idx > 0 ? () => regenerateMessage(idx) : undefined)
                      }
                      showRegenerate={msg.role === 'user' || (msg.role === 'assistant' && idx > 0)}
                      disableRegenerate={currentSessionLoading}
                      disableDelete={currentSessionLoading && idx === messages.length - 1 && msg.role === 'assistant' && !msg.content.trim()}
                    />
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
              {activeTemporaryUploads.length > 0 && (
                <div className="px-3 pb-2 flex flex-wrap gap-2">
                  {activeTemporaryUploads.map(upload => (
                    <span
                      key={upload.upload_id}
                      className="inline-flex max-w-full items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700"
                    >
                      <span className="max-w-48 truncate" title={upload.filename}>
                        {upload.filename}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          const nextUploads = activeTemporaryUploads.filter(item => item.upload_id !== upload.upload_id);
                          syncSessionTemporaryUploads(activeSessionId, nextUploads);
                        }}
                        className="text-emerald-500 hover:text-emerald-700"
                        aria-label={`移除 ${upload.filename}`}
                        title="移除"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
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
                    disabled={currentConversationLoading}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    新建对话
                  </button>
                  <button
                    onClick={clearContext}
                    disabled={currentConversationLoading}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <Eraser className="w-3.5 h-3.5" />
                    清除上下文
                  </button>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                    <button
                      onClick={currentSessionLoading ? stopCurrentGeneration : () => handleSend()}
                      disabled={!currentSessionLoading && !input.trim()}
                      title={currentSessionLoading ? '停止生成并丢弃本次结果' : ''}
                      className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                        currentSessionLoading
                          ? 'bg-rose-600 text-white hover:bg-rose-700'
                          : 'bg-indigo-600 text-white hover:bg-indigo-700'
                      }`}
                    >
                    {currentSessionLoading ? <Square className="w-3.5 h-3.5" /> : <Send className="w-3.5 h-3.5" />}
                    {currentSessionLoading ? '停止' : '发送'}
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
