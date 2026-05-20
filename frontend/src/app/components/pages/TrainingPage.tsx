import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, CheckCircle2, CircleX, Download, Eye, FileText, Globe, History, Loader2, Plus, RefreshCw, Trash2, Upload, WandSparkles, X } from 'lucide-react';
import { useApp } from '../../../lib/context';
import { docApi, trainingApi } from '../../../lib/api';
import type {
  DocumentInfo,
  KnowledgeBase,
  PresentationSpec,
  QualityReport,
  TrainingGenerateResponse,
  TrainingHtmlGenerateResponse,
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
type SlideCountChoice = '8' | '10' | '12' | '15' | '18' | '20' | '25' | 'custom';
type TrainingHistoryKind = 'html' | 'ppt';
type GenerationKind = 'html' | 'outline' | 'ppt';

const TRAINING_MODE_KEY = 'anniu-training-mode-v1';
const TRAINING_DRAFT_KEY = 'anniu-training-draft-v1';

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
};

type TrainingDraftStorage = {
  mode?: MainMode;
  setupDraft?: PptSetupDraft;
  htmlTitle?: string;
  htmlReportDate?: string;
  htmlPresenter?: string;
  htmlAudience?: string;
  htmlRequirements?: string;
  selectedSources?: TrainingSourceInput[];
};

type TrainingHistoryItem = {
  id: string;
  kind: TrainingHistoryKind;
  title: string;
  createdAt: string;
  pageCount: number;
  downloadUrl: string;
  previewUrl?: string;
  filename: string;
  notesDownloadUrl?: string;
  notesFilename?: string;
};

const TRAINING_HISTORY_KEY = 'anniu-training-history-v1';

function createDefaultPptSetup(kbId = ''): PptSetupDraft {
  return {
    sourceMode: 'kb_document',
    kbId,
    documentId: '',
    requirement: '请突出应急处置、报警流程和初期火灾扑救',
    slideCountChoice: '15',
    customSlideCount: 12,
    style: 'standard_training',
    includeSpeakerNotes: true,
  };
}

