/**
 *
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { AlertTriangle, File, Folder, Trash2, Edit3 } from 'lucide-react';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useI18n } from '@/shared/hooks/useI18n';



export interface FileCreateDialogProps {
  open: boolean;
  type: 'file' | 'folder';
  onClose: () => void;
  onConfirm: (name: string) => void;
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

  const handleConfirm = () => {
    if (validateName(name)) {
      onConfirm(name.trim());
      setName('');
      setError('');
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {type === 'file' ? <File className="h-5 w-5" /> : <Folder className="h-5 w-5" />}
            {t(`common.fileOperations.create.${type}.title`)}
          </DialogTitle>
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
          <Button onClick={handleConfirm} disabled={!name.trim() || !!error}>
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
  onConfirm: (newName: string) => void;
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

  const handleConfirm = () => {
    if (validateName(name)) {
      onConfirm(name.trim());
      setError('');
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit3 className="h-5 w-5" />
            {t('common.fileOperations.rename.title')}
          </DialogTitle>
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
          <Button onClick={handleConfirm} disabled={!name.trim() || name === currentName || !!error}>
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
  fileType: 'file' | 'directory';
  onClose: () => void;
  onConfirm: () => void;
}

export const FileDeleteDialog: React.FC<FileDeleteDialogProps> = ({
  open,
  fileName,
  fileType,
  onClose,
  onConfirm,
}) => {
  const { t } = useI18n();

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {t('common.fileOperations.delete.title')}
          </DialogTitle>
          <DialogDescription>
            {t('common.fileOperations.delete.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm">
            {t(`common.fileOperations.delete.${fileType === 'directory' ? 'folder' : 'file'}`, { name: fileName })}
          </p>
          {fileType === 'directory' && (
            <p className="text-sm text-muted-foreground mt-2">
              {t('common.fileOperations.delete.folderWarning')}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button variant="destructive" onClick={handleConfirm}>
            <Trash2 className="h-4 w-4 mr-2" />
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
  onConfirm: () => void;
}

export const BatchDeleteDialog: React.FC<BatchDeleteDialogProps> = ({
  open,
  files,
  onClose,
  onConfirm,
}) => {
  const { t } = useI18n();

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  const fileCount = files.filter(f => f.type === 'file').length;
  const folderCount = files.filter(f => f.type === 'directory').length;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {t('common.fileOperations.batchDelete.title')}
          </DialogTitle>
          <DialogDescription>
            {t('common.fileOperations.batchDelete.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="py-4 space-y-4">
          <div className="text-sm">
            <p className="font-semibold mb-2">
              {t('common.fileOperations.batchDelete.summary', { count: files.length })}
            </p>
            <div className="flex gap-4 text-muted-foreground">
              {fileCount > 0 && <span>{t('common.fileOperations.batchDelete.fileCount', { count: fileCount })}</span>}
              {folderCount > 0 && <span>{t('common.fileOperations.batchDelete.folderCount', { count: folderCount })}</span>}
            </div>
          </div>

          <ScrollArea className="h-[200px] rounded-md border p-4">
            <div className="space-y-2">
              {files.map((file, index) => (
                <div key={index} className="flex items-center gap-2 text-sm">
                  {file.type === 'directory' ? (
                    <Folder className="h-4 w-4 text-blue-500" />
                  ) : (
                    <File className="h-4 w-4 text-gray-500" />
                  )}
                  <span className="truncate">{file.path}</span>
                </div>
              ))}
            </div>
          </ScrollArea>

          {folderCount > 0 && (
            <p className="text-sm text-muted-foreground">
              {t('common.fileOperations.batchDelete.folderWarning')}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('common.fileOperations.buttons.cancel')}
          </Button>
          <Button variant="destructive" onClick={handleConfirm}>
            <Trash2 className="h-4 w-4 mr-2" />
            {t('common.fileOperations.batchDelete.deleteAll')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
