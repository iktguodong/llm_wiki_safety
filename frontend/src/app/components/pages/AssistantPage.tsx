import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  Check,
  Copy,
  Eraser,
  Globe,
  MessageSquare,
  Plus,
  Search,
  Send,
  Settings,
  Trash2,
  Wand2,
  X,
} from 'lucide-react';
import { assistants, type AssistantDefinition } from '../../data/assistants';
import { useApp } from '../../../lib/context';
import { chatApi } from '../../../lib/api';

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
  const [items, setItems] = useState<AssistantDefinition[]>(() => {
    try {
      const raw = localStorage.getItem('anniu-assistants-v1');
      return raw ? JSON.parse(raw) : assistants;
    } catch {
      return assistants;
    }
  });
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<AssistantDefinition | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(activeAssistantId || items[0]?.id || '');
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const allModels = providers.flatMap(p => p.models);
  const selectedAssistant = items.find(item => item.id === selectedId) || items[0];
  const assistantTopics = topics.filter(topic => topic.assistantId === selectedAssistant?.id);
  const currentTopic = topics.find(topic => topic.id === currentTopicId && topic.assistantId === selectedAssistant?.id) || assistantTopics[0];
  const messages = currentTopic?.messages || [];

  useEffect(() => {
    localStorage.setItem('anniu-assistants-v1', JSON.stringify(items));
  }, [items]);

  useEffect(() => {
    localStorage.setItem('anniu-assistant-topics-v1', JSON.stringify(topics));
  }, [topics]);

  useEffect(() => {
    if (activeAssistantId) setSelectedId(activeAssistantId);
  }, [activeAssistantId]);

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
    setItems(prev => {
      const exists = prev.some(item => item.id === next.id);
      return exists ? prev.map(item => item.id === next.id ? next : item) : [next, ...prev];
    });
    setSelectedId(next.id);
    onStartChat(next);
    setDialogOpen(false);
    setEditing(null);
  };

  const selectAssistant = (assistant: AssistantDefinition) => {
    setSelectedId(assistant.id);
    onStartChat(assistant);
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

  const sendMessage = () => {
    const question = input.trim();
    if (!question || isLoading || !selectedAssistant) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    if (!currentTopic) return;
    const targetTopicId = currentTopic.id;
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

  return (
    <div className="h-full flex flex-col bg-slate-50">
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-slate-900">助手</h1>
            <p className="text-sm text-slate-500 mt-1">管理专业角色、提示词和默认调用配置</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索助手"
                className="w-56 pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button
              onClick={openCreate}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              新建助手
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        <aside className="w-[360px] flex-shrink-0 border-r border-slate-200 bg-white/70 px-5 py-5 overflow-y-auto">
          <div className="space-y-3">
          {filteredItems.map(assistant => {
            const isActive = assistant.id === selectedId;
            const modelName = allModels.find(m => m.id === assistant.default_model_id)?.name || assistant.default_model_id || currentModelId || '当前模型';
            const defaultKbs = assistant.default_knowledge_base_ids
              .map(id => knowledgeBases.find(kb => kb.id === id)?.name || id)
              .filter(Boolean);

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
                className={`w-full text-left border rounded-lg p-4 transition-colors ${
                  isActive ? 'bg-indigo-50 border-indigo-100' : 'bg-white border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-lg bg-indigo-50 flex items-center justify-center text-xl flex-shrink-0">
                    {assistant.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h2 className="text-base text-slate-900 font-semibold">{assistant.name}</h2>
                      {isActive && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs">
                          <Check className="w-3 h-3" />
                          当前使用
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-slate-500 leading-relaxed">{assistant.description}</p>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-500">
                  <div className="rounded-md bg-slate-50 px-3 py-2">
                    <div className="text-slate-400">默认模型</div>
                    <div className="mt-1 text-slate-700 truncate">{modelName}</div>
                  </div>
                  <div className="rounded-md bg-slate-50 px-3 py-2">
                    <div className="text-slate-400">知识库</div>
                    <div className="mt-1 text-slate-700 truncate">{defaultKbs.join('、') || '手动选择'}</div>
                  </div>
                  <div className="rounded-md bg-slate-50 px-3 py-2">
                    <div className="text-slate-400">联网搜索</div>
                    <div className="mt-1 text-slate-700">{assistant.use_web_search ? '默认开启' : '默认关闭'}</div>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    {assistant.use_web_search ? <Globe className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                    <span>{assistant.use_web_search ? '可结合联网资料' : '专注本地和模型能力'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setEditing(assistant); setDialogOpen(true); }}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50 transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      设置
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); selectAssistant(assistant); }}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700 transition-colors"
                    >
                      <MessageSquare className="w-4 h-4" />
                      选择
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
          </div>
        </aside>

        <main className="flex-1 min-w-0 flex flex-col">
          {selectedAssistant ? (
            <>
              <div className="flex-shrink-0 bg-white border-b border-slate-200 px-6 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-xl">{selectedAssistant.icon}</div>
                      <div>
                        <h2 className="text-slate-900 font-semibold">{selectedAssistant.name}</h2>
                        <p className="text-xs text-slate-500 mt-0.5">{selectedAssistant.description}</p>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => { setEditing(selectedAssistant); setDialogOpen(true); }}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50"
                  >
                    <Settings className="w-4 h-4" />
                    设置助手
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3">
                  <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                    <div className="text-xs text-slate-400">当前模型</div>
                    <div className="text-sm text-slate-700 mt-1 truncate">
                      {allModels.find(m => m.id === selectedAssistant.default_model_id)?.name || selectedAssistant.default_model_id || currentModelId || '当前模型'}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                    <div className="text-xs text-slate-400">知识库</div>
                    <div className="text-sm text-slate-700 mt-1 truncate">
                      {selectedAssistant.default_knowledge_base_ids
                        .map(id => knowledgeBases.find(kb => kb.id === id)?.name || id)
                        .join('、') || '未绑定'}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                    <div className="text-xs text-slate-400">联网搜索</div>
                    <div className="text-sm text-slate-700 mt-1">{selectedAssistant.use_web_search ? '开启' : '关闭'}</div>
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
                  <p className="text-xs text-slate-600 leading-relaxed line-clamp-3 whitespace-pre-wrap">{promptPreview}</p>
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
                  <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-2xl rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed ${
                      msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-sm' : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                    }`}>
                      {msg.content}
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
