import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { Command, FilePlus2, Paperclip, SendHorizontal, Square, X } from 'lucide-react';
import { promptInvocationApi } from '@/shared/api/promptInvocationApi';
import { PromptInvocationPickerDialog } from '@/shared/components/prompt-invocation-picker';
import { toPromptInvocationTool } from '@/shared/types/promptInvocations';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  WORKSPACE_FILE_REFERENCE_MIME,
  formatFileSize,
  getFileIcon,
  toWorkspaceFileReferencePath,
} from '@/shared/components/file-workbench';
import {
  CHAT_ATTACHMENT_ACCEPT,
  MAX_CHAT_ATTACHMENTS,
  validateChatAttachmentFile,
} from '../attachments/attachmentConstraints';
import type { ChatAttachmentUploadOperation } from '../attachments/attachmentModel';
import { getThreadApi } from '../api/threadApi';
import type { ChatAttachment } from '../attachments/attachmentModel';
import type { OutgoingMessage, Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { isRunning } from '../model/threadStatusModel';
import { AgentSettingsMenu, ModelSettingsMenu, ModeSettingsMenu } from './ThreadSettingsMenu';
import { normalizeThreadSettings, type ThreadSettings } from '../model/threadSettingsModel';
import {
  applyAiChatHandoff,
  type AiChatHandoffRequest,
} from '../model/chatHandoffModel';
import { SpeechToTextButton } from './SpeechToTextButton';
import {
  useAiChatIntegration,
  type AiChatCodeReference,
} from '../contexts/AiChatIntegrationContext';

interface ChatInputAreaProps {
  thread: Thread;
  capabilities: WorkspaceCapabilities;
  onSubmitDraft: (message: OutgoingMessage) => void;
  onPostMessage: (message: OutgoingMessage) => void;
  onStop?: () => void;
  isStopping?: boolean;
  onPatchDraft: (patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => void;
  onHeightChange?: (height: number) => void;
  onEnsureThread?: () => Promise<Thread | null>;
  draftHandoff?: AiChatHandoffRequest | null;
  onDraftHandoffApplied?: (handoffId: string) => void;
}

interface AttachmentPreviewItem {
  id: string;
  attachment: ChatAttachment;
}

const messageKey = (message: OutgoingMessage): string => JSON.stringify(message);

const previewItemsFromMessage = (message: OutgoingMessage | null | undefined): AttachmentPreviewItem[] =>
  (message?.attachments ?? []).map((attachment, index) => ({
    id: `${attachment.attachmentId}:${index}`,
    attachment: {
      id: `${attachment.attachmentId}:${index}`,
      kind: 'text-file',
      name: attachment.attachmentId,
      mimeType: 'application/octet-stream',
      size: 0,
      status: 'ready',
      progress: 100,
      attachmentId: attachment.attachmentId,
    },
  }));

const buildMessage = (text: string, attachments: ChatAttachment[] = []): OutgoingMessage => ({
  text,
  attachments: attachments
    .filter((attachment) => attachment.status === 'ready' && attachment.attachmentId)
    .map((attachment) => ({ attachmentId: attachment.attachmentId! })),
});

const toCodeReferencePath = (filePath: string): string => {
  const trimmedPath = filePath.trim();
  if (trimmedPath.startsWith('/workspace/')) {
    return `./${trimmedPath.slice('/workspace/'.length)}`;
  }
  if (trimmedPath === '/workspace') {
    return './';
  }
  return toWorkspaceFileReferencePath(trimmedPath);
};

const buildMessageWithCodeReference = (
  text: string,
  attachments: ChatAttachment[],
  codeReference: AiChatCodeReference | null,
): OutgoingMessage => {
  if (!codeReference) {
    return buildMessage(text, attachments);
  }

  const lineRange = codeReference.startLine === codeReference.endLine
    ? `${codeReference.startLine}`
    : `${codeReference.startLine}-${codeReference.endLine}`;
  const referenceText = `File:${toCodeReferencePath(codeReference.filePath)}:${lineRange}`;
  const trimmedText = text.trim();
  return buildMessage(
    trimmedText ? `${referenceText}\n${trimmedText}` : referenceText,
    attachments,
  );
};

const toolbarIconButtonClass =
  'inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50';

export const ChatInputArea = ({
  thread,
  capabilities,
  onSubmitDraft,
  onPostMessage,
  onStop,
  isStopping = false,
  onPatchDraft,
  onHeightChange,
  onEnsureThread,
  draftHandoff,
  onDraftHandoffApplied,
}: ChatInputAreaProps) => {
  const { t } = useI18n();
  const {
    clearCodeReference,
    codeReference,
    fileChooser: FileChooserDialog,
    runtimeBaseUrl,
    workspaceId: integrationWorkspaceId,
  } = useAiChatIntegration();
  const [text, setText] = useState(thread.draftMessage?.text ?? '');
  const [attachments, setAttachments] = useState<AttachmentPreviewItem[]>(() =>
    previewItemsFromMessage(thread.draftMessage),
  );
  const [isFocused, setIsFocused] = useState(false);
  const [textareaHeight, setTextareaHeight] = useState(40);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const activeThreadIdRef = useRef(thread.id);
  const selectedAgenticToolRef = useRef(thread.agenticTool);
  const localDraftValuesRef = useRef(new Set<string>());
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentsRef = useRef<AttachmentPreviewItem[]>([]);
  const appliedDraftHandoffIdsRef = useRef(new Set<string>());
  const uploadOperationsRef = useRef(new Map<string, ChatAttachmentUploadOperation>());
  const [fileChooserOpen, setFileChooserOpen] = useState(false);
  const [promptInvocationOpen, setPromptInvocationOpen] = useState(false);
  const [isVoiceBusy, setIsVoiceBusy] = useState(false);
  const isVoiceBusyRef = useRef(false);
  const threadApi = useMemo(
    () => (runtimeBaseUrl
      ? getThreadApi(runtimeBaseUrl)
      : null),
    [runtimeBaseUrl],
  );
  isVoiceBusyRef.current = isVoiceBusy;

  const rawSettings = useMemo<ThreadSettings>(
    () => ({
      agenticTool: thread.agenticTool,
      model: thread.model,
      claudeMode: thread.claudeMode,
    }),
    [thread.agenticTool, thread.claudeMode, thread.model],
  );
  const settings = useMemo(
    () => normalizeThreadSettings(capabilities, rawSettings),
    [capabilities, rawSettings],
  );
  const hasContent = text.trim().length > 0 || attachments.length > 0 || Boolean(codeReference);
  const isExpanded = text.includes('\n');
  const isActive = isFocused || hasContent;
  const selectionPatch = (nextSettings: ThreadSettings): Partial<ThreadSettings> => {
    if (thread.status === 'draft') {
      return nextSettings;
    }
    return {
      model: nextSettings.model,
      claudeMode: nextSettings.claudeMode,
    };
  };

  const resizeTextarea = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    const compactHeight = 40;
    const expandedMinHeight = 56;
    const measuredHeight = isExpanded ? textarea.scrollHeight : compactHeight;
    const nextHeight = Math.min(
      Math.max(measuredHeight, isExpanded ? expandedMinHeight : compactHeight),
      208,
    );
    textarea.style.height = `${nextHeight}px`;
    setTextareaHeight(nextHeight);
  }, [isExpanded]);

  useEffect(() => {
    resizeTextarea();
  }, [resizeTextarea, text]);

  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => {
    selectedAgenticToolRef.current = thread.agenticTool;
  }, [thread.agenticTool]);

  useEffect(() => () => {
    for (const operation of uploadOperationsRef.current.values()) {
      operation.abort();
    }
    for (const item of attachmentsRef.current) {
      if (item.attachment.previewUrl) {
        URL.revokeObjectURL(item.attachment.previewUrl);
      }
    }
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !onHeightChange) return;

    const reportHeight = () => onHeightChange(root.getBoundingClientRect().height);
    reportHeight();

    const observer = new ResizeObserver(reportHeight);
    observer.observe(root);
    return () => observer.disconnect();
  }, [onHeightChange]);

  useEffect(() => {
    const incomingMessage = thread.draftMessage ?? buildMessage('');
    const incomingText = incomingMessage.text;
    const incomingKey = messageKey(incomingMessage);
    if (activeThreadIdRef.current !== thread.id) {
      const previousThreadId = activeThreadIdRef.current;
      activeThreadIdRef.current = thread.id;
      localDraftValuesRef.current.clear();
      const isMaterializingNewTaskDraft = previousThreadId === 'new-task-draft';
      setText((current) => (isMaterializingNewTaskDraft && !incomingText ? current : incomingText));
      setAttachments((current) => (
        isMaterializingNewTaskDraft && incomingMessage.attachments.length === 0
          ? current
          : previewItemsFromMessage(incomingMessage)
      ));
      return;
    }
    if (localDraftValuesRef.current.has(incomingKey)) {
      localDraftValuesRef.current.delete(incomingKey);
      return;
    }
    setText(incomingText);
    setAttachments(previewItemsFromMessage(incomingMessage));
  }, [thread.draftMessage, thread.id]);

  const patchDraftText = useCallback(
    (nextText: string, nextAttachments = attachments) => {
      if (thread.status === 'draft') {
        const message = buildMessage(nextText, nextAttachments.map((item) => item.attachment));
        localDraftValuesRef.current.add(messageKey(message));
        onPatchDraft({ draftMessage: message.text.trim() || message.attachments.length > 0 ? message : null });
      }
    },
    [attachments, onPatchDraft, thread.status],
  );

  const submitText = useCallback(
    (value: string) => {
      if (isVoiceBusyRef.current) {
        return;
      }
      if (attachments.some((item) => item.attachment.status !== 'ready')) {
        return;
      }
      const message = buildMessageWithCodeReference(
        value,
        attachments.map((item) => item.attachment),
        codeReference,
      );
      if (!message.text.trim() && message.attachments.length === 0) {
        return;
      }

      if (thread.status === 'draft') {
        onSubmitDraft(message);
        onPatchDraft({ draftMessage: null });
      } else {
        onPostMessage(message);
      }
      setText('');
      setAttachments([]);
      clearCodeReference?.();
    },
    [
      attachments,
      clearCodeReference,
      codeReference,
      onPatchDraft,
      onPostMessage,
      onSubmitDraft,
      thread.status,
    ],
  );

  useEffect(() => {
    if (!draftHandoff || draftHandoff.delivery !== 'draft') return;
    if (appliedDraftHandoffIdsRef.current.has(draftHandoff.id)) return;
    appliedDraftHandoffIdsRef.current.add(draftHandoff.id);
    setText((current) => {
      const next = applyAiChatHandoff(current, draftHandoff, thread.agenticTool);
      patchDraftText(next);
      return next;
    });
    onDraftHandoffApplied?.(draftHandoff.id);
  }, [draftHandoff, onDraftHandoffApplied, patchDraftText, thread.agenticTool]);

  const handleVoiceTranscript = useCallback((transcript: string) => {
    setText((current) => {
      const next = current.trim() ? `${current}\n${transcript}` : transcript;
      patchDraftText(next);
      return next;
    });
  }, [patchDraftText]);

  const loadPromptInvocationCatalog = useCallback(async () => {
    const workspaceId = integrationWorkspaceId ?? thread.workspaceId;
    if (!runtimeBaseUrl || !workspaceId) {
      throw new Error('Workspace Runtime is unavailable');
    }

    return promptInvocationApi.list(
      runtimeBaseUrl,
      workspaceId,
      toPromptInvocationTool(selectedAgenticToolRef.current),
    );
  }, [integrationWorkspaceId, runtimeBaseUrl, thread.workspaceId]);

  const openPromptInvocationPicker = useCallback(() => {
    setPromptInvocationOpen(true);
  }, []);

  const handleTextChange = (next: string) => {
    setText(next);
    patchDraftText(next);
    if (!text.startsWith('/') && next.startsWith('/')) {
      openPromptInvocationPicker();
    }
  };

  const handleTextKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key !== 'Enter' ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    ) {
      return;
    }

    event.preventDefault();
    submitText(text);
  };

  const handleFileReference = (path: string) => {
    const referencePath = toWorkspaceFileReferencePath(path);
    if (!referencePath) {
      return;
    }
    const next = text ? `${text}\n@${referencePath}` : `@${referencePath}`;
    setText(next);
    patchDraftText(next);
    setFileChooserOpen(false);
  };

  const getDraggedWorkspaceFileReference = (event: DragEvent<HTMLElement>) => {
    if (!event.dataTransfer.types.includes(WORKSPACE_FILE_REFERENCE_MIME)) {
      return null;
    }
    return event.dataTransfer.getData(WORKSPACE_FILE_REFERENCE_MIME);
  };

  const uploadFiles = useCallback(async (files: File[] | FileList) => {
    const incomingFiles = Array.from(files);
    console.info('[ai-chat][attachment-upload:requested]', {
      threadId: thread.id,
      threadStatus: thread.status,
      hasThreadApi: Boolean(threadApi),
      hasEnsureThread: Boolean(onEnsureThread),
      incomingFileCount: incomingFiles.length,
      currentAttachmentCount: attachments.length,
      files: incomingFiles.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type || 'application/octet-stream',
      })),
    });
    if (!threadApi) {
      console.warn('[ai-chat][attachment-upload:blocked:no-thread-api]', {
        threadId: thread.id,
        threadStatus: thread.status,
      });
      return;
    }
    let uploadThread: Thread | null = thread;
    if (onEnsureThread) {
      console.info('[ai-chat][attachment-upload:ensure-thread:start]', {
        threadId: thread.id,
        threadStatus: thread.status,
      });
      try {
        uploadThread = await onEnsureThread();
      } catch (error) {
        console.error('[ai-chat][attachment-upload:ensure-thread:error]', {
          threadId: thread.id,
          threadStatus: thread.status,
          error,
        });
        return;
      }
      console.info('[ai-chat][attachment-upload:ensure-thread:done]', {
        originalThreadId: thread.id,
        originalThreadStatus: thread.status,
        uploadThreadId: uploadThread?.id,
        uploadThreadStatus: uploadThread?.status,
      });
    }
    if (!uploadThread) {
      console.warn('[ai-chat][attachment-upload:blocked:no-upload-thread]', {
        threadId: thread.id,
        threadStatus: thread.status,
      });
      return;
    }
    const availableSlots = Math.max(0, MAX_CHAT_ATTACHMENTS - attachments.length);
    const acceptedFiles = incomingFiles.slice(0, availableSlots);
    if (acceptedFiles.length < incomingFiles.length) {
      console.warn('[ai-chat][attachment-upload:slot-limit]', {
        threadId: uploadThread.id,
        availableSlots,
        incomingFileCount: incomingFiles.length,
        acceptedFileCount: acceptedFiles.length,
      });
    }

    for (const file of acceptedFiles) {
      const validation = validateChatAttachmentFile(file);
      if (!validation.ok) {
        console.warn('[ai-chat][attachment-upload:validation-rejected]', {
          threadId: uploadThread.id,
          fileName: file.name,
          fileSize: file.size,
          fileType: file.type || 'application/octet-stream',
          errorKey: validation.errorKey,
        });
        continue;
      }
      const localId = crypto.randomUUID();
      const previewUrl = validation.kind === 'image' ? URL.createObjectURL(file) : undefined;
      const item: AttachmentPreviewItem = {
        id: localId,
        attachment: {
          id: localId,
          kind: validation.kind,
          name: file.name,
          mimeType: file.type || 'application/octet-stream',
          size: file.size,
          status: 'uploading',
          progress: 0,
          previewUrl,
        },
      };

      setAttachments((current) => [...current, item]);
      console.info('[ai-chat][attachment-upload:item:start]', {
        threadId: uploadThread.id,
        localId,
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type || 'application/octet-stream',
        kind: validation.kind,
      });
      const operation = threadApi.uploadAttachment(uploadThread.id, file, (progress) => {
        setAttachments((current) => current.map((currentItem) => (
          currentItem.id === localId
            ? {
                ...currentItem,
                attachment: { ...currentItem.attachment, progress },
              }
            : currentItem
        )));
      });
      uploadOperationsRef.current.set(localId, operation);
      void operation.promise
        .then((uploaded) => {
          console.info('[ai-chat][attachment-upload:item:success]', {
            threadId: uploadThread.id,
            localId,
            attachmentId: uploaded.attachmentId,
            kind: uploaded.kind,
            name: uploaded.name,
            size: uploaded.size,
            mimeType: uploaded.mimeType,
          });
          uploadOperationsRef.current.delete(localId);
          setAttachments((current) => {
            const next = current.map((currentItem) => (
              currentItem.id === localId
                ? {
                    ...currentItem,
                    attachment: {
                      ...currentItem.attachment,
                      kind: uploaded.kind,
                      name: uploaded.name,
                      mimeType: uploaded.mimeType,
                      size: uploaded.size,
                      status: 'ready' as const,
                      progress: 100,
                      attachmentId: uploaded.attachmentId,
                    },
                  }
                : currentItem
            ));
            queueMicrotask(() => patchDraftText(text, next));
            return next;
          });
        })
        .catch((error: unknown) => {
          uploadOperationsRef.current.delete(localId);
          if (error instanceof DOMException && error.name === 'AbortError') {
            console.info('[ai-chat][attachment-upload:item:aborted]', {
              threadId: uploadThread.id,
              localId,
              fileName: file.name,
            });
            return;
          }
          console.error('[ai-chat][attachment-upload:item:error]', {
            threadId: uploadThread.id,
            localId,
            fileName: file.name,
            error,
          });
          setAttachments((current) => current.map((currentItem) => (
            currentItem.id === localId
              ? {
                  ...currentItem,
                  attachment: {
                    ...currentItem.attachment,
                    status: 'failed' as const,
                    errorKey: 'aiChat.input.attachmentUploadFailed',
                  },
                }
              : currentItem
          )));
        });
    }
  }, [attachments.length, onEnsureThread, patchDraftText, text, thread, threadApi]);

  const handleRemoveAttachment = (attachmentId: string) => {
    setAttachments((current) => {
      const removed = current.find((item) => item.id === attachmentId);
      const operation = uploadOperationsRef.current.get(attachmentId);
      if (operation) {
        operation.abort();
        uploadOperationsRef.current.delete(attachmentId);
      } else if (removed?.attachment.status === 'ready' && removed.attachment.attachmentId) {
        void threadApi?.deleteAttachment(thread.id, removed.attachment.attachmentId);
      }
      if (removed?.attachment.previewUrl) {
        URL.revokeObjectURL(removed.attachment.previewUrl);
      }
      const next = current.filter((item) => item.id !== attachmentId);
      queueMicrotask(() => patchDraftText(text, next));
      return next;
    });
  };

  return (
    <div
      ref={rootRef}
      className="pointer-events-none bg-gradient-to-t from-background/70 to-background/0 px-3 pb-3 pt-2"
    >
      <div
        data-expanded={isExpanded}
        data-active={isActive}
        onPaste={(event) => {
          const files = Array.from(event.clipboardData.files);
          if (files.length === 0) return;
          event.preventDefault();
          uploadFiles(files);
        }}
        onDragOver={(event) => {
          if (getDraggedWorkspaceFileReference(event)) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
            return;
          }
          if (event.dataTransfer.types.includes('Files')) {
            event.preventDefault();
          }
        }}
        onDrop={(event) => {
          const workspaceFileReference = getDraggedWorkspaceFileReference(event);
          if (workspaceFileReference) {
            event.preventDefault();
            handleFileReference(workspaceFileReference);
            return;
          }
          const files = Array.from(event.dataTransfer.files);
          if (files.length === 0) return;
          event.preventDefault();
          uploadFiles(files);
        }}
        className="pointer-events-auto mx-auto flex w-full max-w-3xl flex-col rounded-[28px] bg-background px-2 py-1.5 shadow-[0_0_0_1px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.04),0_10px_60px_rgba(0,0,0,0.06)] transition-[padding,box-shadow] duration-200 ease-out data-[active=true]:shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_3px_12px_rgba(0,0,0,0.06),0_14px_72px_rgba(0,0,0,0.08)] data-[expanded=true]:py-2"
      >
        {codeReference && (
          <div className="flex min-w-0 px-2 pt-1">
            <div
              className="flex max-w-full items-center gap-2 rounded-md border border-border/70 bg-muted/50 px-2 py-1 text-xs text-foreground"
              title={codeReference.filePath}
            >
              <span className="shrink-0" aria-hidden="true">
                {getFileIcon(codeReference.fileName)}
              </span>
              <span className="max-w-44 truncate font-medium">
                {codeReference.fileName}
              </span>
              <span className="shrink-0 text-muted-foreground">
                {codeReference.startLine === codeReference.endLine
                  ? t('aiChat.input.codeReferenceLine', { line: codeReference.startLine })
                  : t('aiChat.input.codeReferenceRange', {
                    startLine: codeReference.startLine,
                    endLine: codeReference.endLine,
                  })}
              </span>
              <button
                type="button"
                aria-label={`${t('aiChat.input.removeCodeReference')} ${codeReference.fileName}`}
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                onClick={() => clearCodeReference?.()}
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
        <div className="min-w-0 px-2 transition-[min-height] duration-200 ease-out">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(event) => handleTextChange(event.target.value)}
            onKeyDown={handleTextKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={t(isRunning(thread.status) ? 'aiChat.input.queuedPlaceholder' : 'aiChat.input.placeholder')}
            style={{ height: textareaHeight }}
            className="max-h-52 min-h-10 w-full resize-none overflow-y-auto border-0 bg-transparent px-2 py-2 text-sm outline-none transition-[height] duration-200 ease-out placeholder:text-muted-foreground/75"
          />
        </div>
        {attachments.length > 0 && (
          <div className="flex min-w-0 flex-wrap gap-1.5 px-2 pb-1">
            {attachments.map((item) => (
              <div
                key={item.id}
                className="flex max-w-full items-center gap-2 rounded-md border border-border/70 bg-muted/50 px-2 py-1 text-xs text-foreground"
              >
                {item.attachment.kind === 'image' && item.attachment.previewUrl ? (
                  <img
                    src={item.attachment.previewUrl}
                    alt=""
                    className="h-7 w-7 shrink-0 rounded object-cover"
                  />
                ) : (
                  <span className="shrink-0" aria-hidden="true">
                    {getFileIcon(item.attachment.name)}
                  </span>
                )}
                <span className="max-w-44 truncate" title={item.attachment.name}>
                  {item.attachment.name}
                </span>
                <span className="shrink-0 text-muted-foreground">{formatFileSize(item.attachment.size)}</span>
                <span className="shrink-0 text-muted-foreground">
                  {item.attachment.status === 'uploading'
                    ? t('aiChat.input.attachmentUploading', { progress: item.attachment.progress })
                    : item.attachment.status === 'ready'
                      ? t('aiChat.input.attachmentReady')
                      : t(item.attachment.errorKey ?? 'aiChat.input.attachmentUploadFailed')}
                </span>
                <button
                  type="button"
                  aria-label={`${t('aiChat.input.removeAttachment')} ${item.attachment.name}`}
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                  onClick={() => handleRemoveAttachment(item.id)}
                >
                  <X className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div data-testid="ai-chat-input-toolbar" className="flex min-w-0 flex-wrap items-center justify-between gap-2 px-1">
          <div className="flex min-w-0 items-center gap-2">
            <AgentSettingsMenu
              capabilities={capabilities}
              settings={settings}
              locked={thread.status !== 'draft'}
              onChange={(nextSettings) => {
                selectedAgenticToolRef.current = nextSettings.agenticTool;
                onPatchDraft(nextSettings);
              }}
            />
            <ModelSettingsMenu
              capabilities={capabilities}
              settings={settings}
              locked={false}
              onChange={(nextSettings) => onPatchDraft(selectionPatch(nextSettings))}
            />
            <ModeSettingsMenu
              capabilities={capabilities}
              settings={settings}
              locked={false}
              onChange={(nextSettings) => onPatchDraft(selectionPatch(nextSettings))}
            />
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <button
              type="button"
              aria-label={t('aiChat.input.fileReference')}
              className={toolbarIconButtonClass}
              onClick={() => setFileChooserOpen(true)}
            >
              <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label={t('aiChat.input.uploadFile')}
              className={toolbarIconButtonClass}
              onClick={() => {
                console.info('[ai-chat][attachment-upload:button-click]', {
                  threadId: thread.id,
                  threadStatus: thread.status,
                  hasThreadApi: Boolean(threadApi),
                  hasFileInput: Boolean(fileInputRef.current),
                });
                fileInputRef.current?.click();
              }}
            >
              <Paperclip className="h-4 w-4" aria-hidden="true" />
            </button>
            <input
              ref={fileInputRef}
              id="ai-chat-file-input"
              name="ai-chat-file-input"
              data-testid="ai-chat-file-input"
              type="file"
              multiple
              accept={CHAT_ATTACHMENT_ACCEPT}
              className="sr-only"
              onChange={(event) => {
                console.info('[ai-chat][attachment-upload:input-change]', {
                  threadId: thread.id,
                  threadStatus: thread.status,
                  fileCount: event.target.files?.length ?? 0,
                });
                if (event.target.files && event.target.files.length > 0) {
                  uploadFiles(event.target.files);
                  event.target.value = '';
                }
              }}
            />
            <button
              type="button"
              aria-label={t('aiChat.input.slashCommand')}
              className={toolbarIconButtonClass}
              onClick={openPromptInvocationPicker}
            >
              <Command className="h-4 w-4" aria-hidden="true" />
            </button>
            <SpeechToTextButton
              className={toolbarIconButtonClass}
              disabled={!threadApi}
              transcribeAudio={threadApi?.transcribeAudio}
              onBusyChange={setIsVoiceBusy}
              onTranscript={handleVoiceTranscript}
            />
            <button
              type="button"
              aria-label={t(isRunning(thread.status) ? 'aiChat.workbench.stop' : 'aiChat.input.send')}
              className={
                isRunning(thread.status)
                  ? 'inline-flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50'
                  : 'inline-flex h-8 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50'
              }
              disabled={
                isRunning(thread.status)
                  ? isStopping
                  : (isVoiceBusy
                    || (!text.trim() && attachments.length === 0 && !codeReference)
                    || attachments.some((item) => item.attachment.status !== 'ready'))
              }
              onClick={() => {
                if (isRunning(thread.status)) {
                  onStop?.();
                  return;
                }
                submitText(text);
              }}
            >
              {isRunning(thread.status) ? (
                <Square className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <>
                  <SendHorizontal className="h-4 w-4" aria-hidden="true" />
                  <span>{t('aiChat.input.send')}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {FileChooserDialog ? (
        <FileChooserDialog
          open={fileChooserOpen}
          onOpenChange={setFileChooserOpen}
          onFileSelect={handleFileReference}
          t={t}
        />
      ) : null}
      <PromptInvocationPickerDialog
        open={promptInvocationOpen}
        onOpenChange={setPromptInvocationOpen}
        catalogKey={`${integrationWorkspaceId ?? thread.workspaceId}:${selectedAgenticToolRef.current}`}
        loadCatalog={loadPromptInvocationCatalog}
        onSelect={(item) => {
          setText(item.invocation);
          patchDraftText(item.invocation);
        }}
      />
    </div>
  );
};
