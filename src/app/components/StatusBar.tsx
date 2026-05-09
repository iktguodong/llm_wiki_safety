import { useState, useRef, useEffect } from 'react';
import { ChevronDown, BookOpen, Cpu } from 'lucide-react';

interface StatusBarProps {
  currentKnowledgeBase: string;
  currentModel: string;
  onKnowledgeBaseChange: (kb: string) => void;
  onModelChange: (model: string) => void;
}

const knowledgeBases = ['港口安全知识库', '安全生产制度库', '消防法规库'];
const models = ['V3 Flash', 'V3 Pro', 'GPT-4o', 'Claude 3.5 Sonnet'];

function StatusDropdown({
  value,
  options,
  onChange,
  icon: Icon,
  label,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  icon: React.ElementType;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative flex items-center gap-1.5">
      <Icon className="w-3.5 h-3.5 text-slate-400" />
      <span className="text-slate-500">{label}:</span>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-slate-700 hover:text-slate-900 transition-colors"
      >
        <span>{value}</span>
        <ChevronDown className="w-3 h-3 text-slate-400" />
      </button>
      {open && (
        <div className="absolute bottom-full mb-1.5 left-0 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50 min-w-[160px]">
          {options.map((opt) => (
            <button
              key={opt}
              onClick={() => { onChange(opt); setOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-sm transition-colors hover:bg-slate-50 ${
                opt === value ? 'text-indigo-600' : 'text-slate-700'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function StatusBar({
  currentKnowledgeBase,
  currentModel,
  onKnowledgeBaseChange,
  onModelChange,
}: StatusBarProps) {
  return (
    <div className="h-9 bg-white border-t border-slate-200 px-5 flex items-center justify-between text-xs">
      <StatusDropdown
        value={currentKnowledgeBase}
        options={knowledgeBases}
        onChange={onKnowledgeBaseChange}
        icon={BookOpen}
        label="知识库"
      />
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
        <span className="text-slate-400">已就绪</span>
      </div>
      <StatusDropdown
        value={currentModel}
        options={models}
        onChange={onModelChange}
        icon={Cpu}
        label="模型"
      />
    </div>
  );
}
