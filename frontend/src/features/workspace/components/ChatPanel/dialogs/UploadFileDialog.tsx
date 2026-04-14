import React, { useCallback, useRef, useState } from 'react';
import { CloudUpload, FileText, X } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import type { ChatUploadItem } from '../../types';
import { formatFileSize } from '@/features/workspace/features/file-management/utils/fileTypeUtils';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('UploadFileDialog');

interface UploadFileDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  uploads: ChatUploadItem[];
  onSelectFiles: (files: File[] | FileList) => void;
  onRemoveUpload: (uploadId: string) => void;
  onClearUploads: () => void;
  onConfirm: () => Promise<void> | void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const UploadFileDialog: React.FC<UploadFileDialogProps> = ({
  open,
  onOpenChange,
  uploads,
  onSelectFiles,
  onRemoveUpload,
  onClearUploads,
  onConfirm,
  t,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files && event.target.files.length > 0) {
        onSelectFiles(event.target.files);
        event.target.value = '';
      }
    },
    [onSelectFiles]
  );

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
        onSelectFiles(event.dataTransfer.files);
        event.dataTransfer.clearData();
      }
    },
    [onSelectFiles]
  );

  const renderStatus = useCallback(
    (status: ChatUploadItem['status']) => {
      switch (status) {
        case 'uploading':
          return t('workspace.chat.dialogs.upload.status.processing');
        case 'error':
          return t('workspace.chat.dialogs.upload.status.error');
        case 'ready':
        default:
          return t('workspace.chat.dialogs.upload.status.ready');
      }
    },
    [t]
  );

  const handleConfirm = useCallback(async () => {
    if (uploads.length === 0) {
      onOpenChange(false);
      return;
    }
    try {
      setIsSubmitting(true);
      await onConfirm();
    } catch (error) {
      logger.error('上傳檔案失敗', { error });
    } finally {
      setIsSubmitting(false);
    }
  }, [onConfirm, onOpenChange, uploads.length]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('workspace.chat.dialogs.upload.title')}</DialogTitle>
          <DialogDescription>{t('workspace.chat.dialogs.upload.description')}</DialogDescription>
        </DialogHeader>

        <div
          className={`flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center transition-colors ${
            isDragging ? 'border-primary bg-primary/10' : 'border-border bg-muted/30'
          } ${isSubmitting ? 'pointer-events-none opacity-70' : ''}`}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
          onClick={handleBrowseClick}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              handleBrowseClick();
            }
          }}
        >
          <CloudUpload className="h-8 w-8 text-primary" />
          <div>
            <p className="text-sm font-medium text-foreground">
              {t('workspace.chat.dialogs.upload.dropzoneTitle')}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('workspace.chat.dialogs.upload.dropzoneSubtitle')}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleBrowseClick();
            }}
            disabled={isSubmitting}
          >
            {t('workspace.chat.dialogs.upload.browse')}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
            disabled={isSubmitting}
          />
        </div>

        <div className="mt-4 space-y-2">
          {uploads.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-4 py-4 text-center text-xs text-muted-foreground">
              {t('workspace.chat.dialogs.upload.dropzoneSubtitle')}
            </div>
          ) : (
            uploads.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-md border border-border/60 bg-muted/40 px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground" title={item.file.name}>
                      {item.file.name}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(item.file.size)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-muted-foreground">
                    {renderStatus(item.status)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    type="button"
                    onClick={() => onRemoveUpload(item.id)}
                    title={t('common.delete')}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          {uploads.length > 0 && (
            <Button variant="ghost" type="button" onClick={onClearUploads} disabled={isSubmitting}>
              {t('common.reset')}
            </Button>
          )}
          <Button variant="ghost" type="button" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            {t('common.cancel')}
          </Button>
          <Button type="button" onClick={handleConfirm} disabled={uploads.length === 0 || isSubmitting}>
            {t('workspace.chat.dialogs.upload.confirm')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default UploadFileDialog;
