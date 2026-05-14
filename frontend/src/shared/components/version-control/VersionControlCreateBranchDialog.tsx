import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useState } from 'react';
import { GitBranch } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';

export interface VersionControlCreateBranchPayload {
  branch: string;
  startPoint?: string;
  stashChanges?: boolean;
}

interface VersionControlCreateBranchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: VersionControlCreateBranchPayload) => void | Promise<void>;
  isCreating?: boolean;
  supportsStartPoint?: boolean;
  supportsStashBeforeCheckout?: boolean;
}

export const VersionControlCreateBranchDialog: React.FC<VersionControlCreateBranchDialogProps> = ({
  open,
  onOpenChange,
  onCreate,
  isCreating = false,
  supportsStartPoint = true,
  supportsStashBeforeCheckout = true,
}) => {
  const { t } = useI18n();
  const [branchName, setBranchName] = useState('');
  const [startPoint, setStartPoint] = useState('');
  const [stashBeforeCheckout, setStashBeforeCheckout] = useState(false);

  useEffect(() => {
    if (!open) {
      setBranchName('');
      setStartPoint('');
      setStashBeforeCheckout(false);
    }
  }, [open]);

  const handleCreate = async () => {
    const branch = branchName.trim();
    if (!branch) {
      return;
    }

    await onCreate({
      branch,
      startPoint: supportsStartPoint ? startPoint.trim() || undefined : undefined,
      stashChanges: supportsStashBeforeCheckout ? stashBeforeCheckout : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogHeading icon={GitBranch} iconClassName="h-4 w-4">
            {t('shared.versionControl.branchDialog.title')}
          </DialogHeading>
          <DialogDescription>{t('shared.versionControl.branchDialog.description')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
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
          {supportsStashBeforeCheckout && (
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Checkbox
                checked={stashBeforeCheckout}
                onCheckedChange={(checked) => setStashBeforeCheckout(Boolean(checked))}
              />
              {t('shared.versionControl.branchDialog.stashChanges')}
            </label>
          )}
        </div>
        <DialogFooter>
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

export default VersionControlCreateBranchDialog;
