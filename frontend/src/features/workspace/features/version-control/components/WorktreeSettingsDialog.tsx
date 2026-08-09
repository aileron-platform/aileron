import React, { useEffect, useMemo, useState } from 'react';
import { GitBranch, Save } from 'lucide-react';
import { apiClient } from '@/shared/api/apiClient';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type { WorkspaceDetailResponse } from '@/features/workspace/api/workspaceApiTypes';

const DEFAULT_WORKTREE_SUBDIR = '.worktrees';
const MAX_WORKTREE_SUBDIR_LENGTH = 64;

interface WorktreeSettingsDialogProps {
  open: boolean;
  workspaceId: string | null;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => Promise<void> | void;
}

const validateWorktreeSubdir = (value: string): string | null => {
  const normalized = value.trim();
  if (!normalized || normalized === '.') {
    return 'workspace.versionControl.worktree.validation.empty';
  }
  if (normalized.startsWith('/') || normalized.endsWith('/') || normalized.includes('\\')) {
    return 'workspace.versionControl.worktree.validation.separator';
  }
  const segments = normalized.split('/');
  if (segments.some(segment => !segment)) {
    return 'workspace.versionControl.worktree.validation.separator';
  }
  if (segments.some(segment => segment === '.' || segment === '..')) {
    return 'workspace.versionControl.worktree.validation.parentTraversal';
  }
  if (normalized.length > MAX_WORKTREE_SUBDIR_LENGTH) {
    return 'workspace.versionControl.worktree.validation.tooLong';
  }
  return null;
};

export const WorktreeSettingsDialog: React.FC<WorktreeSettingsDialogProps> = ({
  open,
  workspaceId,
  onOpenChange,
  onSaved,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [value, setValue] = useState(DEFAULT_WORKTREE_SUBDIR);
  const [initialValue, setInitialValue] = useState(DEFAULT_WORKTREE_SUBDIR);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let isActive = true;

    const loadWorkspace = async () => {
      if (!open || !workspaceId) {
        return;
      }

      setIsLoading(true);
      setErrorKey(null);
      try {
        const detail = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`
        );
        if (!isActive) {
          return;
        }
        const nextValue = detail.worktreeSubdir || DEFAULT_WORKTREE_SUBDIR;
        setValue(nextValue);
        setInitialValue(nextValue);
      } catch {
        if (isActive) {
          toast({
            title: t('workspace.versionControl.worktree.toast.loadFailed.title'),
            description: t('workspace.versionControl.worktree.toast.loadFailed.description'),
            variant: 'destructive',
          });
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadWorkspace();

    return () => {
      isActive = false;
    };
  }, [open, t, toast, workspaceId]);

  const validationErrorKey = useMemo(() => validateWorktreeSubdir(value), [value]);
  const canSave = Boolean(workspaceId) && !isLoading && !isSaving && !validationErrorKey && value.trim() !== initialValue;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!workspaceId) {
      return;
    }

    const nextErrorKey = validateWorktreeSubdir(value);
    setErrorKey(nextErrorKey);
    if (nextErrorKey) {
      return;
    }

    setIsSaving(true);
    try {
      const normalized = value.trim();
      await apiClient.put<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
        { worktreeSubdir: normalized }
      );
      setInitialValue(normalized);
      setValue(normalized);
      toast({
        title: t('workspace.versionControl.worktree.toast.saveSuccess.title'),
        description: t('workspace.versionControl.worktree.toast.saveSuccess.description'),
      });
      await onSaved?.();
      onOpenChange(false);
    } catch {
      toast({
        title: t('workspace.versionControl.worktree.toast.saveFailed.title'),
        description: t('workspace.versionControl.worktree.toast.saveFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const displayedErrorKey = errorKey || validationErrorKey;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogHeading icon={GitBranch}>
            {t('workspace.versionControl.worktree.dialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('workspace.versionControl.worktree.dialog.description')}
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="worktree-subdir">
              {t('workspace.versionControl.worktree.dialog.fieldLabel')}
            </Label>
            <Input
              id="worktree-subdir"
              value={value}
              disabled={isLoading || isSaving}
              aria-invalid={Boolean(displayedErrorKey)}
              aria-describedby="worktree-subdir-help"
              onChange={(event) => {
                setValue(event.target.value);
                setErrorKey(null);
              }}
            />
            <p id="worktree-subdir-help" className="text-xs text-muted-foreground">
              {displayedErrorKey
                ? t(displayedErrorKey)
                : t('workspace.versionControl.worktree.dialog.helper')}
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
              {t('workspace.versionControl.worktree.dialog.cancel')}
            </Button>
            <Button type="submit" disabled={!canSave}>
              <Save className="mr-2 h-4 w-4" />
              {isSaving
                ? t('workspace.versionControl.worktree.dialog.saving')
                : t('workspace.versionControl.worktree.dialog.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
