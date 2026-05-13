import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Download, FileText, Globe, Loader2, Plus, Trash2, Upload, WandSparkles, X } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { docApi, trainingApi } from '../../../lib/api';
import type {
  DocumentInfo,
  KnowledgeBase,
  PresentationSpec,
  QualityReport,
  TrainingGenerateResponse,
  HtmlDeckStyle,
  HtmlDeckTheme,
  HtmlGenerateResponse,
  TrainingOutline,
  TrainingOutlineResponse,
  TrainingOutlineSlide,
  TrainingSourceInput,
  TrainingStyle,
} from '../../../lib/types';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Separator } from '../ui/separator';
import { Textarea } from '../ui/textarea';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';

type MainMode = 'html' | 'ppt';
type SourceMode = 'kb_document' | 'temporary_upload';
type SlideCountChoice = '5' | '15' | '20' | '30' | 'custom';

const TRAINING_MODE_KEY = 'anniu-training-mode-v1';

type KbResources = {
  loading: boolean;
  error: string | null;
  docs: DocumentInfo[];
};

type PptSetupDraft = {
  sourceMode: SourceMode;
  kbId: string;
  documentId: string;
  requirement: string;
  slideCountChoice: SlideCountChoice;
  customSlideCount: number;
  style: TrainingStyle;
  includeSpeakerNotes: boolean;
  renderStyle: HtmlDeckStyle;
  theme: HtmlDeckTheme;
};

const styleOptions: { value: TrainingStyle; label: string; desc: string }[] = [
  { value: 'standard_training', label: '标准安全培训', desc: '适合常规安全生产培训，结构均衡' },
  { value: 'management_briefing', label: '管理层汇报', desc: '强调结论、风险矩阵和责任闭环' },
  { value: 'frontline_shift_training', label: '班组宣贯', desc: '字更大、少字、动作导向' },
];

const htmlThemeOptions: { value: HtmlDeckTheme; label: string; desc: string }[] = [
  { value: 'ink', label: '墨水经典', desc: '深墨黑 + 暖米白，最稳妥的默认视觉' },
  { value: 'indigo', label: '靛蓝瓷', desc: '更冷静的蓝色系统，适合技术和数据' },
  { value: 'forest', label: '森林墨', desc: '偏自然的绿调，适合文化与稳重内容' },
  { value: 'kraft', label: '牛皮纸', desc: '偏怀旧的人文底色，适合叙事型内容' },
  { value: 'dune', label: '沙丘', desc: '更克制的中性色，适合设计与品牌感' },
];

function durationFromSlideCount(slideCount: number) {
  if (slideCount <= 5) return 15;
  if (slideCount <= 15) return 30;
  if (slideCount <= 20) return 45;
  return Math.min(90, Math.max(45, Math.round(slideCount * 2)));
}

function slideTypeLabel(slideType: TrainingOutlineSlide['slide_type']) {
  const labels: Record<TrainingOutlineSlide['slide_type'], string> = {
    cover: '封面',
    agenda: '目录',
    content: '正文',
    workflow: '流程',
    risk_scene: '风险场景',
    legal_requirement: '制度要求',
    control_measures: '控制措施',
    case_discussion: '案例讨论',
    checklist: '检查清单',
    quiz: '测验',
    summary: '总结',
  };
  return labels[slideType] || '正文';
}

function sourceLabel(source: TrainingSourceInput, knowledgeBases: KnowledgeBase[]) {
  if (source.type === 'kb_document') {
    return source.title || source.document_id || '知识库文档';
  }
  if (source.type === 'temporary_upload') {
    return source.title || source.upload_id || '上传文档';
  }
  if (source.type === 'prompt') {
    return source.title || '按需求生成';
  }
  if (source.type === 'knowledge_base') {
    return knowledgeBases.find((kb) => kb.id === source.kb_id)?.name || source.kb_id || '知识库';
  }
  return source.title || '来源';
}

function buildSlideCount(choice: SlideCountChoice, customSlideCount: number) {
  if (choice === 'custom') {
    return Math.max(1, customSlideCount || 1);
  }
  return Number(choice);
}

