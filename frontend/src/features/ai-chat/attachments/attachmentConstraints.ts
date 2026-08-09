import type { ChatAttachmentKind } from './attachmentModel';

export const MAX_CHAT_ATTACHMENTS = 10;

export const CHAT_ATTACHMENT_ACCEPT =
  'image/*,application/pdf,text/*,application/json,.txt,.csv,.md,.markdown';

const CHAT_ATTACHMENT_SIZE_LIMITS: Record<ChatAttachmentKind, number> = {
  image: 10 * 1024 * 1024,
  pdf: 25 * 1024 * 1024,
  'text-file': 10 * 1024 * 1024,
};

type ChatAttachmentValidationResult =
  | { ok: true; kind: ChatAttachmentKind }
  | { ok: false; reason: 'unsupported-type' | 'too-large'; maxBytes?: number };

const classifyChatAttachmentFile = (file: File): ChatAttachmentKind | null => {
  const mimeType = file.type;
  const lowerName = file.name.toLowerCase();
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType === 'application/pdf' || lowerName.endsWith('.pdf')) return 'pdf';
  if (
    mimeType.startsWith('text/')
    || mimeType === 'application/json'
    || lowerName.endsWith('.txt')
    || lowerName.endsWith('.csv')
    || lowerName.endsWith('.md')
    || lowerName.endsWith('.markdown')
    || lowerName.endsWith('.json')
  ) {
    return 'text-file';
  }
  return null;
};

export const validateChatAttachmentFile = (file: File): ChatAttachmentValidationResult => {
  const kind = classifyChatAttachmentFile(file);
  if (!kind) return { ok: false, reason: 'unsupported-type' };
  const maxBytes = CHAT_ATTACHMENT_SIZE_LIMITS[kind];
  if (file.size > maxBytes) {
    return { ok: false, reason: 'too-large', maxBytes };
  }
  return { ok: true, kind };
};
