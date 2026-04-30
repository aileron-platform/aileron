import React, { useCallback } from 'react';
import { AtSign, BookOpen, FileText, Paperclip, Send, Slash, X, XCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import type { ChatUploadItem, ChatCodeReference } from './types';
import { getFileIcon } from '@/shared/utils/fileIconUtils';
import { formatFileSize } from '@/shared/utils/fileTypeUtils';
import { PermissionModeSelector, type PermissionMode } from './PermissionModeSelector';
import { normalizeAgentType } from '../../features/agent-settings/utils';

export interface ChatInputBarProps {
  value: string;
  isConnected: boolean;
  hasActiveRequests: boolean;
  isAborting?: boolean;
  attachments: ChatUploadItem[];
  codeReferences: ChatCodeReference[];
  cliType?: string;
  permissionMode?: PermissionMode;
  onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  onAbort: () => void;
  onOpenFilePicker: () => void;
  onOpenUploadDialog: () => void;
  onOpenSlashDialog: () => void;
  onOpenOpenSpecDialog: () => void;
  onRemoveAttachment: (id: string) => void;
  onRemoveCodeReference: (id: string) => void;
  onPermissionModeChange?: (mode: PermissionMode) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const ChatInputBar: React.FC<ChatInputBarProps> = ({
  value,
  isConnected,
  hasActiveRequests,
  isAborting = false,
  attachments,
  codeReferences,
  cliType,
  permissionMode = 'bypassPermissions',
  onChange,
  onSend,
  onAbort,
  onOpenFilePicker,
  onOpenUploadDialog,
  onOpenSlashDialog,
  onOpenOpenSpecDialog,
  onRemoveAttachment,
  onRemoveCodeReference,
  onPermissionModeChange,
  t,
}) => {
  const hasMessage = value.trim().length > 0;
  const hasAttachments = attachments.length > 0;
  const hasReferences = codeReferences.length > 0;
  const canSend = (hasMessage || hasAttachments || hasReferences) && isConnected && !isAborting;
  const showPermissionMode = normalizeAgentType(cliType) === 'claude';

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        onSend();
      }
    },
    [onSend]
  );

  return (
    <div className="border-t border-border bg-background/95">
      <div className="space-y-2">
        {!isConnected && (
          <div className="bg-amber-100 px-3 py-2 text-xs font-medium text-amber-800">
            {t('workspace.chat.input.disabledDisconnected')}
          </div>
        )}

        <div className="">
          {(codeReferences.length > 0 || attachments.length > 0) && (
            <div className="flex flex-wrap gap-1 border-b border-border/80 bg-muted/40 px-2 py-2">
              {codeReferences.map(reference => {
                const icon = getFileIcon(reference.fileName);
                const linesLabel = reference.startLine === reference.endLine
                  ? `:${reference.startLine}`
                  : `:${reference.startLine}-${reference.endLine}`;
                return (
                  <div
                    key={reference.id}
                    className="flex items-center gap-1 rounded-full border border-border/80 bg-background px-2 py-0.5 shadow-sm"
                    title={reference.filePath}
                  >
                    <span className="flex items-center justify-center">{icon}</span>
                    <span className="text-xs font-medium text-foreground">
                      {reference.fileName}
                      {linesLabel}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-4 w-4 text-muted-foreground hover:text-destructive"
                      type="button"
                      onClick={() => onRemoveCodeReference(reference.id)}
                      title={t('common.delete')}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                );
              })}

              {attachments.map(item => (
                <div
                  key={item.id}
                  className="flex items-center gap-1 rounded-full border border-border/80 bg-background px-2 py-0.5 shadow-sm"
                >
                  <FileText className="h-4 w-4 text-primary" />
                  <div className="flex flex-col">
                    <span className="text-xs font-medium text-foreground max-w-[160px] truncate">
                      {item.file.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {formatFileSize(item.file.size)}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-4 w-4 text-muted-foreground hover:text-destructive"
                    type="button"
                    onClick={() => onRemoveAttachment(item.id)}
                    title={t('common.delete')}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
          <Textarea
            value={value}
            onChange={onChange}
            onKeyDown={handleKeyDown}
            placeholder={t('workspace.chat.input.placeholder')}
            disabled={!isConnected || isAborting}
            className="min-h-[96px] border-none bg-transparent px-4 py-3 text-sm focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={onOpenUploadDialog}
                title={t('workspace.chat.input.attachments')}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Paperclip className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onOpenFilePicker}
                title={t('workspace.chat.input.files')}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <AtSign className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onOpenSlashDialog}
                title={t('workspace.chat.input.commands')}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Slash className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onOpenOpenSpecDialog}
                title={t('workspace.chat.input.openspec')}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <BookOpen className="h-4 w-4" />
              </button>
              {showPermissionMode && onPermissionModeChange && (
                <PermissionModeSelector
                  value={permissionMode}
                  onChange={onPermissionModeChange}
                  t={t}
                />
              )}
            </div>

            <div className="flex items-center gap-1.5">
              {hasActiveRequests && (
                <button
                  type="button"
                  onClick={onAbort}
                  title={t('workspace.chat.input.abort')}
                  disabled={isAborting}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:pointer-events-none"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={onSend}
                disabled={!canSend}
                title={t('workspace.chat.input.send')}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInputBar;
