import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Copy,
  Eraser,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Plus,
  Search,
  Send,
  Settings,
  Trash2,
  Wand2,
  Upload,
  X,
  User,
} from 'lucide-react';
import { assistants as defaultAssistants, type AssistantDefinition } from '../../data/assistants';
import { useApp } from '../../../lib/context';
import { chatApi, docApi } from '../../../lib/api';
import { buildChatMemory } from '../../lib/chat-memory';
import { renderAssistantBubble } from '../../lib/chat-render';
import LogoMark from '../LogoMark';

const ASSISTANT_CUSTOM_KEY = 'anniu-assistant-custom-v2';
const ASSISTANT_OVERRIDES_KEY = 'anniu-assistant-overrides-v2';
const ASSISTANT_HIDDEN_KEY = 'anniu-assistant-hidden-v2';
const LEGACY_ASSISTANTS_KEY = 'anniu-assistants-v1';

type AssistantOverrides = Record<string, AssistantDefinition>;

const legacyDefaultAssistants: Record<string, AssistantDefinition> = {
  'incident-review': {
    id: 'incident-review',
    name: '事故复盘',
    description: '梳理事故经过、原因、责任边界和整改措施，适合安全复盘和会议材料。',
    icon: '📊',
    system_prompt: '你是企业安全事故复盘助手。回答时请围绕事故经过、直接原因、间接原因、管理缺陷、责任边界、整改措施和跟踪验证展开，语言客观、严谨、可用于内部复盘材料。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  'official-writing': {
    id: 'official-writing',
    name: '公文写作',
    description: '生成通知、报告、请示、总结等安全管理常用公文。',
    icon: '📝',
    system_prompt: '你是企业安全管理公文写作助手。请使用正式、清晰、可落地的公文表达，结构完整，避免口语化和夸张表述。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  'emergency-plan': {
    id: 'emergency-plan',
    name: '应急预案解读',
    description: '围绕预案组织架构、响应流程、职责分工和现场处置进行解释。',
    icon: '🛡️',
    system_prompt: '你是应急预案解读助手。请优先解释组织机构、响应分级、启动条件、职责分工、处置流程和注意事项，回答要便于一线人员理解和执行。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
  'training-ppt': {
    id: 'training-ppt',
    name: '培训材料生成',
    description: '把知识库内容整理成培训主题、课程大纲、讲稿要点和 PPT 思路。',
    icon: '🎓',
    system_prompt: '你是企业安全培训材料助手。请把内容整理成适合培训的结构，包括培训目标、对象、课程章节、案例、互动问题和考核要点。',
    default_knowledge_base_ids: [],
    use_web_search: false,
  },
};

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : fallback;
  } catch {
    return fallback;
  }
}

function equalAssistant(a: AssistantDefinition, b: AssistantDefinition) {
  return a.id === b.id
    && a.name === b.name
    && a.description === b.description
    && a.icon === b.icon
    && a.system_prompt === b.system_prompt
    && a.default_model_id === b.default_model_id
    && a.use_web_search === b.use_web_search
    && JSON.stringify(a.default_knowledge_base_ids) === JSON.stringify(b.default_knowledge_base_ids);
}

function migrateLegacyAssistants(): {
  customAssistants: AssistantDefinition[];
  overrides: AssistantOverrides;
  hiddenDefaultIds: string[];
} {
  const legacyItems = readJson<AssistantDefinition[]>(LEGACY_ASSISTANTS_KEY, []);
  const defaultIds = new Set(defaultAssistants.map(item => item.id));
  const customAssistants: AssistantDefinition[] = [];
  const overrides: AssistantOverrides = {};

  for (const item of legacyItems) {
    if (defaultIds.has(item.id)) {
      const legacyDefault = legacyDefaultAssistants[item.id];
      if (!legacyDefault || !equalAssistant(item, legacyDefault)) {
        overrides[item.id] = item;
      }
      continue;
    }
    customAssistants.push(item);
  }

  return {
    customAssistants,
    overrides,
    hiddenDefaultIds: [],
  };
}

