import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import type { PlatformKnowledgeBaseSummary } from '../model/platformResourceTypes';

const GIB = 1024 ** 3;

interface Props {
  selectionIdentity: string | null;
  resource: PlatformKnowledgeBaseSummary | null;
  onClose: () => void;
  onSubmit: (quotaBytes: number | null) => Promise<void>;
  isSubmitting: boolean;
  hasError: boolean;
}

export const KnowledgeBaseQuotaDialog: React.FC<Props> = ({
  selectionIdentity,
  resource,
  onClose,
  onSubmit,
  isSubmitting,
  hasError,
}) => {
  const { t } = useI18n();
  const [quotaGiB, setQuotaGiB] = React.useState('');
  const activeIdentity = selectionIdentity;
  const activeIdentityRef = React.useRef(activeIdentity);
  activeIdentityRef.current = activeIdentity;

  React.useEffect(() => {
    setQuotaGiB(resource ? String(resource.effectiveQuotaBytes / GIB) : '');
  }, [resource, selectionIdentity]);

  const parsedGiB = Number(quotaGiB);
  const requestedBytes = parsedGiB * GIB;
  const canSubmit = Boolean(resource)
    && /^\d+$/.test(quotaGiB)
    && Number.isSafeInteger(parsedGiB)
    && parsedGiB >= 0
    && Number.isSafeInteger(requestedBytes)
    && requestedBytes >= (resource?.currentSizeBytes ?? 0)
    && !isSubmitting;

  const updateQuota = async (quotaBytes: number | null) => {
    if (!resource || isSubmitting) return;
    const submittedIdentity = activeIdentity;
    try {
      await onSubmit(quotaBytes);
      if (activeIdentityRef.current === submittedIdentity) onClose();
    } catch {
      // Mutation state renders the localized error.
    }
  };

  return (
    <Dialog
      open={resource !== null}
      onOpenChange={open => { if (!open && !isSubmitting) onClose(); }}
    >
      <DialogContent
        onEscapeKeyDown={event => { if (isSubmitting) event.preventDefault(); }}
        onInteractOutside={event => { if (isSubmitting) event.preventDefault(); }}
      >
        <DialogHeader>
          <DialogTitle>{t('platformResources.quotaDialog.title')}</DialogTitle>
          <DialogDescription>
            {t('platformResources.quotaDialog.description', { name: resource?.name ?? '' })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="platform-kb-quota-gib">
            {t('platformResources.quotaDialog.quotaGiBLabel')}
          </Label>
          <Input
            id="platform-kb-quota-gib"
            inputMode="numeric"
            min={0}
            step={1}
            value={quotaGiB}
            onChange={event => setQuotaGiB(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">{t('platformResources.quotaDialog.help')}</p>
        </div>
        {hasError ? <p className="text-sm text-destructive">{t('platformResources.quotaDialog.error')}</p> : null}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={isSubmitting} onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="button" variant="outline" disabled={!resource || isSubmitting} onClick={() => { void updateQuota(null); }}>
            {t('platformResources.quotaDialog.reset')}
          </Button>
          <Button type="button" disabled={!canSubmit} onClick={() => { void updateQuota(requestedBytes); }}>
            {t('platformResources.quotaDialog.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
