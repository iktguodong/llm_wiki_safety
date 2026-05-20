import { User } from 'lucide-react';
import type { ReactNode, RefObject } from 'react';
import { renderAssistantBubble, shouldExpandMessageLayout } from '../lib/chat-render';
import LogoMark from './LogoMark';
import { MessageActionBar } from './MessageActionBar';

export type ChatMessageListMessage = {
  role: 'user' | 'assistant';
  content: string;
  time: string;
};

type ChatMessageListProps = {
  messages: ChatMessageListMessage[];
  scrollRef: RefObject<HTMLDivElement | null>;
  endRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  className?: string;
  emptyState?: ReactNode;
  onCopy: (message: ChatMessageListMessage, index: number) => void;
  onExport: (message: ChatMessageListMessage, index: number, format: 'md' | 'txt' | 'docx') => void;
  onDelete: (index: number) => void;
  onRegenerateUser: (content: string) => void;
  onRegenerateAssistant: (index: number) => void;
  disableRegenerate: boolean;
};

export function ChatMessageList({
  messages,
  scrollRef,
  endRef,
  onScroll,
  className = 'flex-1 overflow-y-auto px-6 py-6 space-y-6',
  emptyState,
  onCopy,
  onExport,
  onDelete,
  onRegenerateUser,
  onRegenerateAssistant,
  disableRegenerate,
}: ChatMessageListProps) {
  return (
    <div ref={scrollRef} onScroll={onScroll} className={className}>
      {messages.length > 0 ? messages.map((msg, idx) => {
        const expanded = shouldExpandMessageLayout(msg.content);
        return (
          <div
            key={idx}
            className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{
                background: msg.role === 'assistant' ? '#EEF2FF' : '#4F46E5',
              }}
            >
              {msg.role === 'assistant' ? (
                <LogoMark
                  className="w-full h-full rounded-full overflow-hidden flex items-center justify-center"
                  imageClassName="w-full h-full object-contain scale-110"
                />
              ) : (
                <User className="w-4 h-4 text-white" />
              )}
            </div>
            <div
              className={`flex min-w-0 flex-col gap-1 ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              } ${expanded ? 'flex-1' : 'max-w-2xl'}`}
            >
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">
                  {msg.role === 'assistant' ? '安牛助手' : '我'}
                </span>
                <span className="text-xs text-slate-300">{msg.time}</span>
              </div>
              <div
                className={`px-4 py-3 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed w-full ${
                  expanded ? 'max-w-none' : 'max-w-full'
                } ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                }`}
              >
                {msg.role === 'assistant' ? renderAssistantBubble(msg.content) : msg.content}
              </div>
              <MessageActionBar
                onCopy={() => onCopy(msg, idx)}
                onExport={(format) => onExport(msg, idx, format)}
                onDelete={() => onDelete(idx)}
                onRegenerate={
                  msg.role === 'user'
                    ? () => onRegenerateUser(msg.content)
                    : (msg.role === 'assistant' && idx > 0 ? () => onRegenerateAssistant(idx) : undefined)
                }
                showRegenerate={msg.role === 'user' || (msg.role === 'assistant' && idx > 0)}
                disableRegenerate={disableRegenerate}
                disableDelete={disableRegenerate && idx === messages.length - 1 && msg.role === 'assistant' && !msg.content.trim()}
              />
            </div>
          </div>
        );
      }) : emptyState}
      <div ref={endRef} />
    </div>
  );
}
