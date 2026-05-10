import { useState, useEffect } from 'react';
import { Plus, Pencil, FlaskConical, CheckCircle2, ChevronDown, X, Bot, MessageSquareText, Wand2 } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { configApi } from '../../../lib/api';
import type { ModelProvider, AppConfig } from '../../../lib/types';

// 预置的服务商 与 可用模型（用户可在 Dialog 里选择）
const PROVIDER_PRESETS: Array<{
  id: string;
  name: string;
  base_url: string;
  available_models: Array<{ id: string; name: string; type: string }>;
}> = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com',
    available_models: [
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash', type: 'chat' },
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro', type: 'chat' },
    ],
  },
];

function SettingRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-600">{label}</span>
      <div>{children}</div>
    </div>
  );
}

function ModelSelect({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none pl-3 pr-8 py-1.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-700 cursor-pointer"
      >
        {options.map((m: string) => (
          <option key={m}>{m}</option>
        ))}
      </select>
      <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
    </div>
  );
}

export default function SettingsPage() {
  const { providers, modelRoles, updateModelRole, syncAllConfig, knowledgeBases } = useApp();
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ModelProvider | null>(null);

  // 模型名称 ↔ ID 映射
  const allModels = providers.flatMap(p => p.models);
  const allModelNames = allModels.map(m => m.name);
  const nameToId = new Map(allModels.map(m => [m.name, m.id]));
  const idToName = new Map(allModels.map(m => [m.id, m.name]));
  const totalStorageMb = knowledgeBases.reduce((sum, kb) => sum + (kb.total_size_mb || 0), 0);
  const totalDocuments = knowledgeBases.reduce((sum, kb) => sum + (kb.document_count || 0), 0);
  const [localDefaultModels, setLocalDefaultModels] = useState<Record<string, string>>(() => {
    try {
      const raw = localStorage.getItem('anniu-default-models-v1');
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    localStorage.setItem('anniu-default-models-v1', JSON.stringify(localDefaultModels));
  }, [localDefaultModels]);

  const getRoleModelName = (role: string): string => {
    const modelId = modelRoles[role];
    return (modelId && idToName.get(modelId)) || allModelNames[0] || '';
  };

  const handleRoleChange = (role: string) => (name: string) => {
    const modelId = nameToId.get(name);
    if (modelId) updateModelRole(role, modelId);
  };

  const getLocalDefaultName = (key: string, fallbackRole = 'qa_chat') => {
    const modelId = localDefaultModels[key] || modelRoles[fallbackRole];
    return (modelId && idToName.get(modelId)) || allModelNames[0] || '';
  };

  const handleLocalDefaultChange = (key: string) => (name: string) => {
    const modelId = nameToId.get(name);
    if (modelId) setLocalDefaultModels(prev => ({ ...prev, [key]: modelId }));
  };

  const handleTest = async (provider: ModelProvider) => {
    setTesting(prev => ({ ...prev, [provider.id]: true }));
    try {
      await configApi.validateModel({
        provider_id: provider.id,
        api_key: provider.api_key,
        base_url: provider.base_url,
      });
      alert('连接成功');
    } catch (err) {
      alert('连接失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setTesting(prev => ({ ...prev, [provider.id]: false }));
    }
  };

  const handleAddProvider = () => {
    setEditingProvider(null);
    setDialogOpen(true);
  };

  const handleEditProvider = (providerId: string) => {
    const p = providers.find(x => x.id === providerId) || null;
    setEditingProvider(p);
    setDialogOpen(true);
  };

  const handleSaveProvider = async (p: ModelProvider) => {
    const cfg = await configApi.get();
    const exists = cfg.models.providers.some(x => x.id === p.id);
    const nextProviders = exists
      ? cfg.models.providers.map(x => (x.id === p.id ? p : x))
      : [...cfg.models.providers, p];
    await configApi.update({
      models: {
        providers: nextProviders,
        model_roles: cfg.models.model_roles,
      },
    } as Partial<AppConfig>);
    await syncAllConfig();
  };

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5">
        <h1 className="text-slate-900">设置</h1>
        <p className="text-sm text-slate-500 mt-0.5">模型服务与数据管理</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6 space-y-5">

        {/* Model providers */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
           <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
             <div>
               <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>模型服务提供者</div>
               <div className="text-xs text-slate-500 mt-0.5">管理 AI 模型接入配置</div>
             </div>
             <button 
               onClick={handleAddProvider}
               className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors cursor-pointer">
               <Plus className="w-3.5 h-3.5" />
               添加服务
             </button>
           </div>

          <div className="divide-y divide-slate-100">
            {providers.map((provider: ModelProvider) => (
              <div key={provider.id} className="px-6 py-4 hover:bg-slate-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-xs flex-shrink-0"
                      style={{ background: '#EEF2FF', color: '#4F46E5', fontWeight: 600 }}
                    >
                      {provider.name[0]}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-900" style={{ fontWeight: 500 }}>{provider.name}</span>
                        {provider.api_key && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                        )}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">{provider.base_url}</div>
                      <div className="text-xs text-slate-500 mt-0.5">模型: {provider.models.map(m => m.name).join(', ')}</div>
                    </div>
                  </div>
                   <div className="flex items-center gap-2">
                     <button
                       onClick={() => handleTest(provider)}
                       disabled={testing[provider.id]}
                       className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-50 cursor-pointer"
                     >
                       <FlaskConical className="w-3 h-3" />
                       {testing[provider.id] ? '测试中...' : '测试'}
                     </button>
                     <button 
                       onClick={() => handleEditProvider(provider.id)}
                       className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer">
                       <Pencil className="w-3 h-3" />
                       编辑
                     </button>
                   </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cherry-style default models */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>默认模型设置</div>
            <div className="text-xs text-slate-500 mt-0.5">借鉴 Cherry Studio：为对话、话题命名和提示词优化指定默认模型</div>
          </div>
          <div className="px-6 py-2">
            <SettingRow label="默认对话模型">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-slate-400" />
                <ModelSelect value={getLocalDefaultName('chat')} options={allModelNames} onChange={handleLocalDefaultChange('chat')} />
              </div>
            </SettingRow>
            <SettingRow label="话题命名模型">
              <div className="flex items-center gap-2">
                <MessageSquareText className="w-4 h-4 text-slate-400" />
                <ModelSelect value={getLocalDefaultName('topic_naming')} options={allModelNames} onChange={handleLocalDefaultChange('topic_naming')} />
              </div>
            </SettingRow>
            <SettingRow label="提示词优化模型">
              <div className="flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-slate-400" />
                <ModelSelect value={getLocalDefaultName('prompt_optimize')} options={allModelNames} onChange={handleLocalDefaultChange('prompt_optimize')} />
              </div>
            </SettingRow>
          </div>
        </div>

        {/* Model assignment */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>模型用途分配</div>
            <div className="text-xs text-slate-500 mt-0.5">为不同任务指定最优模型</div>
          </div>
          <div className="px-6 py-2">
            <SettingRow label="文档解析模型">
              <ModelSelect
                value={getRoleModelName('doc_parse')}
                options={allModelNames}
                onChange={handleRoleChange('doc_parse')}
              />
            </SettingRow>
            <SettingRow label="知识问答模型">
              <ModelSelect
                value={getRoleModelName('qa_chat')}
                options={allModelNames}
                onChange={handleRoleChange('qa_chat')}
              />
            </SettingRow>
            <SettingRow label="PPT 生成模型">
              <ModelSelect
                value={getRoleModelName('ppt_gen')}
                options={allModelNames}
                onChange={handleRoleChange('ppt_gen')}
              />
            </SettingRow>
          </div>
          <div className="mx-6 mb-4 mt-1 px-4 py-3 bg-blue-50 border border-blue-100 rounded-lg">
            <p className="text-xs text-blue-700">不同任务可使用不同模型，以优化效果与调用成本的平衡</p>
          </div>
        </div>

        {/* Data management */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>数据管理</div>
            <div className="text-xs text-slate-500 mt-0.5">知识库存储配置与统计</div>
          </div>
          <div className="px-6 py-4 space-y-4">
            <div className="text-sm text-slate-500">
              知识库存储由系统自动管理，无需手工配置路径。
            </div>

            <div className="grid grid-cols-3 gap-4">
              {[
                { label: '总占用空间', value: `${totalStorageMb.toFixed(1)} MB` },
                { label: '知识库数量', value: `${knowledgeBases.length}` },
                { label: '文档总数', value: `${totalDocuments}` },
              ].map(stat => (
                <div key={stat.label} className="bg-slate-50 rounded-lg p-3 text-center border border-slate-100">
                  <div className="text-slate-900" style={{ fontWeight: 600, fontSize: '18px' }}>{stat.value}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* About */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>关于</div>
          </div>
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>安牛 v1.0.0</div>
              <div className="text-xs text-slate-500 mt-0.5">企业安全知识库助手 · 基于 LLM Wiki 构建</div>
            </div>
            <button className="px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
              检查更新
            </button>
          </div>
        </div>

      </div>

      {/* 添加/编辑服务商 Dialog */}
      {dialogOpen && (
        <ProviderDialog
          initial={editingProvider}
          onClose={() => setDialogOpen(false)}
          onSave={handleSaveProvider}
        />
      )}
    </div>
  );
}

function ProviderDialog({
  initial,
  onClose,
  onSave,
}: {
  initial: ModelProvider | null;
  onClose: () => void;
  onSave: (p: ModelProvider) => Promise<void>;
}) {
  const isEdit = !!initial;
  const initialPresetId = initial?.id && PROVIDER_PRESETS.some(p => p.id === initial.id)
    ? initial.id
    : PROVIDER_PRESETS[0].id;
  const [presetId, setPresetId] = useState(initialPresetId);
  const preset = PROVIDER_PRESETS.find(p => p.id === presetId) || PROVIDER_PRESETS[0];
  const [name, setName] = useState(initial?.name || preset.name);
  const [baseUrl, setBaseUrl] = useState(initial?.base_url || preset.base_url);
  const [apiKey, setApiKey] = useState(initial?.api_key || '');
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(
    initial?.models.map(m => m.id) || preset.available_models.map(m => m.id)
  );
  const [saving, setSaving] = useState(false);

  // 切换预设时（仅新建时）重填默认值
  useEffect(() => {
    if (!isEdit) {
      setName(preset.name);
      setBaseUrl(preset.base_url);
      setSelectedModelIds(preset.available_models.map(m => m.id));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetId]);

  const handleSave = async () => {
    if (!selectedModelIds.length) return;
    setSaving(true);
    try {
      const models = preset.available_models.filter(m => selectedModelIds.includes(m.id));
      await onSave({
        id: initial?.id || preset.id,
        name,
        base_url: baseUrl,
        api_key: apiKey,
        models,
      });
      onClose();
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl border border-slate-200 w-[480px] max-w-[90vw]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="text-slate-900" style={{ fontWeight: 500 }}>
            {isEdit ? '编辑服务商' : '添加模型服务商'}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">服务商</label>
            <select
              value={presetId}
              onChange={(e) => setPresetId(e.target.value)}
              disabled={isEdit}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-500"
            >
              {PROVIDER_PRESETS.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">Base URL</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">可用模型（至少选择一个）</label>
            <div className="space-y-1.5">
              {preset.available_models.map(m => (
                <label
                  key={m.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedModelIds.includes(m.id)}
                    onChange={(e) => {
                      setSelectedModelIds(prev =>
                        e.target.checked ? [...prev, m.id] : prev.filter(x => x !== m.id)
                      );
                    }}
                    className="w-3.5 h-3.5 rounded accent-indigo-600"
                  />
                  <div className="flex-1">
                    <div className="text-sm text-slate-700">{m.name}</div>
                    <div className="text-xs text-slate-400">{m.id}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !selectedModelIds.length}
            className="px-4 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