function normalizePoints(text: string) {
  return text
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function OutlineSlideCard({
  slide,
  index,
  total,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  slide: TrainingOutlineSlide;
  index: number;
  total: number;
  onChange: (next: TrainingOutlineSlide) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-base text-slate-900">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">
                {slide.slide_no}
              </span>
              <span>{slideTypeLabel(slide.slide_type)}</span>
            </CardTitle>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              {slide.layout_hint && <span>布局：{slide.layout_hint}</span>}
              {slide.source_refs.length > 0 && <span>来源：{slide.source_refs.length} 条</span>}
            </div>
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
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <Label>页面标题</Label>
            <Input value={slide.title} onChange={(e) => onChange({ ...slide, title: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label>页面类型</Label>
            <Select value={slide.slide_type} onValueChange={(value) => onChange({ ...slide, slide_type: value as TrainingOutlineSlide['slide_type'] })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  'cover',
                  'agenda',
                  'content',
                  'workflow',
                  'risk_scene',
                  'legal_requirement',
                  'control_measures',
                  'case_discussion',
                  'checklist',
                  'quiz',
                  'summary',
                ].map((item) => (
                  <SelectItem key={item} value={item}>
                    {slideTypeLabel(item as TrainingOutlineSlide['slide_type'])}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1">
          <Label>关键点</Label>
          <Textarea
            rows={4}
            value={slide.key_points.join('\n')}
            onChange={(e) => onChange({ ...slide, key_points: normalizePoints(e.target.value) })}
            placeholder="每行一个要点"
          />
        </div>
        <div className="space-y-1">
          <Label>讲稿备注</Label>
          <Textarea
            rows={3}
            value={slide.notes || ''}
            onChange={(e) => onChange({ ...slide, notes: e.target.value })}
            placeholder="用于讲解时的备注"
          />
        </div>
        <div className="space-y-1">
          <Label>版式提示</Label>
          <Input value={slide.layout_hint || ''} onChange={(e) => onChange({ ...slide, layout_hint: e.target.value })} placeholder="例如：两栏 / 时间线 / 卡片" />
        </div>
      </CardContent>
    </Card>
  );
}

function TopModeCard({
  active,
  title,
  subtitle,
  icon,
  onClick,
}: {
  active: boolean;
  title: string;
  subtitle: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-[76px] flex-1 items-center gap-3 rounded-2xl border px-4 py-3 text-left transition ${
        active ? 'border-emerald-300 bg-emerald-50 text-emerald-950' : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-sm font-semibold tracking-wide">{title}</div>
        <div className="mt-0.5 text-xs text-slate-500">{subtitle}</div>
      </div>
    </button>
  );
}

export default function TrainingPage() {
  const { knowledgeBases, currentKbId } = useApp();
  const [mode, setMode] = useState<MainMode>(() => {
    try {
      const raw = localStorage.getItem(TRAINING_MODE_KEY);
      if (raw === 'html' || raw === 'ppt') {
        return raw;
      }
    } catch {
      // ignore storage failures and fall back to PPT
    }
    return 'ppt';
  });
  const [setupDraft, setSetupDraft] = useState<PptSetupDraft>({
    sourceMode: 'kb_document',
    kbId: currentKbId || '',
    documentId: '',
    requirement: '请突出应急处置、报警流程和初期火灾扑救',
    slideCountChoice: '15',
    customSlideCount: 12,
    style: 'standard_training',
    includeSpeakerNotes: true,
    renderStyle: 'magazine',
    theme: 'ink',
  });
  const [selectedSources, setSelectedSources] = useState<TrainingSourceInput[]>([]);
  const [kbResources, setKbResources] = useState<Record<string, KbResources>>({});
  const [outline, setOutline] = useState<TrainingOutline | null>(null);
  const [presentation, setPresentation] = useState<PresentationSpec | null>(null);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string>('');
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const [filename, setFilename] = useState<string>('');
  const [htmlTitle, setHtmlTitle] = useState<string>('');
  const [notesDownloadUrl, setNotesDownloadUrl] = useState<string>('');
  const [notesFilename, setNotesFilename] = useState<string>('');
  const [jobId, setJobId] = useState<string>('');
  const [loadingOutline, setLoadingOutline] = useState(false);
  const [loadingGenerate, setLoadingGenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documentPickerOpen, setDocumentPickerOpen] = useState(false);
  const [newMenuOpen, setNewMenuOpen] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const slideCount = buildSlideCount(setupDraft.slideCountChoice, setupDraft.customSlideCount);
  const durationMinutes = useMemo(() => durationFromSlideCount(slideCount), [slideCount]);
  const selectedSourceSummary = useMemo(() => {
    if (selectedSources.length === 0) return '选择文档';
    if (selectedSources.length === 1) return sourceLabel(selectedSources[0], knowledgeBases);
    return `已选 ${selectedSources.length} 个文档`;
  }, [knowledgeBases, selectedSources]);
  const slideCountSummary = useMemo(() => {
    if (setupDraft.slideCountChoice === 'custom') {
      return `自由输入 ${setupDraft.customSlideCount || 1} 页`;
    }
    return `${slideCount} 页`;
  }, [slideCount, setupDraft.customSlideCount, setupDraft.slideCountChoice]);
  const styleSummary = useMemo(() => styleOptions.find((item) => item.value === setupDraft.style)?.label || '选择风格', [setupDraft.style]);
  const themeSummary = useMemo(
    () => htmlThemeOptions.find((item) => item.value === setupDraft.theme)?.label || '墨水经典',
    [setupDraft.theme],
  );
  const notesSummary = setupDraft.includeSpeakerNotes ? '有' : '无';

  useEffect(() => {
    if (!setupDraft.kbId && knowledgeBases[0]) {
      setSetupDraft((prev) => ({ ...prev, kbId: currentKbId || knowledgeBases[0].id }));
    }
  }, [currentKbId, knowledgeBases, setupDraft.kbId]);

  useEffect(() => {
    try {
      localStorage.setItem(TRAINING_MODE_KEY, mode);
    } catch {
      // ignore storage failures
    }
  }, [mode]);

  useEffect(() => {
    const loadKb = async (kbId: string) => {
      setKbResources((prev) => ({
        ...prev,
        [kbId]: prev[kbId] || { loading: true, error: null, docs: [] },
      }));
      try {
        const docsRes = await docApi.list(kbId);
        setKbResources((prev) => ({
          ...prev,
          [kbId]: {
            loading: false,
            error: null,
            docs: docsRes.items,
          },
        }));
      } catch (err) {
        setKbResources((prev) => ({
          ...prev,
          [kbId]: {
            loading: false,
            error: err instanceof Error ? err.message : '加载失败',
            docs: prev[kbId]?.docs || [],
          },
        }));
      }
    };

    if (setupDraft.sourceMode === 'kb_document' && setupDraft.kbId) {
      const kbInfo = kbResources[setupDraft.kbId];
      if (!kbInfo || (kbInfo.loading === false && kbInfo.error)) {
        void loadKb(setupDraft.kbId);
      }
    }
  }, [setupDraft.kbId, setupDraft.sourceMode, kbResources]);

  const resetWorkflow = (nextMode: MainMode = 'ppt') => {
    setMode(nextMode);
    setSetupDraft({
      sourceMode: 'kb_document',
      kbId: currentKbId || knowledgeBases[0]?.id || '',
      documentId: '',
      requirement: '',
      slideCountChoice: '15',
      customSlideCount: 12,
      style: 'standard_training',
      includeSpeakerNotes: true,
      renderStyle: 'magazine',
      theme: 'ink',
    });
    setSelectedSources([]);
    setOutline(null);
    setPresentation(null);
    setQualityReport(null);
    setDownloadUrl('');
    setPreviewUrl('');
    setFilename('');
    setHtmlTitle('');
    setNotesDownloadUrl('');
    setNotesFilename('');
    setJobId('');
    setLoadingOutline(false);
    setLoadingGenerate(false);
    setError(null);
    setDocumentPickerOpen(false);
    setNewMenuOpen(false);
    uploadInputRef.current && (uploadInputRef.current.value = '');
  };

  const handleUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    for (const file of fileArray) {
      try {
        const res = await trainingApi.uploadTemporary(file);
        setSelectedSources((prev) => {
          const next = [
            ...prev,
            {
              type: 'temporary_upload',
              upload_id: res.upload_id,
              title: res.filename,
              metadata: { detected_type: res.detected_type },
            },
          ];
          return dedupeSources(next);
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : '临时上传失败');
      }
    }
  };

  const dedupeSources = (items: TrainingSourceInput[]) => {
    const seen = new Set<string>();
    const result: TrainingSourceInput[] = [];
    for (const item of items) {
      const key = sourceKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(item);
    }
    return result;
  };

  const sourceKey = (source: TrainingSourceInput) => {
    if (source.type === 'kb_document') {
      return `kb_document:${source.kb_id || ''}:${source.document_id || ''}`;
    }
    if (source.type === 'temporary_upload') {
      return `temporary_upload:${source.upload_id || ''}`;
    }
    if (source.type === 'knowledge_base') {
      return `knowledge_base:${source.kb_id || ''}`;
    }
    if (source.type === 'prompt') {
      return `prompt:${source.prompt || source.title || ''}`;
    }
    return `${source.type}:${source.title || ''}:${source.document_id || ''}:${source.upload_id || ''}`;
  };

  const addKbDocumentSource = () => {
    if (!setupDraft.kbId) {
      setError('请选择知识库');
      return;
    }
    if (!setupDraft.documentId) {
      setError('请选择知识库中的文档');
      return;
    }
    const doc = kbResources[setupDraft.kbId]?.docs.find((item) => item.id === setupDraft.documentId);
    setSelectedSources((prev) =>
      dedupeSources([
        ...prev,
        {
          type: 'kb_document',
          kb_id: setupDraft.kbId,
          document_id: setupDraft.documentId,
          title: doc?.file || '知识库文档',
        },
      ]),
    );
    setSetupDraft((prev) => ({ ...prev, documentId: '' }));
  };

  const removeSource = (index: number) => {
    setSelectedSources((prev) => prev.filter((_, i) => i !== index));
  };

  const resolveSetupSource = (allowEmpty = false): boolean => {
    const requirement = setupDraft.requirement.trim();
    if (!requirement) {
      setError('请输入主题和需求');
      return false;
    }
    if (!allowEmpty && selectedSources.length === 0) {
      setError('请至少添加一个文档');
      return false;
    }
    return true;
  };

  const generateOutline = async () => {
    if (!resolveSetupSource(mode === 'html')) {
      return;
    }
    setOutline(null);
    setPresentation(null);
    setQualityReport(null);
    setDownloadUrl('');
    setPreviewUrl('');
    setFilename('');
    setNotesDownloadUrl('');
    setNotesFilename('');
    setJobId('');
    setLoadingOutline(true);
    setError(null);
    try {
      const res: TrainingOutlineResponse = await trainingApi.generateOutline({
        sources: selectedSources,
        topic: setupDraft.requirement.trim(),
        audience: '',
        duration_minutes: durationMinutes,
        slide_count: slideCount,
        style: setupDraft.style,
        focus_areas: [],
        include_quiz: true,
        include_speaker_notes: setupDraft.includeSpeakerNotes,
        job_id: jobId || undefined,
      });
      setJobId(res.job_id);
      setOutline(res.outline);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成大纲失败');
    } finally {
      setLoadingOutline(false);
    }
  };

  const updateSlide = (index: number, next: TrainingOutlineSlide) => {
    setOutline((prev) => {
      if (!prev) return prev;
      const slides = [...prev.slides];
      slides[index] = next;
      return { ...prev, slides };
    });
  };

  const moveSlide = (index: number, direction: -1 | 1) => {
    setOutline((prev) => {
      if (!prev) return prev;
      const target = index + direction;
      if (target < 0 || target >= prev.slides.length) return prev;
      const slides = [...prev.slides];
      [slides[index], slides[target]] = [slides[target], slides[index]];
      return {
        ...prev,
        slides: slides.map((slide, idx) => ({ ...slide, slide_no: idx + 1 })),
      };
    });
  };

  const addSlide = () => {
    setOutline((prev) => {
      if (!prev) return prev;
      const slides = [
        ...prev.slides,
        {
          id: `slide-manual-${Date.now()}`,
          slide_no: prev.slides.length + 1,
          title: '新增页面',
          key_points: ['关键点1', '关键点2'],
          notes: '补充这一页的讲解备注',
          layout_hint: '正文页',
          slide_type: 'content',
          source_refs: [],
          visual_type: 'two_column',
          safety_level: 'normal',
        } as TrainingOutlineSlide,
      ];
      return { ...prev, slides };
    });
  };

  const removeSlide = (index: number) => {
    setOutline((prev) => {
      if (!prev) return prev;
      const slides = prev.slides.filter((_, i) => i !== index).map((slide, idx) => ({ ...slide, slide_no: idx + 1 }));
      return { ...prev, slides };
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
        template_id: setupDraft.style,
        include_quiz: true,
        include_speaker_notes: setupDraft.includeSpeakerNotes,
        topic: outline.topic,
        audience: outline.audience,
        duration_minutes: outline.duration_minutes,
        slide_count: outline.slides.length,
        style: setupDraft.style,
        focus_areas: [],
      });
      setJobId(res.job_id);
      setPresentation(res.presentation);
      setQualityReport(res.quality_report);
      setDownloadUrl(trainingApi.download(res.filename));
      setPreviewUrl('');
      setFilename(res.filename);
      setHtmlTitle('');
      setNotesDownloadUrl(res.notes_download_url || '');
      setNotesFilename(res.notes_filename || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成 PPT 失败');
    } finally {
      setLoadingGenerate(false);
    }
  };

  const generateHtml = async () => {
    if (!resolveSetupSource(true)) {
      return;
    }
    setLoadingGenerate(true);
    setError(null);
    setDownloadUrl('');
    setPreviewUrl('');
    setFilename('');
    setHtmlTitle('');
    setPresentation(null);
    setQualityReport(null);
    setOutline(null);
    setNotesDownloadUrl('');
    setNotesFilename('');
    try {
      const res: HtmlGenerateResponse = await trainingApi.generateHtml({
        job_id: jobId || undefined,
        sources: selectedSources,
        topic: setupDraft.requirement.trim(),
        audience: '',
        duration_minutes: durationMinutes,
        slide_count: slideCount,
        style: setupDraft.style,
        focus_areas: [],
        include_quiz: true,
        include_speaker_notes: false,
        render_style: setupDraft.renderStyle,
        theme: setupDraft.theme,
        template_id: setupDraft.renderStyle,
      });
      setJobId(res.job_id);
      setHtmlTitle(res.deck.title || setupDraft.requirement.trim() || 'HTML 网页');
      setDownloadUrl(trainingApi.downloadHtml(res.job_id, res.filename));
      setPreviewUrl(trainingApi.previewHtml(res.job_id, res.filename));
      setFilename(res.filename);
      setPresentation(null);
      setQualityReport(null);
      setNotesDownloadUrl('');
      setNotesFilename('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成 HTML 失败');
    } finally {
      setLoadingGenerate(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-8 py-5">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-slate-900">培训材料生成</h1>
          <Popover open={newMenuOpen} onOpenChange={setNewMenuOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                新建
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-52 rounded-2xl border-slate-200 p-2 shadow-2xl">
              <div className="space-y-1">
                <button
                  type="button"
                  onClick={() => resetWorkflow('html')}
                  className="flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-slate-50"
                >
                  <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <Globe className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900">生成 HTML</div>
                    <div className="text-xs text-slate-500">适合做成网页形式的培训内容</div>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => resetWorkflow('ppt')}
                  className="flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-slate-50"
                >
                  <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900">生成 PPT</div>
                    <div className="text-xs text-slate-500">适合导出后继续编辑修改</div>
                  </div>
                </button>
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-8 py-6">
        <div className="mb-5 flex gap-3">
          <TopModeCard
            active={mode === 'html'}
            title="生成精美的HTML网页"
            subtitle="适用日常汇报培训"
            icon={<Globe className="h-5 w-5" />}
            onClick={() => setMode('html')}
          />
          <TopModeCard
            active={mode === 'ppt'}
            title="生成可导出的PPT"
            subtitle="适用自由编辑修改"
            icon={<FileText className="h-5 w-5" />}
            onClick={() => setMode('ppt')}
          />
        </div>

        {error && (
          <div className="mb-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {mode === 'html' ? (
          <div className="space-y-6">
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="space-y-4 p-4">
                <Textarea
                  rows={3}
                  value={setupDraft.requirement}
                  onChange={(e) => setSetupDraft((prev) => ({ ...prev, requirement: e.target.value }))}
                  placeholder="HTML 网页主题 / 需求"
                  className="min-h-[112px] bg-slate-50"
                />

                {selectedSources.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {selectedSources.map((source, index) => (
                      <div
                        key={`${source.type}-${sourceKey(source)}-${index}`}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
                      >
                        <span className="max-w-[260px] truncate">{sourceLabel(source, knowledgeBases)}</span>
                        <button
                          type="button"
                          onClick={() => removeSource(index)}
                          className="text-slate-400 transition hover:text-slate-700"
                          aria-label="移除来源"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(220px,.78fr)_minmax(220px,.78fr)_minmax(220px,.82fr)_auto] xl:items-center">
                  <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <Label className="text-sm font-medium text-slate-700">选择文档</Label>
                    <Popover open={documentPickerOpen} onOpenChange={setDocumentPickerOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-10 w-full justify-between rounded-xl border-slate-200 bg-white px-3 text-slate-900 shadow-sm"
                        >
                          <span className="truncate text-left">{selectedSourceSummary}</span>
                          <span className="ml-3 shrink-0 text-slate-400">▾</span>
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-[640px] max-w-[calc(100vw-2rem)] rounded-[24px] border-slate-200 p-4 shadow-2xl">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setSetupDraft((prev) => ({ ...prev, sourceMode: 'kb_document' }))}
                            className={`rounded-full border px-3 py-1.5 text-sm transition ${
                              setupDraft.sourceMode === 'kb_document' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-white text-slate-700'
                            }`}
                          >
                            来自知识库
                          </button>
                          <button
                            type="button"
                            onClick={() => setSetupDraft((prev) => ({ ...prev, sourceMode: 'temporary_upload' }))}
                            className={`rounded-full border px-3 py-1.5 text-sm transition ${
                              setupDraft.sourceMode === 'temporary_upload' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-white text-slate-700'
                            }`}
                          >
                            上传文档
                          </button>
                        </div>

                        {setupDraft.sourceMode === 'kb_document' ? (
                          <div className="mt-4 space-y-3">
                            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_auto]">
                              <Select
                                value={setupDraft.kbId}
                                onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, kbId: value, documentId: '' }))}
                              >
                                <SelectTrigger className="h-10 min-w-0">
                                  <SelectValue placeholder="选择知识库" />
                                </SelectTrigger>
                                <SelectContent>
                                  {knowledgeBases.map((kb) => (
                                    <SelectItem key={kb.id} value={kb.id}>
                                      {kb.name}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <Select value={setupDraft.documentId} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, documentId: value }))}>
                                <SelectTrigger className="h-10 min-w-0">
                                  <SelectValue placeholder="选择文档" />
                                </SelectTrigger>
                                <SelectContent>
                                  {(kbResources[setupDraft.kbId]?.docs || []).map((doc) => (
                                    <SelectItem key={doc.id} value={doc.id}>
                                      {doc.file}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <Button type="button" onClick={addKbDocumentSource} className="h-10 shrink-0 whitespace-nowrap bg-indigo-600 hover:bg-indigo-700">
                                加入
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-4">
                            <Button variant="outline" className="h-10" onClick={() => uploadInputRef.current?.click()}>
                              <Upload className="mr-2 h-4 w-4" />
                              上传文档
                            </Button>
                            <input
                              ref={uploadInputRef}
                              type="file"
                              multiple
                              accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                              className="hidden"
                              onChange={(e) => e.target.files && void handleUpload(e.target.files)}
                            />
                          </div>
                        )}
                      </PopoverContent>
                    </Popover>
                  </div>

                  <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <Label className="text-sm font-medium text-slate-700">选择页数</Label>
                    <Select value={setupDraft.slideCountChoice} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, slideCountChoice: value as SlideCountChoice }))}>
                      <SelectTrigger className="h-10 w-full rounded-[18px] border-slate-200 bg-white px-4 shadow-sm">
                        <SelectValue>{slideCountSummary}</SelectValue>
                      </SelectTrigger>
                      <SelectContent className="w-[240px] rounded-[28px] border-slate-200 bg-white p-3 shadow-2xl">
                        {['5', '15', '20', '30'].map((item) => (
                          <SelectItem key={item} value={item} className="my-1 rounded-2xl bg-white px-5 py-4 text-base font-medium text-slate-800">
                            {item} 页
                          </SelectItem>
                        ))}
                        <SelectItem value="custom" className="my-1 rounded-2xl bg-white px-5 py-4 text-base font-medium text-slate-800">
                          自由输入
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    {setupDraft.slideCountChoice === 'custom' && (
                      <Input
                        type="number"
                        min={1}
                        value={setupDraft.customSlideCount}
                        onChange={(e) => setSetupDraft((prev) => ({ ...prev, customSlideCount: Number(e.target.value) || 1 }))}
                        className="h-10 w-full rounded-[18px] border-slate-200 bg-white shadow-sm"
                        placeholder="请输入页数"
                      />
                    )}
                  </div>

                  <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <Label className="text-sm font-medium text-slate-700">网页主题色</Label>
                    <Select value={setupDraft.theme} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, theme: value as HtmlDeckTheme }))}>
                      <SelectTrigger className="h-10 w-full rounded-xl border-slate-200 bg-white px-3 shadow-sm">
                        <SelectValue>{themeSummary}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {htmlThemeOptions.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <Label className="text-sm font-medium text-slate-700">内容风格</Label>
                    <Select value={setupDraft.style} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, style: value as TrainingStyle }))}>
                      <SelectTrigger className="h-10 w-full rounded-xl border-slate-200 bg-white px-3 shadow-sm">
                        <SelectValue>{styleSummary}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {styleOptions.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center justify-end xl:self-center">
                    <Button
                      onClick={generateHtml}
                      disabled={loadingGenerate || !setupDraft.requirement.trim()}
                      className="h-10 rounded-xl bg-indigo-600 px-5 hover:bg-indigo-700"
                    >
                      {loadingGenerate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Globe className="mr-2 h-4 w-4" />}
                      生成html网页
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {(downloadUrl || previewUrl || qualityReport) && (
              <Card className="border-slate-200 shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                      <Globe className="h-4 w-4 text-emerald-600" />
                      HTML 结果
                    </CardTitle>
                  <div className="flex flex-wrap gap-2">
                    {previewUrl && (
                      <Button asChild variant="outline">
                        <a href={previewUrl} target="_blank" rel="noreferrer">
                          <Globe className="mr-2 h-4 w-4" />
                          预览 HTML
                        </a>
                      </Button>
                    )}
                    {downloadUrl && (
                      <Button asChild variant="outline">
                        <a href={downloadUrl} target="_blank" rel="noreferrer" download>
                          <Download className="mr-2 h-4 w-4" />
                          下载 HTML网页
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-slate-600">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="font-medium text-slate-900">标题</div>
                      <div className="mt-1 truncate">{htmlTitle || 'HTML 网页'}</div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="font-medium text-slate-900">主题色</div>
                      <div className="mt-1">{themeSummary}</div>
                    </div>
                  </div>
                  {qualityReport && (
                    <div className={`rounded-lg border p-3 text-sm ${qualityReport.passed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                      {qualityReport.summary}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="space-y-3 p-4">
                <Textarea
                  rows={3}
                  value={setupDraft.requirement}
                  onChange={(e) => setSetupDraft((prev) => ({ ...prev, requirement: e.target.value }))}
                  placeholder="PPT主题 / 需求"
                  className="min-h-[112px] bg-slate-50"
                />

                <div className="flex flex-wrap gap-2">
                  {selectedSources.map((source, index) => (
                    <div
                      key={`${source.type}-${sourceKey(source)}-${index}`}
                      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
                    >
                      <span className="max-w-[260px] truncate">{sourceLabel(source, knowledgeBases)}</span>
                      <button
                        type="button"
                        onClick={() => removeSource(index)}
                        className="text-slate-400 transition hover:text-slate-700"
                        aria-label="移除来源"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                  <div className="grid flex-1 gap-3 min-w-0 xl:max-w-[1050px] xl:grid-cols-[repeat(4,minmax(0,1fr))]">
                    <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">选择文档</Label>
                      <Popover open={documentPickerOpen} onOpenChange={setDocumentPickerOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-10 w-full justify-between rounded-xl border-slate-200 bg-white px-3 text-slate-900 shadow-sm"
                          >
                            <span className="truncate text-left">{selectedSourceSummary}</span>
                            <span className="ml-3 shrink-0 text-slate-400">▾</span>
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent align="start" className="w-[640px] max-w-[calc(100vw-2rem)] rounded-[24px] border-slate-200 p-4 shadow-2xl">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setSetupDraft((prev) => ({ ...prev, sourceMode: 'kb_document' }))}
                              className={`rounded-full border px-3 py-1.5 text-sm transition ${
                                setupDraft.sourceMode === 'kb_document' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-white text-slate-700'
                              }`}
                            >
                              来自知识库
                            </button>
                            <button
                              type="button"
                              onClick={() => setSetupDraft((prev) => ({ ...prev, sourceMode: 'temporary_upload' }))}
                              className={`rounded-full border px-3 py-1.5 text-sm transition ${
                                setupDraft.sourceMode === 'temporary_upload' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-white text-slate-700'
                              }`}
                            >
                              上传文档
                            </button>
                          </div>

                          {setupDraft.sourceMode === 'kb_document' ? (
                            <div className="mt-4 space-y-3">
                              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_auto]">
                                <Select
                                  value={setupDraft.kbId}
                                  onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, kbId: value, documentId: '' }))}
                                >
                                  <SelectTrigger className="h-10 min-w-0">
                                    <SelectValue placeholder="选择知识库" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {knowledgeBases.map((kb) => (
                                      <SelectItem key={kb.id} value={kb.id}>
                                        {kb.name}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <Select value={setupDraft.documentId} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, documentId: value }))}>
                                  <SelectTrigger className="h-10 min-w-0">
                                    <SelectValue placeholder="选择文档" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {(kbResources[setupDraft.kbId]?.docs || []).map((doc) => (
                                      <SelectItem key={doc.id} value={doc.id}>
                                        {doc.file}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <Button type="button" onClick={addKbDocumentSource} className="h-10 shrink-0 whitespace-nowrap bg-indigo-600 hover:bg-indigo-700">
                                  加入
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div className="mt-4">
                              <Button variant="outline" className="h-10" onClick={() => uploadInputRef.current?.click()}>
                                <Upload className="mr-2 h-4 w-4" />
                                上传文档
                              </Button>
                              <input
                                ref={uploadInputRef}
                                type="file"
                                multiple
                                accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                                className="hidden"
                                onChange={(e) => e.target.files && void handleUpload(e.target.files)}
                              />
                            </div>
                          )}
                        </PopoverContent>
                      </Popover>
                    </div>

                    <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">选择页数</Label>
                      <Select value={setupDraft.slideCountChoice} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, slideCountChoice: value as SlideCountChoice }))}>
                        <SelectTrigger className="h-10 w-full rounded-[18px] border-slate-200 bg-white px-4 shadow-sm">
                          <SelectValue>{slideCountSummary}</SelectValue>
                        </SelectTrigger>
                        <SelectContent className="w-[240px] rounded-[28px] border-slate-200 bg-white p-3 shadow-2xl">
                          {['5', '15', '20', '30'].map((item) => (
                            <SelectItem key={item} value={item} className="my-1 rounded-2xl bg-white px-5 py-4 text-base font-medium text-slate-800">
                              {item} 页
                            </SelectItem>
                          ))}
                          <SelectItem value="custom" className="my-1 rounded-2xl bg-white px-5 py-4 text-base font-medium text-slate-800">
                            自由输入
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      {setupDraft.slideCountChoice === 'custom' && (
                        <Input
                          type="number"
                          min={1}
                          value={setupDraft.customSlideCount}
                          onChange={(e) => setSetupDraft((prev) => ({ ...prev, customSlideCount: Number(e.target.value) || 1 }))}
                          className="h-10 w-full rounded-[18px] border-slate-200 bg-white shadow-sm"
                          placeholder="请输入页数"
                        />
                      )}
                    </div>

                    <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">选择风格</Label>
                      <Select value={setupDraft.style} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, style: value as TrainingStyle }))}>
                        <SelectTrigger className="h-10 w-full rounded-xl border-slate-200 bg-white px-3 shadow-sm">
                          <SelectValue>{styleSummary}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {styleOptions.map((item) => (
                            <SelectItem key={item.value} value={item.value}>
                              {item.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5 min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">有无备注</Label>
                      <Select
                        value={setupDraft.includeSpeakerNotes ? 'yes' : 'no'}
                        onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, includeSpeakerNotes: value === 'yes' }))}
                      >
                        <SelectTrigger className="h-10 w-full rounded-xl border-slate-200 bg-white px-3 shadow-sm">
                          <SelectValue>{notesSummary}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="yes">有</SelectItem>
                          <SelectItem value="no">无</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Button
                    onClick={generateOutline}
                    disabled={loadingOutline || selectedSources.length === 0}
                    className="h-10 shrink-0 rounded-xl bg-indigo-600 px-5 hover:bg-indigo-700 xl:ml-6 xl:self-center"
                  >
                    {loadingOutline ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <WandSparkles className="mr-2 h-4 w-4" />}
                    生成大纲
                  </Button>
                </div>
              </CardContent>
            </Card>

            {outline && (
              <Card className="border-slate-200">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                      <WandSparkles className="h-4 w-4 text-indigo-600" />
                      逐页大纲
                    </CardTitle>
                    <Button variant="outline" onClick={addSlide}>
                      <Plus className="mr-2 h-4 w-4" />
                      新增页面
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      <div className="font-medium text-slate-900">页数</div>
                      <div className="mt-1">{outline.slides.length} 页</div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      <div className="font-medium text-slate-900">主题</div>
                      <div className="mt-1 truncate">{outline.topic}</div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      <div className="font-medium text-slate-900">时长</div>
                      <div className="mt-1">{outline.duration_minutes} 分钟</div>
                    </div>
                  </div>

                  {outline.warnings.length > 0 && (
                    <div className="space-y-2">
                      {outline.warnings.map((warning) => (
                        <div key={warning} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                          {warning}
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-4">
                    {outline.slides.map((slide, index) => (
                      <OutlineSlideCard
                        key={slide.id}
                        slide={slide}
                        index={index}
                        total={outline.slides.length}
                        onChange={(next) => updateSlide(index, next)}
                        onRemove={() => removeSlide(index)}
                        onMoveUp={() => moveSlide(index, -1)}
                        onMoveDown={() => moveSlide(index, 1)}
                      />
                    ))}
                  </div>

                  <Separator />

                  <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={generatePpt} disabled={loadingGenerate || outline.slides.length === 0} className="bg-indigo-600 hover:bg-indigo-700">
                      {loadingGenerate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                      生成PPT
                    </Button>
                    {downloadUrl && (
                      <Button asChild variant="outline">
                        <a href={downloadUrl} target="_blank" rel="noreferrer">
                          <Download className="mr-2 h-4 w-4" />
                          下载PPT {filename ? `(${filename})` : ''}
                        </a>
                      </Button>
                    )}
                    {notesDownloadUrl && setupDraft.includeSpeakerNotes && (
                      <Button asChild variant="outline">
                        <a href={notesDownloadUrl} target="_blank" rel="noreferrer">
                          <FileText className="mr-2 h-4 w-4" />
                          下载Word备注 {notesFilename ? `(${notesFilename})` : ''}
                        </a>
                      </Button>
                    )}
                  </div>

                  {qualityReport && (
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-base text-slate-900">质量检查</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className={`rounded-lg border p-3 text-sm ${qualityReport.passed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                          {qualityReport.summary}
                        </div>
                        {qualityReport.issues.length > 0 && (
                          <div className="space-y-2">
                            {qualityReport.issues.map((issue, idx) => (
                              <div
                                key={`${issue.code}-${idx}`}
                                className={`rounded-lg border p-3 text-sm ${
                                  issue.level === 'error'
                                    ? 'border-rose-200 bg-rose-50 text-rose-700'
                                    : issue.level === 'warning'
                                      ? 'border-amber-200 bg-amber-50 text-amber-700'
                                      : 'border-slate-200 bg-slate-50 text-slate-700'
                                }`}
                              >
                                <div className="font-medium">{issue.message}</div>
                                {issue.suggestion && <div className="mt-1 text-xs opacity-80">建议：{issue.suggestion}</div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {presentation && (
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-base text-slate-900">生成结果</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3 text-sm text-slate-600">
                        <div>标题：{presentation.title}</div>
                        <div>风格：{presentation.style}</div>
                        <div>页数：{presentation.slides.length}</div>
                      </CardContent>
                    </Card>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
