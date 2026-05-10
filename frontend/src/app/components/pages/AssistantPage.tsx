import { Bot, Check, Globe, MessageSquare, Sparkles } from 'lucide-react';
import { assistants, type AssistantDefinition } from '../../data/assistants';
import { useApp } from '../../../lib/context';

interface AssistantPageProps {
  activeAssistantId?: string | null;
  onStartChat: (assistant: AssistantDefinition) => void;
}

export default function AssistantPage({ activeAssistantId, onStartChat }: AssistantPageProps) {
  const { knowledgeBases, currentModelId } = useApp();

  return (
    <div className="h-full flex flex-col bg-slate-50">
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-slate-900">助手</h1>
            <p className="text-sm text-slate-500 mt-1">管理专业角色和任务模板</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Sparkles className="w-4 h-4" />
            <span>{assistants.length} 个内置助手</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {assistants.map(assistant => {
            const isActive = assistant.id === activeAssistantId;
            const modelName = assistant.default_model_id || currentModelId || '当前模型';
            const defaultKbs = assistant.default_knowledge_base_ids
              .map(id => knowledgeBases.find(kb => kb.id === id)?.name || id)
              .filter(Boolean);

            return (
              <div
                key={assistant.id}
                className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow"
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
                  <button
                    onClick={() => onStartChat(assistant)}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700 transition-colors"
                  >
                    <MessageSquare className="w-4 h-4" />
                    开始对话
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