function buildMergedAssistants(
  customAssistants: AssistantDefinition[],
  overrides: AssistantOverrides,
  hiddenDefaultIds: string[],
) {
  const hidden = new Set(hiddenDefaultIds);
  const mergedDefaults = defaultAssistants
    .filter(item => !hidden.has(item.id))
    .map(item => overrides[item.id] ? { ...overrides[item.id] } : { ...item });

  return [...mergedDefaults, ...customAssistants];
}

interface AssistantPageProps {
  activeAssistantId?: string | null;
  onStartChat: (assistant: AssistantDefinition) => void;
}

type AssistantMessage = { role: 'user' | 'assistant'; content: string; time: string };
type AssistantTopic = {
  id: string;
  assistantId: string;
  title: string;
  messages: AssistantMessage[];
  contextCleared: boolean;
  updatedAt: string;
};

export default function AssistantPage({ activeAssistantId, onStartChat }: AssistantPageProps) {
  const { knowledgeBases, providers, currentModelId } = useApp();
  const initialLegacyState = useMemo(() => migrateLegacyAssistants(), []);
  const [customAssistants, setCustomAssistants] = useState<AssistantDefinition[]>(() => {
    const raw = localStorage.getItem(ASSISTANT_CUSTOM_KEY);
    return raw !== null ? JSON.parse(raw) : initialLegacyState.customAssistants;
  });
  const [overrides, setOverrides] = useState<AssistantOverrides>(() => {
    const raw = localStorage.getItem(ASSISTANT_OVERRIDES_KEY);
    return raw !== null ? JSON.parse(raw) : initialLegacyState.overrides;
  });
  const [hiddenDefaultIds, setHiddenDefaultIds] = useState<string[]>(() => {
    const raw = localStorage.getItem(ASSISTANT_HIDDEN_KEY);
    return raw !== null ? JSON.parse(raw) : initialLegacyState.hiddenDefaultIds;
  });
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<AssistantDefinition | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [input, setInput] = useState('');
  const [topics, setTopics] = useState<AssistantTopic[]>(() => {
    try {
      const raw = localStorage.getItem('anniu-assistant-topics-v1');
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [currentTopicId, setCurrentTopicId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [showAssistantList, setShowAssistantList] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const allModels = providers.flatMap(p => p.models);
  const items = useMemo(
    () => buildMergedAssistants(customAssistants, overrides, hiddenDefaultIds),
    [customAssistants, overrides, hiddenDefaultIds],
  );
  const selectedAssistant = items.find(item => item.id === selectedId) || items[0];
  const assistantTopics = topics.filter(topic => topic.assistantId === selectedAssistant?.id);
  const currentTopic = topics.find(topic => topic.id === currentTopicId && topic.assistantId === selectedAssistant?.id) || assistantTopics[0];
  const messages = currentTopic?.messages || [];

  useEffect(() => {
    localStorage.setItem(ASSISTANT_CUSTOM_KEY, JSON.stringify(customAssistants));
  }, [customAssistants]);

  useEffect(() => {
    localStorage.setItem(ASSISTANT_OVERRIDES_KEY, JSON.stringify(overrides));
  }, [overrides]);

  useEffect(() => {
    localStorage.setItem(ASSISTANT_HIDDEN_KEY, JSON.stringify(hiddenDefaultIds));
  }, [hiddenDefaultIds]);

  useEffect(() => {
    localStorage.setItem('anniu-assistant-topics-v1', JSON.stringify(topics));
  }, [topics]);

  useEffect(() => {
    if (activeAssistantId) {
      setSelectedId(activeAssistantId);
      return;
    }
    if (!selectedAssistant && items[0]) {
      setSelectedId(items[0].id);
    }
  }, [activeAssistantId, items, selectedAssistant]);

  useEffect(() => {
    if (!selectedAssistant) return;
    const existing = topics.find(topic => topic.assistantId === selectedAssistant.id);
    if (existing) {
      setCurrentTopicId(existing.id);
      return;
    }
    const topic = createTopic(selectedAssistant.id);
    setTopics(prev => [topic, ...prev]);
    setCurrentTopicId(topic.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAssistant?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (searchOpen) {
      searchInputRef.current?.focus();
    }
  }, [searchOpen]);

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(item =>
      item.name.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.system_prompt.toLowerCase().includes(q)
    );
  }, [items, query]);

  const openCreate = () => {
    setEditing({
      id: `assistant-${Date.now()}`,
      name: '自定义助手',
      description: '描述这个助手适合处理的任务。',
      icon: '✨',
      system_prompt: '你是一个专业助手。请根据用户需求提供清晰、可靠、可执行的回答。',
      default_model_id: currentModelId,
      default_knowledge_base_ids: [],
      use_web_search: false,
    });
    setDialogOpen(true);
  };

  const saveAssistant = (next: AssistantDefinition) => {
    const isDefaultAssistant = defaultAssistants.some(item => item.id === next.id);
    if (isDefaultAssistant) {
      setOverrides(prev => ({ ...prev, [next.id]: next }));
      setHiddenDefaultIds(prev => prev.filter(id => id !== next.id));
    } else {
      setCustomAssistants(prev => {
        const exists = prev.some(item => item.id === next.id);
        return exists ? prev.map(item => item.id === next.id ? next : item) : [next, ...prev];
      });
    }
    setSelectedId(next.id);
    onStartChat(next);
    setDialogOpen(false);
    setEditing(null);
  };

  const selectAssistant = (assistant: AssistantDefinition) => {
    setSelectedId(assistant.id);
    onStartChat(assistant);
  };

  const deleteAssistant = (assistantId: string) => {
    const target = items.find(item => item.id === assistantId);
    if (!target) return;
    const confirmed = window.confirm(`确定删除「${target.name}」吗？删除后无法恢复。`);
    if (!confirmed) return;

    const isDefaultAssistant = defaultAssistants.some(item => item.id === assistantId);
    if (isDefaultAssistant) {
      setHiddenDefaultIds(prev => (prev.includes(assistantId) ? prev : [...prev, assistantId]));
      setOverrides(prev => {
        const next = { ...prev };
        delete next[assistantId];
        return next;
      });
    } else {
      setCustomAssistants(prev => prev.filter(item => item.id !== assistantId));
    }

    const nextItems = items.filter(item => item.id !== assistantId);
    const fallback = nextItems[0];
    setTopics(prev => prev.filter(topic => topic.assistantId !== assistantId));

    if (selectedId === assistantId) {
      setSelectedId(fallback?.id || '');
      if (fallback) {
        onStartChat(fallback);
      }
    }

    if (editing?.id === assistantId) {
      setDialogOpen(false);
      setEditing(null);
    }
  };

  const createTopic = (assistantId: string): AssistantTopic => ({
    id: `topic-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    assistantId,
    title: '新话题',
    messages: [],
    contextCleared: false,
    updatedAt: new Date().toISOString(),
  });

  const newTopic = () => {
    if (!selectedAssistant) return;
    const topic = createTopic(selectedAssistant.id);
    setTopics(prev => [topic, ...prev]);
    setCurrentTopicId(topic.id);
  };

  const updateCurrentTopic = (updater: (topic: AssistantTopic) => AssistantTopic) => {
    if (!currentTopic) return;
    updateTopicById(currentTopic.id, updater);
  };

  const updateTopicById = (topicId: string, updater: (topic: AssistantTopic) => AssistantTopic) => {
    setTopics(prev => prev.map(topic => topic.id === topicId ? updater(topic) : topic));
  };

  const clearCurrentMessages = () => {
    updateCurrentTopic(topic => ({ ...topic, messages: [], updatedAt: new Date().toISOString() }));
  };

  const clearCurrentContext = () => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    updateCurrentTopic(topic => ({
      ...topic,
      contextCleared: true,
      messages: [...topic.messages, { role: 'assistant', content: '已清除当前话题上下文。接下来的回答将从新的上下文开始。', time }],
      updatedAt: now.toISOString(),
    }));
  };

  const deleteTopic = (topicId: string) => {
    setTopics(prev => prev.filter(topic => topic.id !== topicId));
    if (currentTopicId === topicId) {
      const next = topics.find(topic => topic.id !== topicId && topic.assistantId === selectedAssistant?.id);
      setCurrentTopicId(next?.id || '');
    }
  };

  const handleUploadDocument = async (file?: File | null) => {
    const targetKbId = selectedAssistant?.default_knowledge_base_ids[0];
    if (!targetKbId) {
      window.alert('请先在助手设置里绑定一个知识库，再上传文档。');
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

  const sendMessage = () => {
    const question = input.trim();
    if (!question || isLoading || !selectedAssistant) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    if (!currentTopic) return;
    const targetTopicId = currentTopic.id;
    const historyMessages = buildChatMemory(currentTopic.messages, {
      resetMarkers: ['已清除当前话题上下文。接下来的回答将从新的上下文开始。'],
    });
    updateTopicById(targetTopicId, topic => ({
      ...topic,
      title: topic.title === '新话题' ? question.slice(0, 30) : topic.title,
      messages: [...topic.messages, { role: 'user', content: question, time }, { role: 'assistant', content: '', time }],
      updatedAt: now.toISOString(),
    }));
    setInput('');
    setIsLoading(true);

    chatApi.ask(
      {
        question,
        messages: historyMessages,
        knowledge_base_ids: selectedAssistant.default_knowledge_base_ids,
        model_id: selectedAssistant.default_model_id || currentModelId,
        use_web_search: selectedAssistant.use_web_search,
        assistant_id: selectedAssistant.id,
        assistant_prompt: selectedAssistant.system_prompt,
      },
      (chunk) => {
        updateTopicById(targetTopicId, topic => {
          const last = topic.messages[topic.messages.length - 1];
          if (last?.role !== 'assistant') return topic;
          return {
            ...topic,
            messages: [...topic.messages.slice(0, -1), { ...last, content: last.content + chunk }],
            updatedAt: new Date().toISOString(),
          };
        });
      },
      (err) => {
        updateTopicById(targetTopicId, topic => {
          const last = topic.messages[topic.messages.length - 1];
          if (last?.role !== 'assistant') return topic;
          return {
            ...topic,
            messages: [...topic.messages.slice(0, -1), { ...last, content: `请求失败: ${err.message}` }],
            updatedAt: new Date().toISOString(),
          };
        });
        setIsLoading(false);
      },
      () => setIsLoading(false)
    );
  };

  const promptPreview = selectedAssistant?.system_prompt || '';
  const promptPreviewLines = promptPreview
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .slice(0, 2)
    .join('\n');

  return (
    <div className="h-full flex flex-col bg-slate-50">
      <div className="flex-1 min-h-0 flex">
        {showAssistantList && (
        <aside className="w-64 flex-shrink-0 border-r border-slate-200 bg-white/70 px-3 py-4 overflow-y-auto">
          <div className="space-y-3">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h1 className="text-sm font-medium text-slate-800">助手列表</h1>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setSearchOpen(prev => !prev)}
                    className={`inline-flex items-center justify-center w-10 h-10 rounded-lg border text-sm transition-colors ${
                      searchOpen
                        ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                    aria-pressed={searchOpen}
                    aria-label="搜索助手"
                    title="搜索助手"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                  <button
                    onClick={openCreate}
                    className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 text-indigo-600 bg-transparent hover:bg-indigo-50 transition-colors"
                    aria-label="新建助手"
                    title="新建助手"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAssistantList(false)}
                    className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                    aria-label="折叠助手列表"
                    title="折叠助手列表"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {searchOpen && (
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    ref={searchInputRef}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="搜索助手"
                    className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}
            </div>

            {filteredItems.map(assistant => {
              const isActive = assistant.id === selectedId;

              return (
                <div
                  key={assistant.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectAssistant(assistant)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      selectAssistant(assistant);
                    }
                  }}
                  className={`group w-full text-left border rounded-lg px-3 py-2 transition-colors ${
                      isActive ? 'bg-indigo-50 border-indigo-100' : 'bg-white border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center text-base flex-shrink-0">
                      {assistant.icon}
                    </div>
                    <div className="min-w-0 flex-1 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <h2 className="text-sm text-slate-800 font-medium truncate">{assistant.name}</h2>
                      </div>
                      <div className="flex items-center flex-shrink-0">
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setEditing(assistant); setDialogOpen(true); }}
                          className="opacity-0 group-hover:opacity-100 inline-flex items-center justify-center w-7 h-7 rounded-md text-slate-300 hover:text-indigo-600 hover:bg-indigo-50 transition-colors flex-shrink-0"
                          aria-label={`设置 ${assistant.name}`}
                          title="设置"
                        >
                          <Settings className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
        )}

        <main className="flex-1 min-w-0 flex flex-col">
          {selectedAssistant ? (
            <>
              <div className="flex-shrink-0 bg-white border-b border-slate-200 px-6 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-xl flex-shrink-0">{selectedAssistant.icon}</div>
                      <h2 className="text-slate-900 font-medium text-lg">{selectedAssistant.name}</h2>
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-xs">
                        {allModels.find(m => m.id === selectedAssistant.default_model_id)?.name || selectedAssistant.default_model_id || currentModelId || '当前模型'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {!showAssistantList && (
                      <button
                        onClick={() => setShowAssistantList(true)}
                        className="inline-flex items-center gap-2 px-3 h-9 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm"
                        aria-label="展开助手列表"
                        title="展开助手列表"
                      >
                        <ChevronRight className="w-4 h-4" />
                        <span>展开列表</span>
                      </button>
                    )}
                    <button
                      onClick={() => { setEditing(selectedAssistant); setDialogOpen(true); }}
                      className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
                      aria-label="设置助手"
                      title="设置助手"
                    >
                      <Settings className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteAssistant(selectedAssistant.id)}
                      className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-slate-200 text-slate-400 hover:bg-red-50 hover:text-red-500"
                      aria-label="删除助手"
                      title="删除助手"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-xs text-slate-400">当前提示词</div>
                    <button
                      onClick={() => navigator.clipboard?.writeText(promptPreview)}
                      className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                    >
                      <Copy className="w-3 h-3" />
                      复制
                    </button>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap line-clamp-2 min-h-[2.5rem]">{promptPreviewLines || promptPreview}</p>
                </div>
              </div>

              <div className="flex-shrink-0 bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-2 overflow-x-auto">
                <button
                  onClick={newTopic}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-dashed border-slate-300 text-sm text-slate-600 hover:border-indigo-300 hover:text-indigo-600 flex-shrink-0"
                >
                  <Plus className="w-3.5 h-3.5" />
                  新话题
                </button>
                {assistantTopics.map(topic => (
                  <div
                    key={topic.id}
                    className={`group inline-flex items-center rounded-lg border text-sm flex-shrink-0 ${
                      currentTopic?.id === topic.id ? 'bg-indigo-50 border-indigo-100 text-indigo-700' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setCurrentTopicId(topic.id)}
                      className="inline-flex items-center gap-2 min-w-0 px-3 py-1.5"
                    >
                      <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="max-w-[160px] truncate">{topic.title}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteTopic(topic.id)}
                      className="mr-2 text-slate-300 hover:text-red-500"
                      aria-label={`删除话题 ${topic.title}`}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                {messages.length > 0 ? messages.map((msg, idx) => (
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
                      <div className={`px-4 py-3 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed ${
                        msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-sm' : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                      }`}>
                        {msg.role === 'assistant' ? renderAssistantBubble(msg.content) : msg.content}
                      </div>
                    </div>
                  </div>
                )) : (
                  <div className="h-full flex items-center justify-center text-sm text-slate-400">
                    选择当前助手后，可直接在这里开始对话。
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="flex-shrink-0 px-6 pb-6">
                <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden focus-within:border-indigo-300">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                      }
                    }}
                    placeholder={`向「${selectedAssistant.name}」提问...`}
                    rows={2}
                    className="w-full px-4 pt-4 pb-2 resize-none outline-none text-sm text-slate-700 placeholder-slate-400 bg-transparent"
                  />
                  <div className="px-3 pb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                      <button
                        onClick={() => uploadInputRef.current?.click()}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
                        title="上传文档"
                        aria-label="上传文档"
                      >
                        <Upload className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={clearCurrentContext}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
                      >
                        <Eraser className="w-3.5 h-3.5" />
                        清除上下文
                      </button>
                      <button
                        onClick={clearCurrentMessages}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        清空消息
                      </button>
                    </div>
                    <button
                      onClick={sendMessage}
                      disabled={!input.trim() || isLoading}
                      className="inline-flex items-center gap-2 px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Send className="w-3.5 h-3.5" />
                      发送
                    </button>
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
            </>
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-slate-400">暂无助手</div>
          )}
        </main>
      </div>

      {dialogOpen && editing && (
        <AssistantDialog
          assistant={editing}
          knowledgeBases={knowledgeBases}
          models={allModels}
          onClose={() => { setDialogOpen(false); setEditing(null); }}
          onSave={saveAssistant}
        />
      )}
    </div>
  );
}

function AssistantDialog({
  assistant,
  knowledgeBases,
  models,
  onClose,
  onSave,
}: {
  assistant: AssistantDefinition;
  knowledgeBases: ReturnType<typeof useApp>['knowledgeBases'];
  models: Array<{ id: string; name: string; type: string }>;
  onClose: () => void;
  onSave: (assistant: AssistantDefinition) => void;
}) {
  const [draft, setDraft] = useState<AssistantDefinition>(assistant);

  const toggleKb = (id: string) => {
    setDraft(prev => ({
      ...prev,
      default_knowledge_base_ids: prev.default_knowledge_base_ids.includes(id)
        ? prev.default_knowledge_base_ids.filter(item => item !== id)
        : [...prev.default_knowledge_base_ids, id],
    }));
  };

  const optimizePrompt = () => {
    setDraft(prev => ({
      ...prev,
      system_prompt: `${prev.system_prompt.trim()}\n\n回答要求：\n1. 先给出结论，再展开依据。\n2. 需要区分事实、推断和建议。\n3. 涉及安全管理要求时，尽量给出可执行清单。\n4. 不确定的信息要明确提示，不要编造。`,
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-[760px] max-w-[94vw] max-h-[88vh] overflow-hidden rounded-xl bg-white border border-slate-200 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <div className="text-slate-900 font-semibold">助手设置</div>
            <div className="text-xs text-slate-400 mt-0.5">配置角色提示词、默认模型、知识库和联网策略</div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto max-h-[70vh] space-y-4">
          <div className="grid grid-cols-[88px_1fr] gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">图标</label>
              <input
                value={draft.icon}
                onChange={(e) => setDraft(prev => ({ ...prev, icon: e.target.value.slice(0, 2) }))}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-center text-xl outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">名称</label>
              <input
                value={draft.name}
                onChange={(e) => setDraft(prev => ({ ...prev, name: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1.5">描述</label>
            <input
              value={draft.description}
              onChange={(e) => setDraft(prev => ({ ...prev, description: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs text-slate-500">提示词</label>
              <button
                onClick={optimizePrompt}
                className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-700"
              >
                <Wand2 className="w-3.5 h-3.5" />
                优化提示词
              </button>
            </div>
            <textarea
              value={draft.system_prompt}
              onChange={(e) => setDraft(prev => ({ ...prev, system_prompt: e.target.value }))}
              rows={8}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">默认模型</label>
              <select
                value={draft.default_model_id || ''}
                onChange={(e) => setDraft(prev => ({ ...prev, default_model_id: e.target.value || undefined }))}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">使用当前模型</option>
                {models.map(model => (
                  <option key={model.id} value={model.id}>{model.name}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center justify-between px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700">
              <span>默认开启联网搜索</span>
              <input
                type="checkbox"
                checked={draft.use_web_search}
                onChange={(e) => setDraft(prev => ({ ...prev, use_web_search: e.target.checked }))}
                className="w-4 h-4 accent-indigo-600"
              />
            </label>
          </div>

          <div>
            <div className="text-xs text-slate-500 mb-2">默认知识库</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {knowledgeBases.length > 0 ? knowledgeBases.map(kb => (
                <label key={kb.id} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={draft.default_knowledge_base_ids.includes(kb.id)}
                    onChange={() => toggleKb(kb.id)}
                    className="w-3.5 h-3.5 accent-indigo-600"
                  />
                  <span className="text-sm text-slate-700 flex-1 truncate">{kb.name}</span>
                  <span className="text-xs text-slate-400">{kb.document_count} 文档</span>
                </label>
              )) : (
                <div className="text-sm text-slate-400">暂无知识库，助手会使用纯模型问答。</div>
              )}
            </div>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50">
            取消
          </button>
          <button
            onClick={() => onSave(draft)}
            disabled={!draft.name.trim() || !draft.system_prompt.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-sm text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
