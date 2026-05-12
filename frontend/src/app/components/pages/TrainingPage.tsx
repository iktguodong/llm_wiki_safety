import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Check, FileText, Loader2, Minus, Plus, RefreshCw, Trash2, Upload, WandSparkles, BookOpen, ClipboardList, Download, AlertTriangle } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { docApi, kbApi, trainingApi, wikiApi } from '../../../lib/api';
import type {
  DocumentInfo,
  KnowledgeBase,
  PresentationSpec,
  QualityReport,
  TemporaryTrainingUploadResponse,
  TrainingGenerateResponse,
  TrainingOutline,
  TrainingOutlineResponse,
  TrainingOutlineSection,
  TrainingSourceInput,
  TrainingStyle,
  WikiPage,
} from '../../../lib/types';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { ScrollArea } from '../ui/scroll-area';
import { Separator } from '../ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

type Step = 1 | 2 | 3 | 4;

type KbResources = {
  loading: boolean;
  error: string | null;
  pages: WikiPage[];
  docs: DocumentInfo[];
};

type EditableOutline = TrainingOutline & { sections: TrainingOutlineSection[] };

const styleOptions: { value: TrainingStyle; label: string; desc: string }[] = [
  { value: 'standard_training', label: '标准安全培训', desc: '适合常规安全生产培训，结构均衡' },
  { value: 'management_briefing', label: '管理层汇报', desc: '强调结论、风险矩阵和责任闭环' },
  { value: 'frontline_shift_training', label: '班组宣贯', desc: '字更大、少字、动作导向' },
];

