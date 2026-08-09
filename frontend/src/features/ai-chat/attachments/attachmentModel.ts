export type ChatAttachmentKind = 'image' | 'pdf' | 'text-file';

export interface ChatAttachmentReference {
  attachmentId: string;
}

export type ChatAttachmentStatus = 'uploading' | 'ready' | 'failed';

export interface ChatAttachment {
  id: string;
  kind: ChatAttachmentKind;
  name: string;
  mimeType: string;
  size: number;
  status: ChatAttachmentStatus;
  progress: number;
  attachmentId?: string;
  previewUrl?: string;
  errorKey?: string;
}

export interface ChatAttachmentUploadResponse {
  attachmentId: string;
  kind: ChatAttachmentKind;
  name: string;
  mimeType: string;
  size: number;
}

export interface ChatAttachmentUploadOperation {
  promise: Promise<ChatAttachmentUploadResponse>;
  abort(): void;
}
