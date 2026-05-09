import { useState } from 'react';
import { ChevronRight, Upload, BookOpen, ArrowLeft, Check, Download, FolderOpen, Loader } from 'lucide-react';

type Step = 1 | 2 | 3;
type SourceType = 'knowledge' | 'uploaded' | 'new';

const knowledgeBases = [
  { id: 'kb1', name: '港口安全知识库', docs: 12, pages: 45 },
  { id: 'kb2', name: '安全生产制度库', docs: 8, pages: 28 },
  { id: 'kb3', name: '消防法规库', docs: 5, pages: 18 },
];

const sourceOptions: { value: SourceType; label: string; desc: string; icon: React.ElementType }[] = [
  { value: 'knowledge', label: '从知识库生成', desc: '选择已创建的知识库，提取知识内容', icon: BookOpen },
  { value: 'uploaded', label: '从已上传文档生成', desc: '选择已上传的原始文档文件', icon: FolderOpen },
  { value: 'new', label: '从新文档生成', desc: '上传新文档并立即生成培训材料', icon: Upload },
];

const contentFocusItems = ['理论知识', '操作流程', '案例分析', '法规条款', '应急处置'];

export default function TrainingPage() {
  const [step, setStep] = useState<Step>(1);
  const [sourceType, setSourceType] = useState<SourceType>('knowledge');
  const [selectedKbs, setSelectedKbs] = useState(['kb1', 'kb2']);
  const [isGenerating] = useState(true);
  const [progress] = useState(60);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const stepLabels = ['选择来源', '配置参数', '生成预览'];

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-slate-200 px-8 py-5">
        <h1 className="text-slate-900">培训材料生成</h1>
        <p className="text-sm text-slate-500 mt-0.5">基于知识库内容，一键生成 PPT 培训材料</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {/* Step indicator */}
        <div className="flex items-center mb-8">
          {stepLabels.map((label, idx) => {
            const s = idx + 1;
            const isDone = step > s;
            const isActive = step === s;
            return (
              <div key={s} className="flex items-center">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-sm transition-all ${
                      isDone
                        ? 'bg-indigo-600 text-white'
                        : isActive
                        ? 'bg-indigo-600 text-white ring-4 ring-indigo-100'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {isDone ? <Check className="w-3.5 h-3.5" /> : s}
                  </div>
                  <span
                    className={`text-sm ${
                      isActive ? 'text-indigo-600' : isDone ? 'text-slate-700' : 'text-slate-400'
                    }`}
                    style={{ fontWeight: isActive ? 500 : 400 }}
                  >
                    {label}
                  </span>
                </div>
                {idx < stepLabels.length - 1 && (
                  <div
                    className={`w-20 h-px mx-4 ${step > s ? 'bg-indigo-400' : 'bg-slate-200'}`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Step 1: Source selection */}
        {step === 1 && (
          <div className="space-y-5 max-w-3xl">
            <div className="space-y-3">
              {sourceOptions.map(opt => {
                const Icon = opt.icon;
                const isSelected = sourceType === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSourceType(opt.value)}
                    className={`w-full flex items-center gap-4 p-5 rounded-xl border-2 text-left transition-all ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isSelected ? 'bg-indigo-100' : 'bg-slate-100'
                      }`}
                    >
                      <Icon className={`w-5 h-5 ${isSelected ? 'text-indigo-600' : 'text-slate-500'}`} />
                    </div>
                    <div className="flex-1">
                      <div className={`text-sm ${isSelected ? 'text-indigo-900' : 'text-slate-800'}`} style={{ fontWeight: 500 }}>
                        {opt.label}
                      </div>
                      <div className={`text-xs mt-0.5 ${isSelected ? 'text-indigo-600' : 'text-slate-500'}`}>
                        {opt.desc}
                      </div>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                        isSelected ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                      }`}
                    >
                      {isSelected && <div className="w-2 h-2 bg-white rounded-full" />}
                    </div>
                  </button>
                );
              })}
            </div>

            {sourceType === 'knowledge' && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="text-sm text-slate-700 mb-3" style={{ fontWeight: 500 }}>选择知识库（可多选）</div>
                <div className="space-y-2">
                  {knowledgeBases.map(kb => {
                    const isSelected = selectedKbs.includes(kb.id);
                    return (
                      <label
                        key={kb.id}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? 'border-indigo-200 bg-indigo-50'
                            : 'border-slate-100 bg-slate-50 hover:border-slate-200'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleKb(kb.id)}
                          className="w-4 h-4 rounded accent-indigo-600"
                        />
                        <span className={`text-sm flex-1 ${isSelected ? 'text-indigo-900' : 'text-slate-700'}`}>
                          {kb.name}
                        </span>
                        <span className="text-xs text-slate-400">{kb.docs} 文档 · {kb.pages} 页</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setStep(2)}
                className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors"
              >
                下一步：配置参数
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Configuration */}
        {step === 2 && (
          <div className="space-y-5 max-w-3xl">
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="text-sm text-slate-700 mb-5" style={{ fontWeight: 500 }}>配置培���参数</div>

              <div className="space-y-5">
                <div>
                  <label className="block text-sm text-slate-600 mb-1.5">培训主题</label>
                  <input
                    type="text"
                    defaultValue="港口安全生产应急处置培训"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">目标受众</label>
                    <select className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                      <option>一线作业人员</option>
                      <option>安全管理人员</option>
                      <option>新员工</option>
                      <option>管理人员</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">幻灯片数量</label>
                    <input
                      type="number"
                      defaultValue={20}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-slate-600 mb-2">内容侧重</label>
                  <div className="flex flex-wrap gap-2">
                    {contentFocusItems.map(item => (
                      <label key={item} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          defaultChecked={item !== '法规条款'}
                          className="w-3.5 h-3.5 rounded accent-indigo-600"
                        />
                        <span className="text-sm text-slate-700">{item}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">PPT 模板</label>
                    <select className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                      <option>公司标准模板</option>
                      <option>简约商务模板</option>
                      <option>安全教育模板</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">生成模型</label>
                    <select className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                      <option>DeepSeek V3 Pro</option>
                      <option>DeepSeek V3 Flash</option>
                      <option>GPT-4o</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                上一步
              </button>
              <button
                onClick={() => setStep(3)}
                className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors"
              >
                生成 PPT 大纲
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Generate / Preview */}
        {step === 3 && (
          <div className="space-y-5 max-w-3xl">
            {isGenerating ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8">
                <div className="text-center mb-8">
                  <div className="text-slate-800 mb-1" style={{ fontWeight: 500 }}>正在生成 PPT...</div>
                  <div className="text-sm text-slate-500">预计剩余约 1 分钟</div>
                </div>

                <div className="space-y-5">
                  {/* Step 1: Done */}
                  <div className="flex items-start gap-4">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Check className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div>
                      <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>提取知识点</div>
                      <div className="text-xs text-slate-500 mt-0.5">已提取 73 个 Wiki 页面的核心内容</div>
                    </div>
                  </div>

                  {/* Step 2: In progress */}
                  <div className="flex items-start gap-4">
                    <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Loader className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>生成 PPT 内容</div>
                      <div className="text-xs text-slate-500 mt-0.5 mb-2">正在调用 DeepSeek V3 Pro...</div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <div className="text-xs text-slate-400 mt-1">{progress}%</div>
                    </div>
                  </div>

                  {/* Step 3: Pending */}
                  <div className="flex items-start gap-4 opacity-40">
                    <div className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs text-slate-500">3</span>
                    </div>
                    <div>
                      <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>生成 PPTX 文件</div>
                      <div className="text-xs text-slate-500 mt-0.5">等待中...</div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 p-8">
                <div className="flex flex-col items-center py-6">
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                    style={{ background: '#EEF2FF' }}
                  >
                    <Check className="w-8 h-8 text-indigo-600" />
                  </div>
                  <div className="text-slate-900 mb-1" style={{ fontWeight: 500 }}>PPT 生成完成</div>
                  <div className="text-sm text-slate-500 mb-1">港口安全生产应急处置培训.pptx</div>
                  <div className="text-xs text-slate-400 mb-6">20 页 · 15.2 MB · 2026-05-09 15:30</div>

                  <div className="flex gap-3">
                    <button className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">
                      <Download className="w-4 h-4" />
                      下载文件
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors">
                      <FolderOpen className="w-4 h-4" />
                      打开目录
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                返回列表
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
