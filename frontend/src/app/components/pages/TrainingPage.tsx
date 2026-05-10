import { useState, useRef } from 'react';
import { ChevronRight, Upload, BookOpen, ArrowLeft, Check, Loader, FileText, X, File, FolderOpen } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { trainingApi } from '../../../lib/api';
import type { TrainingOutline } from '../../../lib/types';

type Step = 1 | 2 | 3;
type SourceType = 'knowledge' | 'uploaded' | 'new';

const sourceOptions: { value: SourceType; label: string; desc: string; icon: React.ElementType }[] = [
  { value: 'knowledge', label: '从知识库生成', desc: '选择已创建的知识库，提取知识内容', icon: BookOpen },
  { value: 'uploaded', label: '从已上传文档生成', desc: '选择已上传的原始文档文件', icon: FolderOpen },
  { value: 'new', label: '从新文档生成', desc: '上传新文档并立即生成培训材料', icon: Upload },
];

const contentFocusItems = ['理论知识', '操作流程', '案例分析', '法规条款', '应急处置'];

export default function TrainingPage() {
  const { knowledgeBases, providers } = useApp();
  const [step, setStep] = useState<Step>(1);
  const [sourceType, setSourceType] = useState<SourceType>('knowledge');
  const [selectedKbs, setSelectedKbs] = useState<string[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [outline, setOutline] = useState<TrainingOutline | null>(null);

  // Step 2 受控表单 state
  const [topic, setTopic] = useState('港口安全生产应急处置培训');
  const [audience, setAudience] = useState('一线作业人员');
  const [slideCount, setSlideCount] = useState(20);
  const [duration, setDuration] = useState(60);
  const [focusAreas, setFocusAreas] = useState<string[]>(['理论知识', '操作流程', '案例分析', '应急处置']);
  const [template, setTemplate] = useState('公司标准模板');
  const [modelId, setModelId] = useState<string>('');

  // 模型名称 ↔ ID 映射
  const allModels = providers.flatMap(p => p.models);

  const toggleKb = (kbId: string) => {
    setSelectedKbs(prev =>
      prev.includes(kbId) ? prev.filter(id => id !== kbId) : [...prev, kbId]
    );
  };

  const toggleDoc = (docId: string) => {
    setSelectedDocs(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    );
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    setNewFiles(prev => [...prev, ...files]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setNewFiles(prev => [...prev, ...files]);
    }
  };

  const removeFile = (index: number) => {
    setNewFiles(prev => prev.filter((_, i) => i !== index));
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
          <div className="space-y-5">
            {/* 3 cards in a row */}
            <div className="grid grid-cols-3 gap-4">
              {sourceOptions.map(opt => {
                const Icon = opt.icon;
                const isSelected = sourceType === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSourceType(opt.value)}
                    className={`flex flex-col items-start gap-3 p-5 rounded-xl border-2 text-left transition-all ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                          isSelected ? 'bg-indigo-100' : 'bg-slate-100'
                        }`}
                      >
                        <Icon className={`w-4 h-4 ${isSelected ? 'text-indigo-600' : 'text-slate-500'}`} />
                      </div>
                      <div
                        className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all ${
                          isSelected ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                        }`}
                      >
                        {isSelected && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                      </div>
                    </div>
                    <div>
                      <div
                        className={`text-sm mb-1 ${isSelected ? 'text-indigo-900' : 'text-slate-800'}`}
                        style={{ fontWeight: 500 }}
                      >
                        {opt.label}
                      </div>
                      <div className={`text-xs leading-relaxed ${isSelected ? 'text-indigo-500' : 'text-slate-500'}`}>
                        {opt.desc}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Knowledge base picker */}
            {sourceType === 'knowledge' && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="text-sm text-slate-700 mb-3" style={{ fontWeight: 500 }}>选择知识库（可多选）</div>
                <div className="grid grid-cols-3 gap-3">
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
                          className="w-4 h-4 rounded accent-indigo-600 flex-shrink-0"
                        />
                        <div className="min-w-0">
                          <div className={`text-sm truncate ${isSelected ? 'text-indigo-900' : 'text-slate-700'}`}>
                            {kb.name}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5">{kb.document_count} 文档 · {kb.wiki_page_count} 页</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Uploaded doc picker - simplified, no standalone uploaded doc list */}
            {sourceType === 'uploaded' && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="text-sm text-slate-500 text-center py-6">
                  请先选择知识库，系统会自动使用该知识库中的文档
                </div>
              </div>
            )}

            {/* New file upload */}
            {sourceType === 'new' && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="text-sm text-slate-700 mb-3" style={{ fontWeight: 500 }}>上传文档</div>

                {/* Drop zone */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                  onDragLeave={() => setIsDragOver(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-10 cursor-pointer transition-all ${
                    isDragOver
                      ? 'border-indigo-400 bg-indigo-50'
                      : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50'
                  }`}
                >
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${isDragOver ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                    <Upload className={`w-5 h-5 ${isDragOver ? 'text-indigo-500' : 'text-slate-400'}`} />
                  </div>
                  <div className="text-sm text-slate-700" style={{ fontWeight: 500 }}>拖拽文件到此处，或点击选择</div>
                  <div className="text-xs text-slate-400 mt-1">支持 PDF、Word（.doc/.docx）、TXT、Markdown，单文件最大 50 MB；扫描版 PDF 不支持</div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                </div>

                {/* File list */}
                {newFiles.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="text-xs text-slate-500 mb-2">已选 {newFiles.length} 个文件</div>
                    {newFiles.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 px-4 py-2.5 bg-slate-50 border border-slate-100 rounded-lg"
                      >
                        <div className="w-7 h-7 rounded bg-indigo-50 flex items-center justify-center flex-shrink-0">
                          <File className="w-3.5 h-3.5 text-indigo-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-slate-700 truncate">{file.name}</div>
                          <div className="text-xs text-slate-400 mt-0.5">
                            {(file.size / 1024 / 1024).toFixed(1)} MB
                          </div>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                          className="w-6 h-6 flex items-center justify-center rounded hover:bg-slate-200 transition-colors flex-shrink-0"
                        >
                          <X className="w-3.5 h-3.5 text-slate-400" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
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
          <div className="space-y-5">
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="text-sm text-slate-700 mb-5" style={{ fontWeight: 500 }}>配置培训参数</div>

              <div className="space-y-5">
                <div>
                  <label className="block text-sm text-slate-600 mb-1.5">培训主题</label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">目标受众</label>
                    <select
                      value={audience}
                      onChange={(e) => setAudience(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
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
                      value={slideCount}
                      onChange={(e) => setSlideCount(Number(e.target.value) || 0)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">预计时长（分钟）</label>
                    <input
                      type="number"
                      value={duration}
                      onChange={(e) => setDuration(Number(e.target.value) || 0)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-slate-600 mb-2">内容侧重</label>
                  <div className="flex flex-wrap gap-4">
                    {contentFocusItems.map(item => (
                      <label key={item} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={focusAreas.includes(item)}
                          onChange={(e) => {
                            setFocusAreas(prev =>
                              e.target.checked ? [...prev, item] : prev.filter(x => x !== item)
                            );
                          }}
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
                    <select
                      value={template}
                      onChange={(e) => setTemplate(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
                      <option>公司标准模板</option>
                      <option>简约商务模板</option>
                      <option>安全教育模板</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-600 mb-1.5">生成模型</label>
                    <select
                      value={modelId}
                      onChange={(e) => setModelId(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    >
                      <option value="">使用默认模型</option>
                      {allModels.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
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
                onClick={async () => {
                  setIsGenerating(true);
                  setProgress(30);
                  try {
                    const sourceIds = sourceType === 'knowledge' ? selectedKbs : selectedDocs;
                    const res = await trainingApi.generateOutline(
                      sourceType,
                      sourceIds,
                      {
                        topic,
                        audience,
                        duration,
                        slide_count: slideCount,
                        focus_areas: focusAreas,
                        template,
                        model_id: modelId || undefined,
                      }
                    );
                    setOutline(res);
                    setProgress(60);
                    setStep(3);
                  } catch (err) {
                    alert('生成大纲失败: ' + (err instanceof Error ? err.message : '未知错误'));
                  } finally {
                    setIsGenerating(false);
                  }
                }}
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
          <div className="space-y-5">
            {isGenerating ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8">
                <div className="text-center mb-8">
                  <div className="text-slate-800 mb-1" style={{ fontWeight: 500 }}>正在生成 PPT...</div>
                  <div className="text-sm text-slate-500">预计剩余约 1 分钟</div>
                </div>

                <div className="max-w-lg mx-auto space-y-6">
                  {/* Step 1: Done */}
                  <div className="flex items-start gap-4">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Check className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div>
                      <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>提取知识点</div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        正在汇总所选内容中的关键知识点
                      </div>
                    </div>
                  </div>

                  {/* Step 2: In progress */}
                  <div className="flex items-start gap-4">
                    <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Loader className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>生成 PPT 内容</div>
                      <div className="text-xs text-slate-500 mt-0.5 mb-2">正在调用 {allModels.find(m => m.id === modelId)?.name || '默认模型'}...</div>
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
                <div className="flex flex-col items-center py-6 text-center">
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                    style={{ background: '#EEF2FF' }}
                  >
                    <Check className="w-8 h-8 text-indigo-600" />
                  </div>
                  <div className="text-slate-900 mb-1" style={{ fontWeight: 500 }}>
                    {outline ? '大纲预览已生成' : '等待生成大纲'}
                  </div>
                  <div className="text-sm text-slate-500 mb-4">
                    {outline
                      ? `${outline.title} · ${outline.total_slides} 页 · 预计 ${outline.estimated_duration} 分钟`
                      : '生成大纲后，这里会显示章节结构和页数。'}
                  </div>
                  {outline && (
                    <div className="w-full max-w-xl text-left space-y-3">
                      <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
                        <div className="text-xs text-slate-400 mb-1">章节数量</div>
                        <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>
                          {outline.chapters.length} 个章节
                        </div>
                      </div>
                      <div className="space-y-2">
                        {outline.chapters.slice(0, 5).map((chapter, idx) => (
                          <div key={`${chapter.title}-${idx}`} className="rounded-lg border border-slate-100 px-4 py-3">
                            <div className="text-sm text-slate-800" style={{ fontWeight: 500 }}>{chapter.title}</div>
                            <div className="text-xs text-slate-500 mt-0.5">
                              {chapter.pages} 页 · {chapter.points.length} 个要点
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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
