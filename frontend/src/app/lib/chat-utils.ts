import { normalizeAssistantText } from './chat-render';

type ChatLikeMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export function buildDocxExportName(role: ChatLikeMessage['role'], text: string) {
  const fallback = role === 'assistant' ? '安牛助手回答' : '我的提问';
  const normalized = normalizeAssistantText(text).replace(/\s+/g, ' ').trim();
  const lead = normalized.split(/[。！？!?；;\n]/)[0]?.trim() || normalized;
  const cleaned = lead.replace(/[\\/:*?"<>|\r\n\t]+/g, '_').replace(/\s+/g, ' ').trim();
  return `${(cleaned || fallback).slice(0, 40)}.docx`;
}

export function dropTrailingAssistantMessage<T extends ChatLikeMessage>(messages: T[]) {
  const last = messages[messages.length - 1];
  if (last?.role !== 'assistant') return messages;
  return messages.slice(0, -1);
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
