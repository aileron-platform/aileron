import type {
  ChatAttachmentUploadOperation,
  ChatAttachmentUploadResponse,
} from './attachmentModel';

interface UploadChatAttachmentOptions {
  url: string;
  headers: Record<string, string> | Promise<Record<string, string>>;
  file: File;
  onProgress: (progress: number) => void;
}

export const uploadChatAttachment = ({
  url,
  headers,
  file,
  onProgress,
}: UploadChatAttachmentOptions): ChatAttachmentUploadOperation => {
  let xhr: XMLHttpRequest | null = null;
  let aborted = false;
  const formData = new FormData();
  formData.append('file', file);
  const logContext = {
    url,
    fileName: file.name,
    fileSize: file.size,
    fileType: file.type || 'application/octet-stream',
  };

  const promise = Promise.resolve(headers).then((resolvedHeaders) => new Promise<ChatAttachmentUploadResponse>((resolve, reject) => {
    if (aborted) {
      reject(new DOMException('Upload aborted', 'AbortError'));
      return;
    }
    xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) return;
      const progress = Math.round((event.loaded / event.total) * 100);
      console.debug('[ai-chat][attachment-upload:xhr:progress]', {
        ...logContext,
        loaded: event.loaded,
        total: event.total,
        progress,
      });
      onProgress(progress);
    };

    xhr.onload = () => {
      console.info('[ai-chat][attachment-upload:xhr:load]', {
        ...logContext,
        status: xhr.status,
        responseLength: xhr.responseText.length,
      });
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(`HTTP ${xhr.status}`));
        return;
      }
      try {
        resolve(JSON.parse(xhr.responseText) as ChatAttachmentUploadResponse);
      } catch (error) {
        reject(error);
      }
    };

    xhr.onerror = () => {
      console.error('[ai-chat][attachment-upload:xhr:error]', logContext);
      reject(new Error('upload_failed'));
    };
    xhr.onabort = () => {
      console.info('[ai-chat][attachment-upload:xhr:abort]', logContext);
      reject(new DOMException('Upload aborted', 'AbortError'));
    };

    xhr.open('POST', url);
    for (const [name, value] of Object.entries(resolvedHeaders)) {
      xhr.setRequestHeader(name, value);
    }
    console.info('[ai-chat][attachment-upload:xhr:send]', {
      ...logContext,
      headerNames: Object.keys(resolvedHeaders),
    });
    xhr.send(formData);
  }));

  return {
    promise,
    abort: () => {
      aborted = true;
      xhr?.abort();
    },
  };
};
