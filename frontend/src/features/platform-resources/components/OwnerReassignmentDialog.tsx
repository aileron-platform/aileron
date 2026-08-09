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
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  PlatformResourceOwnerCandidate,
  PlatformResourceOwnerReassignment,
  PlatformResourceSummary,
} from '../model/platformResourceTypes';

interface Props {
  selectionIdentity: string | null;
  resource: PlatformResourceSummary | null;
  candidates: PlatformResourceOwnerCandidate[];
  isSearching: boolean;
  searchError: boolean;
  isSubmitting: boolean;
  submitError: boolean;
  onSearch: (query: string) => void;
  onSubmit: (payload: PlatformResourceOwnerReassignment) => Promise<unknown>;
  onClose: () => void;
}

export const OwnerReassignmentDialog: React.FC<Props> = ({
  selectionIdentity,
  resource,
  candidates,
  isSearching,
  searchError,
  isSubmitting,
  submitError,
  onSearch,
  onSubmit,
  onClose,
}) => {
  const { t } = useI18n();
  const [candidateQuery, setCandidateQuery] = React.useState('');
  const [selectedCandidateId, setSelectedCandidateId] = React.useState<string | null>(null);
  const [reason, setReason] = React.useState('');
  const activeIdentity = selectionIdentity;
  const activeIdentityRef = React.useRef(activeIdentity);
  activeIdentityRef.current = activeIdentity;

  React.useEffect(() => {
    setCandidateQuery('');
    setSelectedCandidateId(null);
    setReason('');
  }, [resource, selectionIdentity]);

  const normalizedReason = reason.trim();
  const canSubmit = Boolean(
    resource
    && selectedCandidateId
    && normalizedReason.length >= 3
    && normalizedReason.length <= 500
    && !isSubmitting,
  );

  const submit = async () => {
    if (!selectedCandidateId || !canSubmit) return;
    const submittedIdentity = activeIdentity;
    try {
      await onSubmit({ targetUserId: selectedCandidateId, reason: normalizedReason });
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
          <DialogTitle>{t('platformResources.ownerReassignment.title')}</DialogTitle>
          <DialogDescription>
            {t('platformResources.ownerReassignment.description', { name: resource?.name ?? '' })}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          role="search"
          onSubmit={event => {
            event.preventDefault();
            setSelectedCandidateId(null);
            onSearch(candidateQuery);
          }}
        >
          <Label htmlFor="platform-resource-owner-search">
            {t('platformResources.ownerReassignment.userSearchLabel')}
          </Label>
          <div className="flex gap-2">
            <Input
              id="platform-resource-owner-search"
              type="search"
              value={candidateQuery}
              onChange={event => setCandidateQuery(event.target.value)}
            />
            <Button type="submit" disabled={!candidateQuery.trim() || isSearching}>
              {t('platformResources.ownerReassignment.search')}
            </Button>
          </div>
        </form>
        <div className="max-h-40 space-y-2 overflow-y-auto">
          {searchError ? (
            <p className="text-sm text-destructive">{t('platformResources.errors.candidateSearch')}</p>
          ) : candidates.map(candidate => (
            <Button
              key={candidate.id}
              type="button"
              variant={selectedCandidateId === candidate.id ? 'default' : 'outline'}
              className="h-auto w-full justify-start py-2 text-left"
              onClick={() => setSelectedCandidateId(candidate.id)}
            >
              <span>
                <span className="block">{candidate.displayName || candidate.username}</span>
                <span className="block text-xs opacity-75">@{candidate.username}</span>
              </span>
            </Button>
          ))}
        </div>
        <div className="space-y-2">
          <Label htmlFor="platform-resource-owner-reason">
            {t('platformResources.ownerReassignment.reasonLabel')}
          </Label>
          <Textarea
            id="platform-resource-owner-reason"
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={event => setReason(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            {t('platformResources.ownerReassignment.reasonHelp')}
          </p>
        </div>
        {submitError ? (
          <p className="text-sm text-destructive">{t('platformResources.errors.reassignment')}</p>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={isSubmitting} onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="button" disabled={!canSubmit} onClick={() => { void submit(); }}>
            {t('platformResources.ownerReassignment.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
