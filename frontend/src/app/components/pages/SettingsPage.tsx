import { useState, useEffect } from 'react';
import { Plus, Pencil, FlaskConical, FolderOpen, CheckCircle2, ChevronDown } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { configApi } from '../../../lib/api';
import type { ModelProvider } from '../../../lib/types';

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
  const { providers, currentModelId, setCurrentModelId } = useApp();
  const [storagePath] = useState('/Users/xxx/knowledge-bases');
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<string | null>(null);

  const allModelNames = providers.flatMap(p => p.models.map(m => m.name));

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
    alert('正在开发中：添加新的模型服务提供者');
    // TODO: 打开添加提供者对话框
  };

  const handleEditProvider = (providerId: string) => {
    setEditing(editing === providerId ? null : providerId);
    // TODO: 打开编辑提供者对话框
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

        {/* Model assignment */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <div className="text-sm text-slate-900" style={{ fontWeight: 500 }}>模型用途分配</div>
            <div className="text-xs text-slate-500 mt-0.5">为不同任务指定最优模型</div>
          </div>
          <div className="px-6 py-2">
            <SettingRow label="文档解析模型">
              <ModelSelect value={currentModelId} options={allModelNames} onChange={setCurrentModelId} />
            </SettingRow>
            <SettingRow label="知识问答模型">
              <ModelSelect value={currentModelId} options={allModelNames} onChange={setCurrentModelId} />
            </SettingRow>
            <SettingRow label="PPT 生成模型">
              <ModelSelect value={currentModelId} options={allModelNames} onChange={setCurrentModelId} />
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
            <div>
              <div className="text-sm text-slate-600 mb-2">知识库存储路径</div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={storagePath}
                  readOnly
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 bg-slate-50"
                />
                <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
                  <FolderOpen className="w-4 h-4" />
                  修改
                </button>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              {[
                { label: '总占用空间', value: '265 MB' },
                { label: '知识库数量', value: '3' },
                { label: '文档总数', value: '25' },
                { label: 'Wiki 页面', value: '91' },
              ].map(stat => (
                <div key={stat.label} className="bg-slate-50 rounded-lg p-3 text-center border border-slate-100">
                  <div className="text-slate-900" style={{ fontWeight: 600, fontSize: '18px' }}>{stat.value}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{stat.label}</div>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button className="px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
                清理缓存
              </button>
              <button className="px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
                备份数据
              </button>
              <button className="px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
                导入数据
              </button>
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
    </div>
  );
}