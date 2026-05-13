import { useEffect, useRef, useState } from 'react';

import { Check, Copy, Download, FileText, RefreshCw, Trash2 } from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

type MessageActionBarProps = {
  showRegenerate?: boolean;
  disableRegenerate?: boolean;
  disableDelete?: boolean;
  disableExport?: boolean;
  onCopy: () => void | Promise<void>;
  onExport: (format: 'md' | 'txt') => void;
  onDelete: () => void;
  onRegenerate?: () => void;
};

export function MessageActionBar({
  showRegenerate = false,
  disableRegenerate = false,
  disableDelete = false,
  disableExport = false,
  onCopy,
  onExport,
  onDelete,
  onRegenerate,
}: MessageActionBarProps) {
  const [copied, setCopied] = useState(false);
  const copiedTimerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (copiedTimerRef.current !== null) {
      window.clearTimeout(copiedTimerRef.current);
    }
  }, []);

  const handleCopy = async () => {
    try {
      await onCopy();
      setCopied(true);
      if (copiedTimerRef.current !== null) {
        window.clearTimeout(copiedTimerRef.current);
      }
      copiedTimerRef.current = window.setTimeout(() => {
        setCopied(false);
        copiedTimerRef.current = null;
      }, 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex items-center gap-1 text-slate-400">
      <button
        type="button"
        onClick={handleCopy}
        title={copied ? '已复制' : '复制'}
        className={`w-7 h-7 inline-flex items-center justify-center rounded-md transition-colors ${
          copied
            ? 'bg-emerald-50 text-emerald-600'
            : 'hover:bg-slate-100 hover:text-slate-600'
        }`}
      >
        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      </button>

      {showRegenerate && onRegenerate ? (
        <button
          type="button"
          onClick={onRegenerate}
          title="重新生成"
          disabled={disableRegenerate}
          className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      ) : null}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            title={disableExport ? '当前内容不可导出' : '导出'}
            disabled={disableExport}
            className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-slate-100 hover:text-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" sideOffset={6} className="w-44 p-1">
          <DropdownMenuItem
            onSelect={() => onExport('md')}
            disabled={disableExport}
            className="gap-2"
          >
            <FileText className="w-3.5 h-3.5" />
            Markdown (.md)
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => onExport('txt')}
            disabled={disableExport}
            className="gap-2"
          >
            <Download className="w-3.5 h-3.5" />
            纯文本 (.txt)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <button
        type="button"
        onClick={onDelete}
        title={disableDelete ? '生成中暂不能删除' : '删除消息'}
        disabled={disableDelete}
        className="w-7 h-7 inline-flex items-center justify-center rounded-md hover:bg-red-50 hover:text-red-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
