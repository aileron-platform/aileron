/**
 *
 */

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { AlertTriangle, File, Folder, Trash2, Edit3, Loader2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { isFileAlreadyExistsError } from '../conflicts/fileConflictModel';
import type { FileOperationDialogResult } from '../hooks/useFileOperationsWithDialog';



export interface FileCreateDialogProps {
  open: boolean;
  type: 'file' | 'folder';
  onClose: () => void;
  onConfirm: (name: string) => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  defaultValue?: string;
  hint?: React.ReactNode;
}

export const FileCreateDialog: React.FC<FileCreateDialogProps> = ({
  open,
  type,
  onClose,
  onConfirm,
  defaultValue = '',
  hint,
}) => {
  const { t } = useI18n();
  const [name, setName] = useState(defaultValue);
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateName = (value: string): boolean => {
    const trimmedValue = value.trim();


    if (!trimmedValue) {
      setError(t('common.fileOperations.validation.nameRequired'));
      return false;
    }


    if (trimmedValue.includes('/') || trimmedValue.includes('\\')) {
      setError(t('common.fileOperations.validation.nameWithPath'));
      return false;
    }


    const invalidChars = /[<>:"|?*\x00-\x1f]/;
    if (invalidChars.test(trimmedValue)) {
      setError(t('common.fileOperations.validation.nameWithInvalidChars'));
      return false;
    }


    const reservedNames = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;
    if (reservedNames.test(trimmedValue)) {
      setError(t('common.fileOperations.validation.nameReserved'));
      return false;
    }

    setError('');
    return true;
  };

  const handleNameChange = (value: string) => {
    setName(value);

    if (error) {
      setError('');
    }
  };

  const handleConfirm = async () => {
    if (validateName(name)) {
      try {
        setIsSubmitting(true);
        await onConfirm(name.trim());
        setName('');
        setError('');
        onClose();
      } catch (submitError) {
        setError(
          isFileAlreadyExistsError(submitError)
            ? t('common.fileOperations.validation.nameExists', { name: name.trim() })
            : submitError instanceof Error
              ? submitError.message
              : String(submitError),
        );
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      void handleConfirm();
    }
  };

  return (
      <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogHeading icon={type === 'file' ? File : Folder}>
            {t(`common.fileOperations.create.${type}.title`)}
          </DialogHeading>
          <DialogDescription>
            {t(`common.fileOperations.create.${type}.description`)}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="name">{t('common.fileOperations.create.nameLabel')}</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t(`common.fileOperations.create.${type}.placeholder`)}
              autoFocus
              className={error ? 'border-red-500' : ''}
            />
            {error && (
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertTriangle className="h-4 w-4" />
                {error}
              </p>
            )}
            {hint ? (
              <p className="text-xs text-muted-foreground">{hint}</p>
            ) : null}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button onClick={() => { void handleConfirm(); }} disabled={!name.trim() || !!error || isSubmitting}>
            {t('common.fileOperations.buttons.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};



export interface FileRenameDialogProps {
  open: boolean;
  currentName: string;
  onClose: () => void;
  onConfirm: (newName: string) => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
}

export const FileRenameDialog: React.FC<FileRenameDialogProps> = ({
  open,
  currentName,
  onClose,
  onConfirm,
}) => {
  const { t } = useI18n();
  const [name, setName] = useState(currentName);
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  React.useEffect(() => {
    if (open) {
      setName(currentName);
      setError('');
    }
  }, [open, currentName]);

  const validateName = (value: string): boolean => {
    const trimmedValue = value.trim();


    if (!trimmedValue) {
      setError(t('common.fileOperations.validation.nameRequired'));
      return false;
    }


    if (trimmedValue === currentName) {
      setError(t('common.fileOperations.validation.nameSame'));
      return false;
    }


    if (trimmedValue.includes('/') || trimmedValue.includes('\\')) {
      setError(t('common.fileOperations.validation.nameWithPath'));
      return false;
    }


    const invalidChars = /[<>:"|?*\x00-\x1f]/;
    if (invalidChars.test(trimmedValue)) {
      setError(t('common.fileOperations.validation.nameWithInvalidChars'));
      return false;
    }


    const reservedNames = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;
    if (reservedNames.test(trimmedValue)) {
      setError(t('common.fileOperations.validation.nameReserved'));
      return false;
    }

    setError('');
    return true;
  };

  const handleNameChange = (value: string) => {
    setName(value);

    if (error) {
      setError('');
    }
  };

  const handleConfirm = async () => {
    if (validateName(name)) {
      try {
        setIsSubmitting(true);
        await onConfirm(name.trim());
        setError('');
        onClose();
      } catch (submitError) {
        setError(
          isFileAlreadyExistsError(submitError)
            ? t('common.fileOperations.validation.nameExists', { name: name.trim() })
            : submitError instanceof Error
              ? submitError.message
              : String(submitError),
        );
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      void handleConfirm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogHeading icon={Edit3}>
            {t('common.fileOperations.rename.title')}
          </DialogHeading>
          <DialogDescription>
            {t('common.fileOperations.rename.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="name">{t('common.fileOperations.rename.nameLabel')}</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
              className={error ? 'border-red-500' : ''}
            />
            {error && (
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertTriangle className="h-4 w-4" />
                {error}
              </p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button onClick={() => { void handleConfirm(); }} disabled={!name.trim() || name === currentName || !!error || isSubmitting}>
            {t('common.fileOperations.buttons.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};



export interface FileDeleteDialogProps {
  open: boolean;
  fileName: string;
  filePath?: string;
  fileType: 'file' | 'directory';
  affectedUnsavedTabsCount?: number;
  onClose: () => void;
  onConfirm: () => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
}

export const FileDeleteDialog: React.FC<FileDeleteDialogProps> = ({
  open,
  fileName,
  filePath,
  fileType,
  affectedUnsavedTabsCount = 0,
  onClose,
  onConfirm,
}) => {
  const { t } = useI18n();
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  React.useEffect(() => {
    if (open) setError('');
  }, [open, filePath]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && !isSubmitting) onClose();
  };

  const handleConfirm = async () => {
    try {
      setIsSubmitting(true);
      await onConfirm();
      setError('');
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : String(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-md flex-col overflow-hidden"
        aria-busy={isSubmitting}
        onEscapeKeyDown={(event) => { if (isSubmitting) event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (isSubmitting) event.preventDefault(); }}
      >
        <DialogHeader>
          <DialogHeading icon={AlertTriangle} className="text-destructive" tone="destructive">
            {t('common.fileOperations.delete.title')}
          </DialogHeading>
          <DialogDescription>
            {t('common.fileOperations.delete.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-auto py-4">
          <p className="text-sm">
            {t(`common.fileOperations.delete.${fileType === 'directory' ? 'folder' : 'file'}`, { name: fileName })}
          </p>
          {fileType === 'directory' && (
            <p className="text-sm text-muted-foreground mt-2">
              {t('common.fileOperations.delete.folderWarning')}
            </p>
          )}
          {filePath ? (
            <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{filePath}</p>
          ) : null}
          {affectedUnsavedTabsCount > 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              {t('common.fileOperations.delete.unsavedTabs', { count: affectedUnsavedTabsCount })}
            </p>
          ) : null}
          {error ? (
            <p className="mt-2 flex items-center gap-1 text-sm text-red-500">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </p>
          ) : null}
        </div>
        <DialogFooter className="shrink-0 sm:justify-between sm:space-x-0">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button variant="destructive" onClick={() => { void handleConfirm(); }} disabled={isSubmitting}>
            {isSubmitting
              ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              : <Trash2 className="mr-2 h-4 w-4" />}
            {t('common.fileOperations.buttons.delete')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};



export interface BatchDeleteDialogProps {
  open: boolean;
  files: Array<{ name: string; path: string; type: 'file' | 'directory' }>;
  onClose: () => void;
  affectedUnsavedTabsCount?: number;
  onConfirm: () => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
}

export const BatchDeleteDialog: React.FC<BatchDeleteDialogProps> = ({
  open,
  files,
  affectedUnsavedTabsCount = 0,
  onClose,
  onConfirm,
}) => {
  const { t } = useI18n();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  React.useEffect(() => {
    if (open) setError('');
  }, [files, open]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && !isSubmitting) onClose();
  };

  const handleConfirm = async () => {
    if (isSubmitting) return;
    setError('');
    setIsSubmitting(true);
    try {
      await onConfirm();
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : String(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const fileCount = files.filter(f => f.type === 'file').length;
  const folderCount = files.filter(f => f.type === 'directory').length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex max-h-[min(90vh,640px)] w-[calc(100vw-2rem)] max-w-md flex-col overflow-hidden"
        aria-busy={isSubmitting}
        onEscapeKeyDown={(event) => { if (isSubmitting) event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (isSubmitting) event.preventDefault(); }}
      >
        <DialogHeader className="shrink-0">
          <DialogHeading icon={AlertTriangle} className="text-destructive" tone="destructive">
            {t('common.fileOperations.batchDelete.title')}
          </DialogHeading>
          <DialogDescription>
            {t('common.fileOperations.batchDelete.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-hidden py-4">
          <div className="shrink-0 text-sm">
            <p className="font-semibold mb-2">
              {t('common.fileOperations.batchDelete.summary', { count: files.length })}
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
              {fileCount > 0 && <span>{t('common.fileOperations.batchDelete.fileCount', { count: fileCount })}</span>}
              {folderCount > 0 && <span>{t('common.fileOperations.batchDelete.folderCount', { count: folderCount })}</span>}
            </div>
          </div>

          <div className="h-48 max-h-[40vh] overflow-auto rounded-md border">
            <div className="min-w-max space-y-2 p-4">
              {files.map((file, index) => (
                <div key={index} className="flex items-center gap-2 text-sm">
                  {file.type === 'directory' ? (
                    <Folder className="h-4 w-4 shrink-0 text-blue-500" />
                  ) : (
                    <File className="h-4 w-4 shrink-0 text-gray-500" />
                  )}
                  <span className="whitespace-nowrap" title={file.path}>
                    {file.path}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {folderCount > 0 && (
            <div className="flex shrink-0 items-start gap-2 text-sm text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{t('common.fileOperations.batchDelete.folderWarning')}</p>
            </div>
          )}
          {affectedUnsavedTabsCount > 0 ? (
            <p className="shrink-0 text-sm text-muted-foreground">
              {t('common.fileOperations.delete.unsavedTabs', { count: affectedUnsavedTabsCount })}
            </p>
          ) : null}
          {error ? (
            <p className="flex shrink-0 items-center gap-1 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </p>
          ) : null}
        </div>
        <DialogFooter className="shrink-0 gap-2 sm:space-x-0">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button variant="destructive" onClick={() => { void handleConfirm(); }} disabled={isSubmitting}>
            {isSubmitting
              ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              : <Trash2 className="mr-2 h-4 w-4" />}
            {t('common.fileOperations.batchDelete.deleteAll')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
