import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useState } from 'react';
import { GitBranch } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';

export interface VersionControlCreateBranchPayload {
  branch: string;
  startPoint?: string;
}

interface VersionControlCreateBranchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: VersionControlCreateBranchPayload) => void | Promise<void>;
  isCreating?: boolean;
  supportsStartPoint?: boolean;
  initialBranchName?: string;
  initialStartPoint?: string;
}

export const VersionControlCreateBranchDialog: React.FC<VersionControlCreateBranchDialogProps> = ({
  open,
  onOpenChange,
  onCreate,
  isCreating = false,
  supportsStartPoint = true,
  initialBranchName = '',
  initialStartPoint = '',
}) => {
  const { t } = useI18n();
  const [branchName, setBranchName] = useState('');
  const [startPoint, setStartPoint] = useState('');

  useEffect(() => {
    if (open) {
      setBranchName(initialBranchName);
      setStartPoint(initialStartPoint);
    } else {
      setBranchName('');
      setStartPoint('');
    }
  }, [initialBranchName, initialStartPoint, open]);

  const handleCreate = async () => {
    const branch = branchName.trim();
    if (!branch) {
      return;
    }

    await onCreate({
      branch,
      startPoint: supportsStartPoint ? startPoint.trim() || undefined : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[calc(100vh-2rem)] max-w-lg flex-col overflow-hidden">
        <DialogHeader>
          <DialogHeading icon={GitBranch} iconClassName="h-4 w-4">
            {t('shared.versionControl.branchDialog.title')}
          </DialogHeading>
          <DialogDescription>{t('shared.versionControl.branchDialog.description')}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          <Input
            value={branchName}
            onChange={(event) => setBranchName(event.target.value)}
            placeholder={t('shared.versionControl.branchDialog.namePlaceholder')}
            aria-label={t('shared.versionControl.branchDialog.nameLabel')}
          />
          {supportsStartPoint && (
            <Input
              value={startPoint}
              onChange={(event) => setStartPoint(event.target.value)}
              placeholder={t('shared.versionControl.branchDialog.startPointPlaceholder')}
              aria-label={t('shared.versionControl.branchDialog.startPointLabel')}
            />
          )}
        </div>
        <DialogFooter className="shrink-0 sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('shared.versionControl.branchDialog.cancel')}
          </Button>
          <Button type="button" onClick={() => void handleCreate()} disabled={!branchName.trim() || isCreating}>
            {isCreating
              ? t('shared.versionControl.branchDialog.creating')
              : t('shared.versionControl.branchDialog.create')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