function truncate(text: string, max = 48) {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function isSameSource(a: TrainingSourceInput, b: TrainingSourceInput) {
  return a.type === b.type && a.kb_id === b.kb_id && a.page_name === b.page_name && a.document_id === b.document_id && a.upload_id === b.upload_id && a.prompt === b.prompt;
}

function makeKey(source: TrainingSourceInput) {
  return [
    source.type,
    source.kb_id || '',
    source.page_name || '',
    source.document_id || '',
    source.upload_id || '',
    source.prompt || '',
  ].join(':');
}

function sourceLabel(source: TrainingSourceInput, knowledgeBases: KnowledgeBase[]) {
  if (source.type === 'knowledge_base') {
    return knowledgeBases.find((kb) => kb.id === source.kb_id)?.name || source.kb_id || '知识库';
  }
  if (source.type === 'wiki_page') return `${source.title || source.page_name || 'Wiki 页面'}`;
  if (source.type === 'kb_document') return `${source.title || source.document_id || '原始文档'}`;
  if (source.type === 'temporary_upload') return `${source.title || source.upload_id || '临时上传'}`;
  return source.prompt || source.title || '提示词';
}

function mergeSources(list: TrainingSourceInput[], next: TrainingSourceInput) {
  const idx = list.findIndex((item) => isSameSource(item, next));
  if (idx >= 0) {
    return list.filter((_, i) => i !== idx);
  }
  return [...list, next];
}

function removeSource(list: TrainingSourceInput[], source: TrainingSourceInput) {
  return list.filter((item) => !isSameSource(item, source));
}

function SectionEditor({
  section,
  index,
  total,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  section: TrainingOutlineSection;
  index: number;
  total: number;
  onChange: (next: TrainingOutlineSection) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  return (
    <Card className="border-slate-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base text-slate-900 flex items-center gap-2">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-xs text-indigo-700">{index + 1}</span>
              <span>章节 {index + 1}</span>
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">编辑章节标题、目标和关键点，生成 PPT 前可以继续微调。</p>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={onMoveUp} disabled={index === 0}>
              <ArrowUp className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={onMoveDown} disabled={index === total - 1}>
              <ArrowDown className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={onRemove}>
              <Trash2 className="h-4 w-4 text-rose-500" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label>章节标题</Label>
            <Input value={section.title} onChange={(e) => onChange({ ...section, title: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label>预计分钟</Label>
            <Input
              type="number"
              min={1}
              value={section.estimated_minutes}
              onChange={(e) => onChange({ ...section, estimated_minutes: Number(e.target.value) || 1 })}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label>章节目标</Label>
          <Textarea rows={2} value={section.goal} onChange={(e) => onChange({ ...section, goal: e.target.value })} />
        </div>
        <div className="space-y-1">
          <Label>关键点（每行一个）</Label>
          <Textarea
            rows={4}
            value={section.key_points.join('\n')}
            onChange={(e) =>
              onChange({
                ...section,
                key_points: e.target.value
                  .split('\n')
                  .map((item) => item.trim())
                  .filter(Boolean)
                  .slice(0, 8),
              })
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}

function SlideSpecPreview({ presentation }: { presentation: PresentationSpec }) {
  return (
    <div className="space-y-3">
      {presentation.slides.map((slide) => (
        <Card key={slide.id} className="border-slate-200">
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="capitalize">{slide.slide_type}</Badge>
                  <span className="text-xs text-slate-500">第 {slide.slide_no} 页</span>
                </div>
                <div className="mt-1 text-sm font-medium text-slate-900">{slide.title}</div>
              </div>
              {slide.safety_level && (
                <Badge variant={slide.safety_level === 'critical' ? 'destructive' : 'outline'}>
                  {slide.safety_level}
                </Badge>
              )}
            </div>
            {slide.subtitle && <p className="text-xs text-slate-500">{slide.subtitle}</p>}
            {slide.bullets.length > 0 && (
              <ul className="space-y-1">
                {slide.bullets.slice(0, 5).map((bullet) => (
                  <li key={bullet} className="text-sm text-slate-700 flex gap-2">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-indigo-500" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            )}
            {slide.notes && <p className="text-xs text-slate-500">备注：{truncate(slide.notes, 120)}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function QualityPanel({ report }: { report: QualityReport }) {
  return (
    <Card className="border-slate-200">
      <CardHeader>
        <CardTitle className="text-base text-slate-900 flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-indigo-600" />
          质量检查
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className={`rounded-lg border p-3 text-sm ${report.passed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
          {report.summary}
        </div>
        <div className="space-y-2">
          {report.issues.map((issue, idx) => (
            <div key={`${issue.code}-${idx}`} className={`rounded-lg border p-3 text-sm ${issue.level === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : issue.level === 'warning' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>
              <div className="font-medium">{issue.message}</div>
              {issue.suggestion && <div className="mt-1 text-xs opacity-80">建议：{issue.suggestion}</div>}
            </div>
          ))}
          {report.issues.length === 0 && <p className="text-sm text-slate-500">未发现明显问题。</p>}
        </div>
      </CardContent>
    </Card>
  );
}

function ExportBar({
  filename,
  downloadUrl,
  loading,
  onGenerate,
}: {
  filename?: string;
  downloadUrl?: string;
  loading: boolean;
  onGenerate: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={onGenerate} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700">
        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <WandSparkles className="mr-2 h-4 w-4" />}
        生成 PPT
      </Button>
      {downloadUrl && (
        <Button asChild variant="outline">
          <a href={downloadUrl} target="_blank" rel="noreferrer">
            <Download className="mr-2 h-4 w-4" />
            下载 {filename || 'PPTX'}
          </a>
        </Button>
      )}
    </div>
  );
}

export default function TrainingPage() {
  const { knowledgeBases, currentKbId } = useApp();
  const [step, setStep] = useState<Step>(1);
  const [selectedSources, setSelectedSources] = useState<TrainingSourceInput[]>([]);
  const [kbResources, setKbResources] = useState<Record<string, KbResources>>({});
  const [expandedKbIds, setExpandedKbIds] = useState<string[]>(currentKbId ? [currentKbId] : []);
  const [promptText, setPromptText] = useState('帮我生成一份危险化学品仓库火灾应急处置培训 PPT');
  const [tempUploadResults, setTempUploadResults] = useState<TemporaryTrainingUploadResponse[]>([]);
  const [outline, setOutline] = useState<EditableOutline | null>(null);
  const [contentPackSummary, setContentPackSummary] = useState<Record<string, unknown> | null>(null);
  const [presentation, setPresentation] = useState<PresentationSpec | null>(null);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string>('');
  const [filename, setFilename] = useState<string>('');
  const [jobId, setJobId] = useState<string>('');
  const [topic, setTopic] = useState('危险化学品仓库火灾应急处置培训');
  const [audience, setAudience] = useState('一线员工');
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [slideCount, setSlideCount] = useState(15);
  const [style, setStyle] = useState<TrainingStyle>('standard_training');
  const [focusAreasText, setFocusAreasText] = useState('应急处置\n报警流程\n初期火灾扑救');
  const [includeQuiz, setIncludeQuiz] = useState(true);
  const [includeSpeakerNotes, setIncludeSpeakerNotes] = useState(true);
  const [templateId, setTemplateId] = useState<TrainingStyle>('standard_training');
  const [loadingOutline, setLoadingOutline] = useState(false);
  const [loadingGenerate, setLoadingGenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const focusAreas = useMemo(
    () => focusAreasText.split('\n').map((item) => item.trim()).filter(Boolean).slice(0, 8),
    [focusAreasText],
  );

  const selectedKbIds = useMemo(
    () => Array.from(new Set(selectedSources.filter((source) => source.type === 'knowledge_base').map((source) => source.kb_id).filter(Boolean) as string[])),
    [selectedSources],
  );

  useEffect(() => {
    const loadKb = async (kbId: string) => {
      setKbResources((prev) => ({
        ...prev,
        [kbId]: prev[kbId] || { loading: true, error: null, pages: [], docs: [] },
      }));
      try {
        const [pagesRes, docsRes] = await Promise.all([wikiApi.list(kbId), docApi.list(kbId)]);
        setKbResources((prev) => ({
          ...prev,
          [kbId]: {
            loading: false,
            error: null,
            pages: pagesRes.items,
            docs: docsRes.items,
          },
        }));
      } catch (err) {
        setKbResources((prev) => ({
          ...prev,
          [kbId]: {
            loading: false,
            error: err instanceof Error ? err.message : '加载失败',
            pages: prev[kbId]?.pages || [],
            docs: prev[kbId]?.docs || [],
          },
        }));
      }
    };

    selectedKbIds.forEach((kbId) => {
      if (!kbResources[kbId] || kbResources[kbId].loading === false && kbResources[kbId].error) {
        void loadKb(kbId);
      }
    });
  }, [selectedKbIds, kbResources]);

  useEffect(() => {
    if (currentKbId && selectedSources.length === 0) {
      setSelectedSources([{ type: 'knowledge_base', kb_id: currentKbId }]);
    }
  }, [currentKbId, selectedSources.length]);

  const toggleKb = (kbId: string) => {
    setSelectedSources((prev) => mergeSources(prev, { type: 'knowledge_base', kb_id: kbId }));
  };

  const toggleWikiPage = (kbId: string, page: WikiPage) => {
    setSelectedSources((prev) => mergeSources(prev, { type: 'wiki_page', kb_id: kbId, page_name: page.name, title: page.title }));
  };

  const toggleDocument = (kbId: string, doc: DocumentInfo) => {
    setSelectedSources((prev) => mergeSources(prev, { type: 'kb_document', kb_id: kbId, document_id: doc.id, title: doc.file }));
  };

  const toggleTempUpload = (item: TemporaryTrainingUploadResponse) => {
    setSelectedSources((prev) => mergeSources(prev, { type: 'temporary_upload', upload_id: item.upload_id, title: item.filename }));
  };

  const addPromptSource = () => {
    const trimmed = promptText.trim();
    if (!trimmed) return;
    setSelectedSources((prev) => {
      const withoutPrompt = prev.filter((item) => item.type !== 'prompt');
      return [...withoutPrompt, { type: 'prompt', prompt: trimmed, title: '自由提示词' }];
    });
  };

  const removeSelectedSource = (source: TrainingSourceInput) => {
    setSelectedSources((prev) => removeSource(prev, source));
  };

  const handleUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    for (const file of fileArray) {
      try {
        const res = await trainingApi.uploadTemporary(file);
        setTempUploadResults((prev) => [...prev, res]);
        toggleTempUpload(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : '临时上传失败');
      }
    }
  };

  const generateOutline = async () => {
    setLoadingOutline(true);
    setError(null);
    try {
      const res = await trainingApi.generateOutline({
        sources: selectedSources,
        topic,
        audience,
        duration_minutes: durationMinutes,
        slide_count: slideCount,
        style,
        focus_areas: focusAreas,
        include_quiz: includeQuiz,
        include_speaker_notes: includeSpeakerNotes,
        job_id: jobId || undefined,
      });
      setJobId(res.job_id);
      setOutline(res.outline as EditableOutline);
      setContentPackSummary(res.content_pack_summary);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成大纲失败');
    } finally {
      setLoadingOutline(false);
    }
  };

  const updateSection = (index: number, next: TrainingOutlineSection) => {
    setOutline((prev) => {
      if (!prev) return prev;
      const sections = [...prev.sections];
      sections[index] = next;
      return { ...prev, sections };
    });
  };

  const moveSection = (index: number, direction: -1 | 1) => {
    setOutline((prev) => {
      if (!prev) return prev;
      const target = index + direction;
      if (target < 0 || target >= prev.sections.length) return prev;
      const sections = [...prev.sections];
      [sections[index], sections[target]] = [sections[target], sections[index]];
      return { ...prev, sections };
    });
  };

  const removeSection = (index: number) => {
    setOutline((prev) => {
      if (!prev) return prev;
      return { ...prev, sections: prev.sections.filter((_, i) => i !== index) };
    });
  };

  const addSection = () => {
    setOutline((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: [
          ...prev.sections,
          {
            id: `sec-manual-${Date.now()}`,
            title: '新增章节',
            goal: '补充这一章节的目标',
            key_points: ['关键点1', '关键点2'],
            estimated_minutes: 3,
            source_refs: [],
          },
        ],
      };
    });
  };

  const generatePpt = async () => {
    if (!outline) {
      setError('请先生成并确认大纲');
      return;
    }
    setLoadingGenerate(true);
    setError(null);
    try {
      const res: TrainingGenerateResponse = await trainingApi.generatePpt({
        job_id: jobId || undefined,
        sources: selectedSources,
        outline,
        template_id: templateId,
        include_quiz: includeQuiz,
        include_speaker_notes: includeSpeakerNotes,
        topic,
        audience,
        duration_minutes: durationMinutes,
        slide_count: slideCount,
        style,
        focus_areas: focusAreas,
      });
      setJobId(res.job_id);
      setPresentation(res.presentation);
      setQualityReport(res.quality_report);
      setDownloadUrl(trainingApi.download(res.filename));
      setFilename(res.filename);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成 PPT 失败');
    } finally {
      setLoadingGenerate(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-8 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-slate-900">培训材料生成</h1>
            <p className="mt-1 text-sm text-slate-500">轻量级安全生产 PPT 工作流：来源、提示词、大纲、生成、质检、下载。</p>
          </div>
          <Button variant="outline" onClick={() => setStep(1)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            返回来源
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-8 py-6">
        <div className="mb-6 flex items-center gap-3">
          {[
            '选择来源',
            '培训参数',
            '生成并编辑大纲',
            '生成 PPT',
          ].map((label, index) => {
            const n = index + 1;
            const active = step === n;
            const done = step > n;
            return (
              <div key={label} className="flex items-center gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-full border text-sm ${done || active ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-500'}`}>
                  {done ? <Check className="h-4 w-4" /> : n}
                </div>
                <span className={`text-sm ${active ? 'text-indigo-700' : done ? 'text-slate-700' : 'text-slate-400'}`}>{label}</span>
                {n < 4 && <div className={`h-px w-16 ${step > n ? 'bg-indigo-400' : 'bg-slate-200'}`} />}
              </div>
            );
          })}
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            {(step === 1 || step === 2) && (
              <Card className="border-slate-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                    <BookOpen className="h-4 w-4 text-indigo-600" />
                    Step 1 - 选择来源
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-3 md:grid-cols-2">
                    {knowledgeBases.map((kb) => {
                      const active = selectedSources.some((source) => source.type === 'knowledge_base' && source.kb_id === kb.id);
                      return (
                        <button
                          key={kb.id}
                          onClick={() => toggleKb(kb.id)}
                          className={`rounded-xl border p-4 text-left transition ${active ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 bg-white hover:border-slate-300'}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-medium text-slate-900">{kb.name}</div>
                              <div className="mt-1 text-xs text-slate-500">{kb.document_count} 文档 · {kb.wiki_page_count} 页</div>
                            </div>
                            <Checkbox checked={active} />
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <Separator />

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-slate-800">知识库原文与 Wiki 页面</div>
                      <div className="text-xs text-slate-500">展开后可选择具体页面或文档</div>
                    </div>
                    {selectedKbIds.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                        先选择一个知识库，或直接使用提示词 / 临时上传文档。
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {selectedKbIds.map((kbId) => {
                          const kb = knowledgeBases.find((item) => item.id === kbId);
                          const res = kbResources[kbId];
                          return (
                            <details key={kbId} open className="rounded-xl border border-slate-200 bg-white p-4">
                              <summary className="cursor-pointer list-none text-sm font-medium text-slate-900">{kb?.name || kbId}</summary>
                              <div className="mt-4 space-y-4">
                                <div className="flex items-center gap-2">
                                  <Badge variant="secondary">当前知识库内容可组合使用</Badge>
                                  {res?.loading && <span className="text-xs text-slate-500">加载中...</span>}
                                </div>
                                {res?.error && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{res.error}</div>}
                                <div className="grid gap-4 md:grid-cols-2">
                                  <div className="rounded-lg border border-slate-200 p-3">
                                    <div className="mb-2 text-sm font-medium text-slate-800">Wiki 页面</div>
                                    <ScrollArea className="h-56 pr-2">
                                      <div className="space-y-2">
                                        {(res?.pages || []).map((page) => {
                                          const active = selectedSources.some((source) => source.type === 'wiki_page' && source.kb_id === kbId && source.page_name === page.name);
                                          return (
                                            <label key={page.name} className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${active ? 'border-indigo-200 bg-indigo-50' : 'border-slate-100 bg-slate-50'}`}>
                                              <Checkbox checked={active} onCheckedChange={() => toggleWikiPage(kbId, page)} />
                                              <div className="min-w-0">
                                                <div className="truncate text-sm text-slate-800">{page.title}</div>
                                                <div className="text-xs text-slate-500">{page.name}</div>
                                              </div>
                                            </label>
                                          );
                                        })}
                                        {(res?.pages || []).length === 0 && <p className="text-sm text-slate-500">暂无页面</p>}
                                      </div>
                                    </ScrollArea>
                                  </div>
                                  <div className="rounded-lg border border-slate-200 p-3">
                                    <div className="mb-2 text-sm font-medium text-slate-800">原始文档</div>
                                    <ScrollArea className="h-56 pr-2">
                                      <div className="space-y-2">
                                        {(res?.docs || []).map((doc) => {
                                          const active = selectedSources.some((source) => source.type === 'kb_document' && source.kb_id === kbId && source.document_id === doc.id);
                                          return (
                                            <label key={doc.id} className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${active ? 'border-indigo-200 bg-indigo-50' : 'border-slate-100 bg-slate-50'}`}>
                                              <Checkbox checked={active} onCheckedChange={() => toggleDocument(kbId, doc)} />
                                              <div className="min-w-0">
                                                <div className="truncate text-sm text-slate-800">{doc.file}</div>
                                                <div className="text-xs text-slate-500">{doc.parse_status} · {doc.page_count} 页</div>
                                              </div>
                                            </label>
                                          );
                                        })}
                                        {(res?.docs || []).length === 0 && <p className="text-sm text-slate-500">暂无文档</p>}
                                      </div>
                                    </ScrollArea>
                                  </div>
                                </div>
                              </div>
                            </details>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <Separator />

                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card className="border-slate-200">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm text-slate-900">自由提示词</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <Textarea rows={4} value={promptText} onChange={(e) => setPromptText(e.target.value)} />
                        <Button variant="outline" onClick={addPromptSource}>
                          <Plus className="mr-2 h-4 w-4" />
                          作为来源添加
                        </Button>
                      </CardContent>
                    </Card>

                    <Card className="border-slate-200">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm text-slate-900">临时上传文档</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center">
                          <Upload className="mx-auto mb-2 h-5 w-5 text-slate-400" />
                          <div className="text-sm text-slate-700">拖拽或选择 PDF / Word / TXT / Markdown</div>
                          <div className="mt-1 text-xs text-slate-500">扫描版 PDF 不做 OCR，无法提取时会直接提示错误。</div>
                          <input
                            ref={uploadInputRef}
                            type="file"
                            multiple
                            accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                            className="hidden"
                            onChange={(e) => e.target.files && void handleUpload(e.target.files)}
                          />
                          <Button variant="outline" className="mt-4" onClick={() => uploadInputRef.current?.click()}>
                            选择文件
                          </Button>
                        </div>
                        {tempUploadResults.length > 0 && (
                          <div className="space-y-2">
                            {tempUploadResults.map((item) => {
                              const active = selectedSources.some((source) => source.type === 'temporary_upload' && source.upload_id === item.upload_id);
                              return (
                                <button key={item.upload_id} onClick={() => toggleTempUpload(item)} className={`w-full rounded-lg border p-3 text-left ${active ? 'border-indigo-200 bg-indigo-50' : 'border-slate-200 bg-white'}`}>
                                  <div className="flex items-center justify-between gap-3">
                                    <div className="min-w-0">
                                      <div className="truncate text-sm text-slate-900">{item.filename}</div>
                                      <div className="text-xs text-slate-500">{(item.size / 1024 / 1024).toFixed(1)} MB · {item.detected_type}</div>
                                    </div>
                                    <Checkbox checked={active} />
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 2 && (
              <Card className="border-slate-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                    <ClipboardList className="h-4 w-4 text-indigo-600" />
                    Step 2 - 培训参数
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-1">
                      <Label>主题</Label>
                      <Input value={topic} onChange={(e) => setTopic(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label>受众</Label>
                      <Input value={audience} onChange={(e) => setAudience(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label>时长（分钟）</Label>
                      <Input type="number" min={5} value={durationMinutes} onChange={(e) => setDurationMinutes(Number(e.target.value) || 30)} />
                    </div>
                    <div className="space-y-1">
                      <Label>页数</Label>
                      <Input type="number" min={6} value={slideCount} onChange={(e) => setSlideCount(Number(e.target.value) || 12)} />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label>风格</Label>
                    <Select value={style} onValueChange={(value) => setStyle(value as TrainingStyle)}>
                      <SelectTrigger>
                        <SelectValue placeholder="选择风格" />
                      </SelectTrigger>
                      <SelectContent>
                        {styleOptions.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            <div>
                              <div>{item.label}</div>
                              <div className="text-xs text-slate-500">{item.desc}</div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>重点领域（每行一个）</Label>
                    <Textarea rows={4} value={focusAreasText} onChange={(e) => setFocusAreasText(e.target.value)} />
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <Checkbox checked={includeQuiz} onCheckedChange={(checked) => setIncludeQuiz(Boolean(checked))} />
                      <div>
                        <div className="text-sm font-medium text-slate-900">生成测验</div>
                        <div className="text-xs text-slate-500">生成 3 - 5 道检验题。</div>
                      </div>
                    </label>
                    <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <Checkbox checked={includeSpeakerNotes} onCheckedChange={(checked) => setIncludeSpeakerNotes(Boolean(checked))} />
                      <div>
                        <div className="text-sm font-medium text-slate-900">生成讲稿备注</div>
                        <div className="text-xs text-slate-500">备注会写入 speaker_notes.md。</div>
                      </div>
                    </label>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 3 && outline && (
              <Card className="border-slate-200">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                      <WandSparkles className="h-4 w-4 text-indigo-600" />
                      Step 3 - 生成并编辑大纲
                    </CardTitle>
                    <Button variant="outline" onClick={addSection}>
                      <Plus className="mr-2 h-4 w-4" />
                      新增章节
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {contentPackSummary && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                      内容包：{String(contentPackSummary.title || contentPackSummary.topic || topic)} · 来源 {String(contentPackSummary.source_count || 0)} 个 · 分块 {String(contentPackSummary.chunk_count || 0)} 个
                    </div>
                  )}
                  {outline.warnings.length > 0 && (
                    <div className="space-y-2">
                      {outline.warnings.map((warning) => (
                        <div key={warning} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">{warning}</div>
                      ))}
                    </div>
                  )}
                  <div className="space-y-4">
                    {outline.sections.map((section, index) => (
                      <SectionEditor
                        key={section.id}
                        section={section}
                        index={index}
                        total={outline.sections.length}
                        onChange={(next) => updateSection(index, next)}
                        onRemove={() => removeSection(index)}
                        onMoveUp={() => moveSection(index, -1)}
                        onMoveDown={() => moveSection(index, 1)}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 4 && presentation && qualityReport && (
              <Card className="border-slate-200">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                    <Download className="h-4 w-4 text-indigo-600" />
                    Step 4 - 生成 PPT
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-1">
                      <Label>模板</Label>
                      <Select value={templateId} onValueChange={(value) => setTemplateId(value as TrainingStyle)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {styleOptions.map((item) => (
                            <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <ExportBar
                    filename={filename}
                    downloadUrl={downloadUrl}
                    loading={loadingGenerate}
                    onGenerate={generatePpt}
                  />

                  <QualityPanel report={qualityReport} />

                  {presentation.quality_warnings.length > 0 && (
                    <div className="space-y-2">
                      {presentation.quality_warnings.map((warning) => (
                        <div key={warning} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">{warning}</div>
                      ))}
                    </div>
                  )}

                  <div>
                    <div className="mb-2 text-sm font-medium text-slate-900">幻灯片预览</div>
                    <SlideSpecPreview presentation={presentation} />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-6">
            <Card className="border-slate-200">
              <CardHeader>
                <CardTitle className="text-base text-slate-900">来源概览</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {selectedSources.length === 0 && <span className="text-sm text-slate-500">尚未选择来源。</span>}
                  {selectedSources.map((source) => (
                    <Badge key={makeKey(source)} variant="secondary" className="flex items-center gap-2">
                      <span className="max-w-[180px] truncate">{sourceLabel(source, knowledgeBases)}</span>
                      <button onClick={() => removeSelectedSource(source)} className="ml-1 inline-flex">
                        <Minus className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <Separator />
                <div className="grid gap-2 text-sm text-slate-600">
                  <div>知识库来源：{selectedSources.filter((source) => source.type === 'knowledge_base').length}</div>
                  <div>Wiki 页面：{selectedSources.filter((source) => source.type === 'wiki_page').length}</div>
                  <div>原始文档：{selectedSources.filter((source) => source.type === 'kb_document').length}</div>
                  <div>临时上传：{selectedSources.filter((source) => source.type === 'temporary_upload').length}</div>
                  <div>提示词：{selectedSources.filter((source) => source.type === 'prompt').length}</div>
                </div>
                <Button variant="outline" className="w-full" onClick={() => setStep(2)} disabled={selectedSources.length === 0}>
                  下一步：培训参数
                </Button>
              </CardContent>
            </Card>

            <Card className="border-slate-200">
              <CardHeader>
                <CardTitle className="text-base text-slate-900">操作提示</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-600">
                <p>1. 先选来源，支持知识库、Wiki 页面、原始文档、临时上传和自由提示词混合使用。</p>
                <p>2. 临时上传文档只用于本次生成，不会写入知识库。</p>
                <p>3. 如果只有提示词，系统会生成通用结构，并在质检里标明未绑定企业原文来源。</p>
                <p>4. 生成后可以先改大纲，再出 PPT。</p>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="text-sm text-slate-600">
            {step === 1 && '完成来源选择后进入下一步。'}
            {step === 2 && '先配置参数，再生成大纲。'}
            {step === 3 && '确认大纲后即可生成 PPT。'}
            {step === 4 && '可以下载 PPTX 或继续调整。'}
          </div>
          <div className="flex items-center gap-2">
            {step > 1 && (
              <Button variant="outline" onClick={() => setStep((prev) => (prev - 1) as Step)}>
                上一步
              </Button>
            )}
            {step === 1 && (
              <Button onClick={() => setStep(2)} disabled={selectedSources.length === 0}>
                下一步
              </Button>
            )}
            {step === 2 && (
              <Button onClick={generateOutline} disabled={loadingOutline || selectedSources.length === 0}>
                {loadingOutline ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <WandSparkles className="mr-2 h-4 w-4" />}
                生成大纲
              </Button>
            )}
            {step === 3 && (
              <Button onClick={generatePpt} disabled={loadingGenerate || !outline}>
                {loadingGenerate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                生成 PPT
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
