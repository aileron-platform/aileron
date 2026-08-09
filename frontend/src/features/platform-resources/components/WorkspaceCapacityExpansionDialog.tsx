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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  PlatformResourceStorageKind,
  PlatformWorkspaceSummary,
  WorkspaceCapacityExpansionRequest,
  WorkspaceCapacityExpansionResponse,
} from '../model/platformResourceTypes';

const GIB = 1024 ** 3;

interface Props {
  resource: PlatformWorkspaceSummary | null;
  onClose: () => void;
  onSubmit: (payload: WorkspaceCapacityExpansionRequest) => Promise<void>;
  status: WorkspaceCapacityExpansionResponse | null;
  isSubmitting: boolean;
  hasError: boolean;
}

export const WorkspaceCapacityExpansionDialog: React.FC<Props> = ({
  resource,
  onClose,
  onSubmit,
  status,
  isSubmitting,
  hasError,
}) => {
  const { t } = useI18n();
  const [storageKind, setStorageKind] = React.useState<Extract<PlatformResourceStorageKind, 'workspace_data' | 'runtime_home'>>('workspace_data');
  const [requestedGiB, setRequestedGiB] = React.useState('');

  React.useEffect(() => {
    setStorageKind('workspace_data');
    setRequestedGiB('');
  }, [resource]);

  const selectedCapacity = resource?.[storageKind === 'workspace_data' ? 'workspaceData' : 'runtimeHome'] ?? null;
  const parsedGiB = Number(requestedGiB);
  const requestedBytes = parsedGiB * GIB;
  const canSubmit = Boolean(resource && selectedCapacity?.expansionSupported)
    && /^\d+$/.test(requestedGiB)
    && Number.isSafeInteger(parsedGiB)
    && parsedGiB > 0
    && Number.isSafeInteger(requestedBytes)
    && requestedBytes > (selectedCapacity?.allocatedBytes ?? 0)
    && status == null
    && !isSubmitting;

  const submit = async () => {
    if (!resource || !canSubmit) return;
    try {
      await onSubmit({
        storageKind,
        requestedBytes,
      });
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
          <DialogTitle>{t('platformResources.expansionDialog.title')}</DialogTitle>
          <DialogDescription>
            {t('platformResources.expansionDialog.description', { name: resource?.name ?? '' })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="platform-workspace-storage-kind">
            {t('platformResources.expansionDialog.storageKindLabel')}
          </Label>
          <Select value={storageKind} onValueChange={value => setStorageKind(value as typeof storageKind)}>
            <SelectTrigger id="platform-workspace-storage-kind"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="workspace_data">{t('platformResources.capacity.workspaceData')}</SelectItem>
              <SelectItem value="runtime_home">{t('platformResources.capacity.runtimeHome')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="platform-workspace-requested-gib">
            {t('platformResources.expansionDialog.requestedGiBLabel')}
          </Label>
          <Input
            id="platform-workspace-requested-gib"
            inputMode="numeric"
            min={1}
            step={1}
            value={requestedGiB}
            onChange={event => setRequestedGiB(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">{t('platformResources.expansionDialog.help')}</p>
        </div>
        {status ? (
          <p className="text-sm" aria-live="polite">
            {t(`platformResources.expansionDialog.phases.${status.phase}`)}
          </p>
        ) : null}
        {hasError ? <p className="text-sm text-destructive">{t('platformResources.expansionDialog.error')}</p> : null}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={isSubmitting} onClick={onClose}>
            {t('common.close')}
          </Button>
          <Button type="button" disabled={!canSubmit} onClick={() => { void submit(); }}>
            {t('platformResources.expansionDialog.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