function readTrainingDraft(): TrainingDraftStorage | null {
  try {
    const raw = localStorage.getItem(TRAINING_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as TrainingDraftStorage;
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function readTrainingHistory(): TrainingHistoryItem[] {
  try {
    const raw = localStorage.getItem(TRAINING_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as TrainingHistoryItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function createJobId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `job-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

const styleOptions: { value: TrainingStyle; label: string; desc: string }[] = [
  { value: 'standard_training', label: '标准安全培训', desc: '适合常规安全生产培训，结构均衡' },
  { value: 'management_briefing', label: '管理层汇报', desc: '强调结论、风险矩阵和责任闭环' },
  { value: 'frontline_shift_training', label: '班组宣贯', desc: '字更大、少字、动作导向' },
];

const strongFieldClassName =
  'border-slate-300 bg-white shadow-sm shadow-slate-100/80 focus-visible:border-indigo-500 focus-visible:ring-indigo-200/60';
const strongSelectTriggerClassName =
  'border-slate-300 bg-white shadow-sm shadow-slate-100/80 focus-visible:border-indigo-500 focus-visible:ring-indigo-200/60';
const strongTextareaClassName =
  'border-slate-300 bg-white shadow-sm shadow-slate-100/80 focus-visible:border-indigo-500 focus-visible:ring-indigo-200/60';

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

function sourceKey(source: TrainingSourceInput) {
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
}

function SourceTagList({
  items,
  knowledgeBases,
  onRemove,
}: {
  items: TrainingSourceInput[];
  knowledgeBases: KnowledgeBase[];
  onRemove: (source: TrainingSourceInput) => void;
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((source, index) => (
        <div
          key={`${source.type}-${sourceKey(source)}-${index}`}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm"
        >
          <span className="max-w-[240px] truncate">{sourceLabel(source, knowledgeBases)}</span>
          <button
            type="button"
            onClick={() => onRemove(source)}
            className="text-slate-400 transition hover:text-slate-700"
            aria-label="移除来源"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

function InlineField({
  label,
  value,
  onChange,
  placeholder,
  helper,
  type = 'text',
  min,
  max,
  className = '',
  stacked = false,
}: {
  label: ReactNode;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  helper?: string;
  type?: 'text' | 'number';
  min?: number;
  max?: number;
  className?: string;
  stacked?: boolean;
}) {
  const [draftValue, setDraftValue] = useState(String(value));

  useEffect(() => {
    setDraftValue(String(value));
  }, [value]);

  const clampNumberString = (raw: string): string => {
    const num = Number(raw);
    if (!Number.isFinite(num)) {
      return raw;
    }
    let clamped = num;
    if (typeof max === 'number' && clamped > max) clamped = max;
    // 下限不在输入过程中强制提升，避免打断用户输入。
    return String(clamped);
  };

  const commitNumberValue = () => {
    if (type !== 'number') {
      return;
    }
    const next = draftValue.trim();
    if (!next) {
      onChange('');
      return;
    }
    onChange(next);
  };

  return (
    <div className="min-w-0 space-y-1">
      <div className={stacked ? 'space-y-2' : 'flex items-center gap-3'}>
        <Label className={`${stacked ? 'block' : 'shrink-0 whitespace-nowrap'} text-sm font-medium text-slate-800`}>{label}</Label>
        <Input
          value={type === 'number' ? draftValue : value}
          onChange={(e) => {
            if (type === 'number') {
              const raw = e.target.value;
              // 超过上限时实时夹到上限，避免输入出 31 这种超出范围的值。
              const clamped = raw === '' ? '' : clampNumberString(raw);
              setDraftValue(clamped);
              if (clamped !== '' && clamped !== raw) {
                onChange(clamped);
              }
              return;
            }
            onChange(e.target.value);
          }}
          onBlur={commitNumberValue}
          onKeyDown={(e) => {
            if (type === 'number' && e.key === 'Enter') {
              commitNumberValue();
            }
          }}
          placeholder={placeholder}
          type={type}
          min={min}
          max={max}
          inputMode={type === 'number' ? 'numeric' : undefined}
          className={`${stacked ? 'h-10 w-full' : 'h-10 flex-1 min-w-0'} ${className}`}
        />
      </div>
      {helper && <p className="truncate text-xs text-slate-500">{helper}</p>}
    </div>
  );
}

function buildSlideCount(choice: SlideCountChoice, customSlideCount: number) {
  if (choice === 'custom') {
    return Math.min(30, Math.max(5, customSlideCount || 5));
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
            <Input
              value={slide.title}
              onChange={(e) => onChange({ ...slide, title: e.target.value })}
              className={strongFieldClassName}
            />
          </div>
          <div className="space-y-1">
            <Label>页面类型</Label>
            <Select value={slide.slide_type} onValueChange={(value) => onChange({ ...slide, slide_type: value as TrainingOutlineSlide['slide_type'] })}>
              <SelectTrigger className={strongSelectTriggerClassName}>
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
            className={strongTextareaClassName}
          />
        </div>
        <div className="space-y-1">
          <Label>讲稿备注</Label>
          <Textarea
            rows={3}
            value={slide.notes || ''}
            onChange={(e) => onChange({ ...slide, notes: e.target.value })}
            placeholder="用于讲解时的备注"
            className={strongTextareaClassName}
          />
        </div>
        <div className="space-y-1">
          <Label>版式提示</Label>
          <Input
            value={slide.layout_hint || ''}
            onChange={(e) => onChange({ ...slide, layout_hint: e.target.value })}
            placeholder="例如：两栏 / 时间线 / 卡片"
            className={strongFieldClassName}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function TopModeCard({
  active,
  disabled,
  title,
  subtitle,
  icon,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  title: string;
  subtitle: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-[64px] flex-1 items-center gap-3 rounded-2xl border px-3 py-2.5 text-left transition ${
        active ? 'border-emerald-300 bg-emerald-50 text-emerald-950' : 'border-slate-200 bg-white hover:border-slate-300'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
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
  const {
    knowledgeBases,
    currentKbId,
    htmlGeneration,
    updateHtmlGeneration,
    resetHtmlGeneration,
  } = useApp();
  const persistedDraft = useMemo(readTrainingDraft, []);
  const [mode, setMode] = useState<MainMode>(() => {
    if (persistedDraft?.mode === 'html' || persistedDraft?.mode === 'ppt') {
      return persistedDraft.mode;
    }
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
  const [setupDraft, setSetupDraft] = useState<PptSetupDraft>(() => persistedDraft?.setupDraft || createDefaultPptSetup(currentKbId || ''));
  const [htmlTitle, setHtmlTitle] = useState(() => persistedDraft?.htmlTitle || '');
  const [htmlReportDate, setHtmlReportDate] = useState(() => persistedDraft?.htmlReportDate || '');
  const [htmlPresenter, setHtmlPresenter] = useState(() => persistedDraft?.htmlPresenter || '');
  const [htmlAudience, setHtmlAudience] = useState(() => persistedDraft?.htmlAudience || '');
  const [htmlRequirements, setHtmlRequirements] = useState(
    () =>
      persistedDraft?.htmlRequirements ||
      '例如：请根据应急预案生成一份面向班组长的应急处置培训材料，重点突出报警流程、初期处置、岗位职责和常见错误。',
  );
  const [selectedSources, setSelectedSources] = useState<TrainingSourceInput[]>(() => persistedDraft?.selectedSources || []);
  const [kbResources, setKbResources] = useState<Record<string, KbResources>>({});
  const [outline, setOutline] = useState<TrainingOutline | null>(null);
  const [presentation, setPresentation] = useState<PresentationSpec | null>(null);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [pptDownloadUrl, setPptDownloadUrl] = useState<string>('');
  const [pptFilename, setPptFilename] = useState<string>('');
  const [notesDownloadUrl, setNotesDownloadUrl] = useState<string>('');
  const [notesFilename, setNotesFilename] = useState<string>('');
  const [jobId, setJobId] = useState<string>('');
  const [loadingOutline, setLoadingOutline] = useState(false);
  const [loadingPptGenerate, setLoadingPptGenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kbDocumentPickerOpen, setKbDocumentPickerOpen] = useState(false);
  const [pendingKbDocumentIds, setPendingKbDocumentIds] = useState<string[]>([]);
  const [newMenuOpen, setNewMenuOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [trainingHistory, setTrainingHistory] = useState<TrainingHistoryItem[]>(() => readTrainingHistory());
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const isMountedRef = useRef(true);
  const generationRef = useRef<{ kind: GenerationKind; jobId: string; controller: AbortController } | null>(null);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void trainingApi.cleanupUploads().catch(() => {
      // 清理失败不影响页面主流程
    });
  }, []);

  const isGenerationLocked = htmlGeneration.loading || loadingOutline || loadingPptGenerate;
  const activeGenerationKind: GenerationKind | null = htmlGeneration.loading
    ? 'html'
    : loadingOutline
      ? 'outline'
      : loadingPptGenerate
        ? 'ppt'
        : null;

  const setActiveGeneration = (kind: GenerationKind, jobId: string) => {
    const controller = new AbortController();
    generationRef.current = { kind, jobId, controller };
    setHistoryOpen(false);
    setNewMenuOpen(false);
    setKbDocumentPickerOpen(false);
    return controller;
  };

  const clearActiveGeneration = () => {
    generationRef.current = null;
  };

  const discardGeneratedOutputs = (kind: GenerationKind) => {
    if (kind === 'html') {
      resetHtmlGeneration();
      return;
    }
    setPptDownloadUrl('');
    setPptFilename('');
    setNotesDownloadUrl('');
    setNotesFilename('');
    setPresentation(null);
    setQualityReport(null);
    if (kind === 'outline') {
      setOutline(null);
    }
    setJobId('');
  };

  const stopCurrentGeneration = () => {
    const current = generationRef.current;
    if (!current) return;
    current.controller.abort();
    discardGeneratedOutputs(current.kind);
    setLoadingOutline(false);
    setLoadingPptGenerate(false);
    setError(null);
    clearActiveGeneration();
    void trainingApi.cancelJob(current.jobId).catch(() => {
      // ignore cancellation failures; UI already reset locally
    });
  };

  const slideCount = buildSlideCount('custom', setupDraft.customSlideCount);
  const durationMinutes = useMemo(() => durationFromSlideCount(slideCount), [slideCount]);
  const selectedSourceSummary = useMemo(() => {
    if (selectedSources.length === 0) return '选择文档';
    if (selectedSources.length === 1) return sourceLabel(selectedSources[0], knowledgeBases);
    return `已选 ${selectedSources.length} 个文档`;
  }, [knowledgeBases, selectedSources]);
  const styleSummary = useMemo(() => styleOptions.find((item) => item.value === setupDraft.style)?.label || '选择风格', [setupDraft.style]);
  const notesSummary = setupDraft.includeSpeakerNotes ? '有' : '无';
  const selectedHtmlSources = useMemo(() => selectedSources.filter((source) => source.type === 'kb_document' || source.type === 'temporary_upload'), [selectedSources]);
  const selectedUploadSources = useMemo(() => selectedSources.filter((source) => source.type === 'temporary_upload'), [selectedSources]);
  const selectedKbSources = useMemo(() => selectedSources.filter((source) => source.type === 'kb_document'), [selectedSources]);
  const selectedKbDocsInCurrentKb = useMemo(
    () =>
      selectedKbSources.filter(
        (source) => source.kb_id === setupDraft.kbId && Boolean(source.document_id),
      ),
    [selectedKbSources, setupDraft.kbId],
  );
  const currentKbDocs = useMemo(() => kbResources[setupDraft.kbId]?.docs || [], [kbResources, setupDraft.kbId]);
  const pendingKbDocumentSet = useMemo(() => new Set(pendingKbDocumentIds), [pendingKbDocumentIds]);

  const appendTrainingHistory = (item: TrainingHistoryItem) => {
    setTrainingHistory((prev) => [item, ...prev.filter((entry) => entry.id !== item.id)].slice(0, 20));
  };

  const removeTrainingHistory = (id: string) => {
    setTrainingHistory((prev) => prev.filter((item) => item.id !== id));
  };

  useEffect(() => {
    if (!setupDraft.kbId && knowledgeBases[0]) {
      setSetupDraft((prev) => ({ ...prev, kbId: currentKbId || knowledgeBases[0].id }));
    }
  }, [currentKbId, knowledgeBases, setupDraft.kbId]);

  useEffect(() => {
    const availableKbIds = new Set(knowledgeBases.map((kb) => kb.id));
    const fallbackKbId = currentKbId || knowledgeBases[0]?.id || '';
    if (!fallbackKbId) return;
    setSetupDraft((prev) => {
      if (prev.kbId && availableKbIds.has(prev.kbId)) {
        return prev;
      }
      if (prev.kbId === fallbackKbId) {
        return prev;
      }
      return { ...prev, kbId: fallbackKbId };
    });
  }, [currentKbId, knowledgeBases]);

  useEffect(() => {
    if (!kbDocumentPickerOpen || setupDraft.sourceMode !== 'kb_document' || !setupDraft.kbId) {
      return;
    }
    setPendingKbDocumentIds(selectedKbDocsInCurrentKb.map((source) => source.document_id as string));
  }, [kbDocumentPickerOpen, selectedKbDocsInCurrentKb, setupDraft.kbId, setupDraft.sourceMode]);

  useEffect(() => {
    try {
      localStorage.setItem(TRAINING_MODE_KEY, mode);
    } catch {
      // ignore storage failures
    }
  }, [mode]);

  useEffect(() => {
    try {
      const payload: TrainingDraftStorage = {
        mode,
        setupDraft,
        htmlTitle,
        htmlReportDate,
        htmlPresenter,
        htmlAudience,
        htmlRequirements,
        selectedSources,
      };
      localStorage.setItem(TRAINING_DRAFT_KEY, JSON.stringify(payload));
    } catch {
      // ignore storage failures
    }
  }, [htmlAudience, htmlPresenter, htmlReportDate, htmlRequirements, htmlTitle, mode, selectedSources, setupDraft]);

  useEffect(() => {
    try {
      localStorage.setItem(TRAINING_HISTORY_KEY, JSON.stringify(trainingHistory));
    } catch {
      // ignore storage failures
    }
  }, [trainingHistory]);

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

  useEffect(() => {
    if (!isGenerationLocked) return;
    setHistoryOpen(false);
    setNewMenuOpen(false);
    setKbDocumentPickerOpen(false);
  }, [isGenerationLocked]);

  const resetWorkflow = (nextMode: MainMode = 'ppt') => {
    generationRef.current?.controller.abort();
    clearActiveGeneration();
    setMode(nextMode);
    setSetupDraft(createDefaultPptSetup(currentKbId || knowledgeBases[0]?.id || ''));
    setHtmlTitle('');
    setHtmlReportDate('');
    setHtmlPresenter('');
    setHtmlAudience('');
    setHtmlRequirements('');
    setSelectedSources([]);
    setOutline(null);
    setPresentation(null);
    setQualityReport(null);
    setPptDownloadUrl('');
    setPptFilename('');
    resetHtmlGeneration();
    setNotesDownloadUrl('');
    setNotesFilename('');
    setJobId('');
    setLoadingOutline(false);
    setLoadingPptGenerate(false);
    setError(null);
    setKbDocumentPickerOpen(false);
    setPendingKbDocumentIds([]);
    setNewMenuOpen(false);
    setHistoryOpen(false);
    uploadInputRef.current && (uploadInputRef.current.value = '');
    try {
      localStorage.removeItem(TRAINING_DRAFT_KEY);
    } catch {
      // ignore storage failures
    }
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

  const removeSourceByKey = (target: TrainingSourceInput) => {
    const key = sourceKey(target);
    setSelectedSources((prev) => prev.filter((item) => sourceKey(item) !== key));
  };

  const addKbDocumentSources = (documentIdsOverride?: string[]) => {
    if (!setupDraft.kbId) {
      setError('请选择知识库');
      return;
    }
    const documentIds =
      documentIdsOverride && documentIdsOverride.length > 0
        ? documentIdsOverride
        : pendingKbDocumentIds.length > 0
          ? pendingKbDocumentIds
          : setupDraft.documentId
            ? [setupDraft.documentId]
            : [];
    if (documentIds.length === 0) {
      setError('请选择至少一个知识库文档');
      return;
    }
    const docs = currentKbDocs
      .filter((doc) => documentIds.includes(doc.id))
      .map((doc) => ({
        type: 'kb_document' as const,
        kb_id: setupDraft.kbId,
        document_id: doc.id,
        title: doc.file || '知识库文档',
      }));
    setSelectedSources((prev) => dedupeSources([...prev, ...docs]));
    setKbDocumentPickerOpen(false);
    setPendingKbDocumentIds([]);
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
    const nextJobId = jobId || createJobId();
    const controller = setActiveGeneration('outline', nextJobId);
    setJobId(nextJobId);
    setOutline(null);
    setPresentation(null);
    setQualityReport(null);
    setPptDownloadUrl('');
    setPptFilename('');
    setNotesDownloadUrl('');
    setNotesFilename('');
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
        job_id: nextJobId,
      }, controller.signal);
      if (isMountedRef.current) {
        setJobId(res.job_id);
        setOutline(res.outline);
      }
    } catch (err) {
      if (!controller.signal.aborted && isMountedRef.current) {
        setError(err instanceof Error ? err.message : '生成大纲失败');
      }
    } finally {
      if (generationRef.current?.jobId === nextJobId) {
        clearActiveGeneration();
      }
      if (isMountedRef.current) {
        setLoadingOutline(false);
      }
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
    const nextJobId = jobId || createJobId();
    const controller = setActiveGeneration('ppt', nextJobId);
    setJobId(nextJobId);
    setLoadingPptGenerate(true);
    setError(null);
    try {
      const res: TrainingGenerateResponse = await trainingApi.generatePpt({
        job_id: nextJobId,
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
      }, controller.signal);
      if (isMountedRef.current) {
        setJobId(res.job_id);
        setPresentation(res.presentation);
        setQualityReport(res.quality_report);
        setPptDownloadUrl(trainingApi.download(res.filename));
        setPptFilename(res.filename);
        setNotesDownloadUrl(res.notes_download_url || '');
        setNotesFilename(res.notes_filename || '');
        appendTrainingHistory({
          id: `${Date.now()}`,
          kind: 'ppt',
          title: res.presentation.title || res.presentation.topic || 'PPT',
          createdAt: new Date().toISOString(),
          pageCount: res.presentation.slides.length,
          downloadUrl: trainingApi.download(res.filename),
          filename: res.filename,
          notesDownloadUrl: res.notes_download_url ? trainingApi.resolveUrl(res.notes_download_url) : undefined,
          notesFilename: res.notes_filename || undefined,
        });
      }
    } catch (err) {
      if (!controller.signal.aborted && isMountedRef.current) {
        setError(err instanceof Error ? err.message : '生成 PPT 失败');
      }
    } finally {
      if (generationRef.current?.jobId === nextJobId) {
        clearActiveGeneration();
      }
      if (isMountedRef.current) {
        setLoadingPptGenerate(false);
      }
    }
  };

  const generateHtml = async () => {
    const title = htmlTitle.trim();
    if (!title) {
      setError('请输入本次材料标题');
      return;
    }
    if (!Number.isFinite(slideCount) || slideCount < 5 || slideCount > 30) {
      setError('页数必须是 5 到 30 之间的有效数字');
      return;
    }
    const nextJobId = createJobId();
    const controller = setActiveGeneration('html', nextJobId);
    setError(null);
    resetHtmlGeneration();
    updateHtmlGeneration({ loading: true, error: null });
    setPresentation(null);
    setQualityReport(null);
    setOutline(null);
    setNotesDownloadUrl('');
    setNotesFilename('');
    try {
      const res: TrainingHtmlGenerateResponse = await trainingApi.generateTrainingHtml({
        kb_id: setupDraft.kbId || currentKbId || null,
        title,
        report_date: htmlReportDate.trim() || null,
        presenter: htmlPresenter.trim() || null,
        audience: htmlAudience.trim() || null,
        requirements: htmlRequirements.trim() || null,
        job_id: nextJobId,
        sources: selectedHtmlSources,
        document_ids: selectedSources
          .filter((source) => source.type === 'kb_document' && source.document_id)
          .map((source) => source.document_id as string),
        page_count: slideCount,
      }, controller.signal);
      updateHtmlGeneration({
        loading: false,
        error: null,
        title: res.title,
        html: res.html,
        slideCount: res.slide_count,
        downloadUrl: trainingApi.resolveUrl(res.download_url),
        previewUrl: trainingApi.resolveUrl(res.preview_url || res.download_url),
        filename: res.filename,
      });
      appendTrainingHistory({
        id: `${Date.now()}`,
        kind: 'html',
        title: res.title,
        createdAt: new Date().toISOString(),
        pageCount: res.slide_count,
        downloadUrl: trainingApi.resolveUrl(res.download_url),
        previewUrl: trainingApi.resolveUrl(res.preview_url || res.download_url),
        filename: res.filename,
      });
      if (isMountedRef.current) {
        setPresentation(null);
        setQualityReport(null);
        setNotesDownloadUrl('');
        setNotesFilename('');
      }
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      const message = err instanceof Error ? err.message : '生成网页失败';
      if (isMountedRef.current) {
        setError(message);
      }
      updateHtmlGeneration({
        loading: false,
        error: message,
      });
    } finally {
      if (generationRef.current?.jobId === nextJobId) {
        clearActiveGeneration();
      }
    }
  };

  const openHtmlPreview = () => {
    const previewUrl = htmlGeneration.previewUrl || htmlGeneration.downloadUrl;
    if (!previewUrl) return;
    const previewWindow = window.open(previewUrl, '_blank', 'noopener,noreferrer');
    if (!previewWindow) {
      setError('浏览器阻止了新窗口，请允许弹窗后重试');
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-slate-900">培训材料生成</h1>
          <div className="flex items-center gap-2">
            {activeGenerationKind && (
              <Button variant="destructive" onClick={() => void stopCurrentGeneration()}>
                <CircleX className="mr-2 h-4 w-4" />
                停止生成
              </Button>
            )}
            <Popover open={historyOpen} onOpenChange={setHistoryOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" disabled={isGenerationLocked}>
                  <History className="mr-2 h-4 w-4" />
                  历史记录
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-[760px] max-w-[calc(100vw-1rem)] rounded-2xl border-slate-200 p-4 shadow-2xl">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">培训材料历史</div>
                    <div className="text-xs text-slate-500">查看、下载或删除你之前生成过的培训材料</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTrainingHistory([])}
                    className="text-xs text-slate-400 transition hover:text-slate-600"
                  >
                    清空
                  </button>
                </div>
                <div className="max-h-[70vh] space-y-3 overflow-auto pr-1">
                  {trainingHistory.length > 0 ? (
                    trainingHistory.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${item.kind === 'html' ? 'bg-emerald-50 text-emerald-700' : 'bg-indigo-50 text-indigo-700'}`}>
                                {item.kind === 'html' ? '网页' : 'PPT'}
                              </span>
                              <div className="min-w-0 truncate text-sm font-medium text-slate-900">{item.title}</div>
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                              <span>{new Date(item.createdAt).toLocaleString()}</span>
                              <span>{item.pageCount} 页</span>
                              <span className="truncate">{item.filename}</span>
                            </div>
                          </div>
                          <div className="flex flex-nowrap gap-2 overflow-x-auto md:overflow-visible">
                            {item.previewUrl && item.kind === 'html' && (
                              <Button asChild size="sm" variant="outline" className="shrink-0 whitespace-nowrap">
                                <a href={item.previewUrl} target="_blank" rel="noreferrer">
                                  <Eye className="mr-2 h-3.5 w-3.5" />
                                  预览
                                </a>
                              </Button>
                            )}
                            <Button asChild size="sm" variant="outline" className="shrink-0 whitespace-nowrap">
                              <a href={item.downloadUrl} target="_blank" rel="noreferrer" download>
                                <Download className="mr-2 h-3.5 w-3.5" />
                                下载
                              </a>
                            </Button>
                            {item.notesDownloadUrl && (
                              <Button asChild size="sm" variant="outline" className="shrink-0 whitespace-nowrap">
                                <a href={item.notesDownloadUrl} target="_blank" rel="noreferrer" download>
                                  <Download className="mr-2 h-3.5 w-3.5" />
                                  讲稿
                                </a>
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                if (window.confirm('确定删除这条历史记录吗？')) {
                                  removeTrainingHistory(item.id);
                                }
                              }}
                              className="shrink-0 whitespace-nowrap text-rose-600 hover:text-rose-700"
                            >
                              <Trash2 className="mr-2 h-3.5 w-3.5" />
                              删除
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-400">
                      暂无历史记录
                    </div>
                  )}
                </div>
              </PopoverContent>
            </Popover>

            <Popover open={newMenuOpen} onOpenChange={setNewMenuOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" disabled={isGenerationLocked}>
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
                      <div className="text-sm font-medium text-slate-900">生成网页</div>
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
      </div>

      <div className={`flex-1 overflow-auto px-6 py-4 ${isGenerationLocked ? 'generation-lock opacity-90' : ''}`} aria-busy={isGenerationLocked}>
        <div className="mb-3 flex gap-2">
          <TopModeCard
            active={mode === 'html'}
            disabled={isGenerationLocked}
            title="生成精美网页"
            subtitle="适用日常汇报培训"
            icon={<Globe className="h-5 w-5" />}
            onClick={() => setMode('html')}
          />
          <TopModeCard
            active={mode === 'ppt'}
            disabled={isGenerationLocked}
            title="生成可导出的PPT"
            subtitle="适用自由编辑修改"
            icon={<FileText className="h-5 w-5" />}
            onClick={() => setMode('ppt')}
          />
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-700">
            {error}
          </div>
        )}

        {mode === 'html' ? (
          <div className="space-y-4">
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="space-y-4 p-3.5 lg:p-4">
                <div className="grid gap-3 xl:grid-cols-3">
                  <InlineField
                    label={(
                      <>
                        材料标题 <span className="text-rose-500">*</span>
                      </>
                    )}
                    value={htmlTitle}
                    onChange={setHtmlTitle}
                    placeholder="请输入本次培训/汇报/展示材料标题"
                    helper="将展示在第一页封面，并作为整份材料的主题。"
                    className={strongFieldClassName}
                    stacked
                  />
                  <InlineField
                    label="汇报时间"
                    value={htmlReportDate}
                    onChange={setHtmlReportDate}
                    placeholder="例如：2026年5月 / 2026年5月12日"
                    helper="选填，将展示在第一页。"
                    className={strongFieldClassName}
                    stacked
                  />
                  <InlineField
                    label="输入页数"
                    value={setupDraft.customSlideCount}
                    onChange={(value) => {
                      const next = Number(value);
                      setSetupDraft((prev) => ({
                        ...prev,
                        slideCountChoice: 'custom',
                        customSlideCount: Number.isFinite(next) ? Math.max(5, Math.min(30, next)) : 5,
                      }));
                    }}
                    type="number"
                    min={5}
                    max={30}
                    placeholder="5 到 30"
                    helper="请输入 5 到 30。"
                    className={strongFieldClassName}
                    stacked
                  />
                </div>

                <div className="grid gap-3 xl:grid-cols-3">
                  <InlineField
                    label="汇报人"
                    value={htmlPresenter}
                    onChange={setHtmlPresenter}
                    placeholder="例如：安全管理部 / 张三"
                    helper="选填，将展示在第一页。"
                    className={strongFieldClassName}
                    stacked
                  />
                  <InlineField
                    label="汇报对象"
                    value={htmlAudience}
                    onChange={setHtmlAudience}
                    placeholder="例如：一线作业人员、班组长、企业主要负责人、监管检查组"
                    helper="用于调整内容深度、语气和展示方式。"
                    className={strongFieldClassName}
                    stacked
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-sm font-medium text-slate-800">生成要求 / 内容说明</Label>
                  <p className="truncate text-xs text-slate-500">请说明本次材料的用途、重点、受众、希望强调的内容、是否需要事故案例/互动题/检查清单等。</p>
                  <Textarea
                    rows={3}
                    value={htmlRequirements}
                    onChange={(e) => setHtmlRequirements(e.target.value)}
                    placeholder="例如：请根据应急预案生成一份面向班组长的应急处置培训材料，重点突出报警流程、初期处置、岗位职责和常见错误。"
                    className={`min-h-[96px] max-h-[280px] resize-y overflow-y-auto ${strongTextareaClassName}`}
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-700">生成网页</div>
                    <div className="text-xs text-slate-500">先补齐来源后即可生成，按钮会保持在首屏可见。</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {(htmlGeneration.html || htmlGeneration.downloadUrl) && !htmlGeneration.loading && (
                      <span className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
                        <CheckCircle2 className="h-4 w-4" />
                        已生成网页
                      </span>
                    )}
                    <Button
                      onClick={generateHtml}
                      disabled={htmlGeneration.loading || !htmlTitle.trim()}
                      className="h-10 shrink-0 rounded-xl bg-indigo-600 px-5 hover:bg-indigo-700"
                    >
                      {htmlGeneration.loading ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (htmlGeneration.html || htmlGeneration.downloadUrl) ? (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      ) : (
                        <Globe className="mr-2 h-4 w-4" />
                      )}
                      {(htmlGeneration.html || htmlGeneration.downloadUrl) && !htmlGeneration.loading ? '重新生成' : '生成网页'}
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="space-y-2.5 rounded-2xl border border-slate-200 bg-slate-50 p-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <Label className="text-sm font-medium text-slate-700">用户自己上传文档</Label>
                        <p className="text-xs text-slate-500">支持一次选择多个文件，上传后会自动加入本次材料来源。</p>
                      </div>
                      <Button type="button" variant="outline" className="h-10 shrink-0" onClick={() => uploadInputRef.current?.click()}>
                        <Upload className="mr-2 h-4 w-4" />
                        上传文档
                      </Button>
                    </div>
                    <input
                      ref={uploadInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.doc,.docx,.txt,.md,.markdown"
                      className="hidden"
                      onChange={(e) => e.target.files && void handleUpload(e.target.files)}
                    />
                    <SourceTagList
                      items={selectedUploadSources}
                      knowledgeBases={knowledgeBases}
                      onRemove={removeSourceByKey}
                    />
                  </div>

                  <div className="space-y-2.5 rounded-2xl border border-slate-200 bg-slate-50 p-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <Label className="text-sm font-medium text-slate-700">选择现有知识库的文档</Label>
                        <p className="text-xs text-slate-500">可以一次勾选多个知识库文档加入本次材料。</p>
                      </div>
                      <Popover open={kbDocumentPickerOpen} onOpenChange={setKbDocumentPickerOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-10 shrink-0 rounded-xl border-slate-200 bg-white px-3 text-slate-900 shadow-sm"
                        >
                            {selectedKbSources.length > 0 ? `已选 ${selectedKbSources.length} 个文档` : '选择知识库文档'}
                        </Button>
                      </PopoverTrigger>
                        <PopoverContent align="end" className="w-[720px] max-w-[calc(100vw-2rem)] rounded-[24px] border-slate-200 p-4 shadow-2xl">
                          {knowledgeBases.length === 0 ? (
                            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                              当前还没有知识库。可以直接上传文档，或先到知识库页面上传安全制度、应急预案、操作规程等资料。
                            </div>
                          ) : (
                            <div className="space-y-4">
                              <div className="space-y-2">
                                <Label className="text-sm font-medium text-slate-700">选择知识库</Label>
                                <Select
                                  value={setupDraft.kbId}
                                  onValueChange={(value) => {
                                    setSetupDraft((prev) => ({ ...prev, kbId: value }));
                                    setPendingKbDocumentIds([]);
                                  }}
                                >
                                  <SelectTrigger className={`h-10 min-w-0 ${strongSelectTriggerClassName}`}>
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
                              </div>

                              {setupDraft.kbId ? (
                                <div className="space-y-3">
                                  <div className="max-h-[320px] space-y-2 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-3">
                                    {kbResources[setupDraft.kbId]?.loading ? (
                                      <p className="px-1 py-6 text-center text-sm text-slate-500">正在加载当前知识库的文档...</p>
                                    ) : currentKbDocs.length === 0 ? (
                                      <p className="px-1 py-6 text-center text-sm text-slate-500">当前知识库暂无可选文档。</p>
                                    ) : (
                                      currentKbDocs.map((doc) => {
                                        const checked = pendingKbDocumentSet.has(doc.id);
                                        return (
                                          <label
                                            key={doc.id}
                                            className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2 transition ${
                                              checked ? 'border-indigo-200 bg-indigo-50/60' : 'border-transparent hover:border-slate-200 hover:bg-slate-50'
                                            }`}
                                          >
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={(event) => {
                                                const nextChecked = event.target.checked;
                                                setPendingKbDocumentIds((prev) => {
                                                  if (nextChecked) {
                                                    return prev.includes(doc.id) ? prev : [...prev, doc.id];
                                                  }
                                                  return prev.filter((item) => item !== doc.id);
                                                });
                                              }}
                                              className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                                            />
                                            <div className="min-w-0">
                                              <div className="truncate text-sm font-medium text-slate-900">{doc.file}</div>
                                              <div className="mt-0.5 text-xs text-slate-500">
                                                {doc.page_count > 0 ? `${doc.page_count} 页` : '页数未知'}
                                                {doc.parse_status ? ` · ${doc.parse_status}` : ''}
                                              </div>
                                            </div>
                                          </label>
                                        );
                                      })
                                    )}
                                  </div>
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="text-xs text-slate-500">
                                      已勾选 {pendingKbDocumentIds.length} 个文档，点击加入后会并入本次材料来源。
                                    </p>
                                    <Button
                                      type="button"
                                      onClick={() => addKbDocumentSources()}
                                      className="h-10 shrink-0 whitespace-nowrap bg-indigo-600 hover:bg-indigo-700"
                                    >
                                      加入所选文档
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <p className="text-sm text-slate-500">请先选择一个知识库，再勾选其中的文档。</p>
                              )}
                            </div>
                          )}
                        </PopoverContent>
                      </Popover>
                    </div>
                    <SourceTagList
                      items={selectedKbSources}
                      knowledgeBases={knowledgeBases}
                      onRemove={removeSourceByKey}
                    />
                  </div>
                </div>

              </CardContent>
            </Card>

            {(htmlGeneration.downloadUrl || htmlGeneration.html || htmlGeneration.error) && (
              <Card className="border-slate-200 shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base text-slate-900">
                      <Globe className="h-4 w-4 text-emerald-600" />
                      网页结果
                    </CardTitle>
                    <div className="flex flex-wrap gap-2">
                      {htmlGeneration.html && (
                        <Button type="button" variant="outline" onClick={openHtmlPreview}>
                          <Globe className="mr-2 h-4 w-4" />
                          新窗口预览
                        </Button>
                      )}
                      {htmlGeneration.downloadUrl && (
                        <Button asChild variant="outline">
                          <a href={htmlGeneration.downloadUrl} target="_blank" rel="noreferrer" download>
                            <Download className="mr-2 h-4 w-4" />
                            下载网页文件
                          </a>
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-slate-600">
                  {htmlGeneration.error && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                      {htmlGeneration.error}
                    </div>
                  )}
                  {htmlGeneration.html && (
                    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-100">
                      {htmlGeneration.previewUrl ? (
                        <iframe
                          title="网页汇报展示材料预览"
                          src={htmlGeneration.previewUrl}
                          className="h-[620px] w-full bg-white"
                        />
                      ) : (
                        <iframe
                          title="网页汇报展示材料预览"
                          srcDoc={htmlGeneration.html}
                          sandbox="allow-scripts allow-same-origin"
                          className="h-[620px] w-full bg-white"
                        />
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="space-y-3 p-3.5 lg:p-4">
                <div className="space-y-1">
                  <Label className="text-sm font-medium text-slate-800">PPT主题 / 需求</Label>
                  <p className="truncate text-xs text-slate-500">请说明本次 PPT 的用途、重点、受众、希望强调的内容、是否需要案例/互动题/检查清单等。</p>
                  <Textarea
                    rows={3}
                    value={setupDraft.requirement}
                    onChange={(e) => setSetupDraft((prev) => ({ ...prev, requirement: e.target.value }))}
                    placeholder="PPT主题 / 需求"
                    className={`min-h-[112px] ${strongTextareaClassName}`}
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  {selectedSources.map((source, index) => (
                    <div
                      key={`${source.type}-${sourceKey(source)}-${index}`}
                      className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
                    >
                      <span className="max-w-[260px] truncate">{sourceLabel(source, knowledgeBases)}</span>
                      <button
                        type="button"
                        onClick={() => removeSourceByKey(source)}
                        className="text-slate-400 transition hover:text-slate-700"
                        aria-label="移除来源"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-700">生成大纲</div>
                    <div className="text-xs text-slate-500">先选来源和参数，按钮会尽量保持在首屏。</div>
                  </div>
                  <Button onClick={generateOutline} disabled={loadingOutline || selectedSources.length === 0} className="bg-indigo-600 hover:bg-indigo-700">
                    {loadingOutline ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <WandSparkles className="mr-2 h-4 w-4" />}
                    生成大纲
                  </Button>
                </div>

                <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch">
                  <div className="grid flex-1 min-w-0 gap-3 xl:grid-cols-4">
                    <div className="h-full min-w-0 space-y-1.5 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">选择文档</Label>
                      <Popover open={kbDocumentPickerOpen} onOpenChange={setKbDocumentPickerOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            className={`h-10 w-full justify-between rounded-xl px-3 text-slate-900 ${strongSelectTriggerClassName}`}
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
                                  <SelectTrigger className={`h-10 min-w-0 ${strongSelectTriggerClassName}`}>
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
                                  <SelectTrigger className={`h-10 min-w-0 ${strongSelectTriggerClassName}`}>
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
                                <Button type="button" onClick={() => addKbDocumentSources()} className="h-10 shrink-0 whitespace-nowrap bg-indigo-600 hover:bg-indigo-700">
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

                    <InlineField
                      label="输入页数"
                      value={setupDraft.customSlideCount}
                      onChange={(value) => {
                        const next = Number(value);
                        setSetupDraft((prev) => ({
                          ...prev,
                          slideCountChoice: 'custom',
                          customSlideCount: Number.isFinite(next) ? Math.max(5, Math.min(30, next)) : 5,
                        }));
                      }}
                      type="number"
                      min={5}
                      max={30}
                      placeholder="5 到 30"
                      helper="请输入 5 到 30。"
                      className={strongFieldClassName}
                    />

                    <div className="h-full min-w-0 space-y-1.5 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">选择风格</Label>
                      <Select value={setupDraft.style} onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, style: value as TrainingStyle }))}>
                        <SelectTrigger className={`h-10 w-full rounded-xl px-3 ${strongSelectTriggerClassName}`}>
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

                    <div className="h-full min-w-0 space-y-1.5 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <Label className="text-sm font-medium text-slate-700">有无备注</Label>
                      <Select
                        value={setupDraft.includeSpeakerNotes ? 'yes' : 'no'}
                        onValueChange={(value) => setSetupDraft((prev) => ({ ...prev, includeSpeakerNotes: value === 'yes' }))}
                      >
                        <SelectTrigger className={`h-10 w-full rounded-xl px-3 ${strongSelectTriggerClassName}`}>
                          <SelectValue>{notesSummary}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="yes">有</SelectItem>
                          <SelectItem value="no">无</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

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
                    <Button onClick={generatePpt} disabled={loadingPptGenerate || outline.slides.length === 0} className="bg-indigo-600 hover:bg-indigo-700">
                      {loadingPptGenerate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                      生成PPT
                    </Button>
                    {pptDownloadUrl && (
                      <Button asChild variant="outline">
                        <a href={pptDownloadUrl} target="_blank" rel="noreferrer">
                          <Download className="mr-2 h-4 w-4" />
                          下载PPT {pptFilename ? `(${pptFilename})` : ''}
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
