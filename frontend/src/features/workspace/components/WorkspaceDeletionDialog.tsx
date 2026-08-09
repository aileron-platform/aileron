import React, { useId, useState } from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { AlertDialogHeading } from '@/shared/components/ui/dialog-heading';
import { useI18n } from '@/shared/hooks/useI18n';

export interface WorkspaceDeletionDialogProps {
  workspaceName: string | null;
  canDelete: boolean;
  isDeleting: boolean;
  isRetry?: boolean;
  onConfirm: (confirmationName: string) => Promise<boolean>;
  className?: string;
}

export const WorkspaceDeletionDialog: React.FC<WorkspaceDeletionDialogProps> = ({
  workspaceName,
  canDelete,
  isDeleting,
  isRetry = false,
  onConfirm,
  className,
}) => {
  const { t } = useI18n();
  const inputId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [confirmationName, setConfirmationName] = useState('');

  if (!canDelete || !workspaceName) {
    return null;
  }

  const reset = () => {
    setConfirmationName('');
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (isDeleting) {
      return;
    }
    setIsOpen(nextOpen);
    if (!nextOpen) {
      reset();
    }
  };

  const handleConfirm = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    if (isDeleting || confirmationName !== workspaceName) {
      return;
    }

    const accepted = await onConfirm(confirmationName);
    if (accepted) {
      setIsOpen(false);
      reset();
    }
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={handleOpenChange}>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className={className}
          disabled={isDeleting}
          data-testid="workspace-deletion-trigger"
        >
          <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
          {t(isDeleting
            ? 'workspace.workspaceSettings.reset.delete.dialog.confirming'
            : isRetry
              ? 'workspace.workspaceSettings.reset.delete.retry'
              : 'workspace.workspaceSettings.reset.delete.trigger')}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent data-testid="workspace-deletion-dialog">
        <AlertDialogHeader>
          <AlertDialogHeading icon={AlertTriangle} tone="destructive">
            {t('workspace.workspaceSettings.reset.delete.dialog.title', { workspaceName })}
          </AlertDialogHeading>
          <AlertDialogDescription asChild className="space-y-3">
            <div>
              <p>
                {t('workspace.workspaceSettings.reset.delete.dialog.intro', { workspaceName })}
              </p>
              <p>
                {t('workspace.workspaceSettings.reset.delete.dialog.impactTitle')}
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm">
                <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.settings')}</li>
                <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.projects')}</li>
                <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.variables')}</li>
                <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.history')}</li>
                <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.automations')}</li>
              </ul>
              <p className="font-medium text-destructive">
                {t('workspace.workspaceSettings.reset.delete.dialog.warning')}
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-2">
          <Label htmlFor={inputId} className="text-sm">
            {t('workspace.workspaceSettings.reset.delete.dialog.confirmLabel.prefix')}{' '}
            <code className="bg-muted px-1 py-0.5 rounded text-xs">{workspaceName}</code>{' '}
            {t('workspace.workspaceSettings.reset.delete.dialog.confirmLabel.suffix')}
          </Label>
          <Input
            id={inputId}
            value={confirmationName}
            onChange={event => setConfirmationName(event.target.value)}
            placeholder={workspaceName}
            className="h-9 text-sm"
            autoComplete="off"
            disabled={isDeleting}
          />
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel
            onClick={reset}
            className="h-7 px-2 text-xs border-border text-muted-foreground hover:bg-muted"
            disabled={isDeleting}
          >
            {t('workspace.workspaceSettings.reset.delete.dialog.cancel')}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={event => void handleConfirm(event)}
            disabled={confirmationName !== workspaceName || isDeleting}
            className="h-7 px-2 text-xs bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting
              ? t('workspace.workspaceSettings.reset.delete.dialog.confirming')
              : t('workspace.workspaceSettings.reset.delete.dialog.confirm')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
