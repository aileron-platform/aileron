import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React from 'react';
import { Check, Share2, UserPlus, UsersRound, X } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareTargetType,
} from '@/features/knowledge-base/model/knowledgeBaseTypes';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import {
  searchKnowledgeBaseShareCandidates,
  type KnowledgeBaseShareCandidate,
} from '@/features/knowledge-base/api/knowledgeBaseApi';
import { cn } from '@/shared/utils/cn';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';
import { getKnowledgeBaseSharingErrorI18nKey } from '../model/knowledgeBaseSharingErrorI18n';

type ShareRole = Exclude<ResourceAccessRole, 'owner'>;

interface KnowledgeBaseSharingTabProps {
  knowledgeBaseId: string;
  canManage: boolean;
}

const ROLE_BADGE_VARIANT: Record<ShareRole, 'outline' | 'secondary' | 'default'> = {
  reader: 'outline',
  manager: 'default',
};

const formatDateTime = (value: string, language: string): string => (
  new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
);

export const KnowledgeBaseSharingTab: React.FC<KnowledgeBaseSharingTabProps> = ({
  knowledgeBaseId,
  canManage,
}) => {
  const { toast } = useToast();
  const { state: i18nState, t } = useI18n();
  const {
    sharesById,
    isMutating,
    loadKnowledgeBaseShares,
    createKnowledgeBaseShare,
    updateKnowledgeBaseShare,
    deleteKnowledgeBaseShare,
  } = useKnowledgeBase();
  const [error, setError] = React.useState<string | null>(null);
  const [isAddDialogOpen, setIsAddDialogOpen] = React.useState(false);
  const [candidateTargetType, setCandidateTargetType] = React.useState<KnowledgeBaseShareTargetType>('user');
  const [candidateQuery, setCandidateQuery] = React.useState('');
  const [candidateTargetId, setCandidateTargetId] = React.useState('');
  const [candidateRole, setCandidateRole] = React.useState<ShareRole>('reader');
  const [candidatePickerOpen, setCandidatePickerOpen] = React.useState(false);
  const [candidates, setCandidates] = React.useState<KnowledgeBaseShareCandidate[]>([]);
  const [isSearchingCandidates, setIsSearchingCandidates] = React.useState(false);
  const [busyShareId, setBusyShareId] = React.useState<string | null>(null);
  const ROLE_OPTIONS: Array<{ value: ShareRole; label: string; description: string }> = React.useMemo(() => ([
    { value: 'reader', label: t('knowledgeBase.sharing.roles.reader.label'), description: t('knowledgeBase.sharing.roles.reader.description') },
    { value: 'manager', label: t('knowledgeBase.sharing.roles.manager.label'), description: t('knowledgeBase.sharing.roles.manager.description') },
  ]), [t]);
  const roleLabel = React.useCallback((role: ShareRole) => t(`knowledgeBase.sharing.roles.${role}.label`), [t]);
  const candidateLabel = candidateTargetType === 'user'
    ? t('knowledgeBase.sharing.candidate.userLabel')
    : t('knowledgeBase.sharing.candidate.groupLabel');
  const candidatePlaceholder = candidateTargetType === 'user'
    ? t('knowledgeBase.sharing.candidate.userPlaceholder')
    : t('knowledgeBase.sharing.candidate.groupPlaceholder');
  const candidateEmpty = candidateTargetType === 'user'
    ? t('knowledgeBase.sharing.candidate.userEmpty')
    : t('knowledgeBase.sharing.candidate.groupEmpty');

  const shares = React.useMemo(
    () => sharesById[knowledgeBaseId] ?? [],
    [knowledgeBaseId, sharesById],
  );

  React.useEffect(() => {
    if (sharesById[knowledgeBaseId] === undefined) {
      void loadKnowledgeBaseShares(knowledgeBaseId).catch((loadError: unknown) => {
        setError(t(getKnowledgeBaseSharingErrorI18nKey(loadError)));
      });
    }
  }, [knowledgeBaseId, loadKnowledgeBaseShares, sharesById, t]);

  React.useEffect(() => {
    if (!canManage || !candidatePickerOpen) {
      setCandidates([]);
      setIsSearchingCandidates(false);
      return;
    }

    const query = candidateQuery.trim();
    if (!query) {
      setCandidates([]);
      setIsSearchingCandidates(false);
      return;
    }

    let active = true;
    setIsSearchingCandidates(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await searchKnowledgeBaseShareCandidates(
          knowledgeBaseId,
          candidateTargetType,
          query,
        );
        if (!active) {
          return;
        }
        setCandidates(response);
      } catch (searchError) {
        if (!active) {
          return;
        }
        setCandidates([]);
        setError(t(getKnowledgeBaseSharingErrorI18nKey(searchError)));
      } finally {
        if (active) {
          setIsSearchingCandidates(false);
        }
      }
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [canManage, candidatePickerOpen, candidateQuery, candidateTargetType, knowledgeBaseId, t]);

  const selectedCandidate = React.useMemo(
    () => candidates.find((item) => item.id === candidateTargetId) ?? null,
    [candidateTargetId, candidates],
  );

  const autocompleteCandidates = React.useMemo(
    () => candidates.filter((candidate) => !shares.some(
      (share) => share.targetType === candidateTargetType && share.targetId === candidate.id,
    )),
    [candidateTargetType, candidates, shares],
  );

  const resetDraft = React.useCallback(() => {
    setCandidateTargetType('user');
    setCandidateQuery('');
    setCandidateTargetId('');
    setCandidateRole('reader');
    setCandidates([]);
    setCandidatePickerOpen(false);
  }, []);

  const handleTargetTypeChange = React.useCallback((targetType: KnowledgeBaseShareTargetType) => {
    setCandidateTargetType(targetType);
    setCandidateQuery('');
    setCandidateTargetId('');
    setCandidates([]);
    setCandidatePickerOpen(false);
    setError(null);
  }, []);

  const handleCreateShare = React.useCallback(async () => {
    if (!candidateTargetId) {
      return;
    }

    setError(null);
    try {
      const createdShare = await createKnowledgeBaseShare(knowledgeBaseId, {
        targetType: candidateTargetType,
        targetId: candidateTargetId,
        role: candidateRole,
      });
      toast({
        title: t('knowledgeBase.sharing.createSuccessTitle'),
        description: t('knowledgeBase.sharing.createSuccessDescription', {
          name: createdShare.targetLabel,
          role: roleLabel(createdShare.role),
        }),
      });
      setIsAddDialogOpen(false);
      resetDraft();
    } catch (createError) {
      setError(t(getKnowledgeBaseSharingErrorI18nKey(createError)));
    }
  }, [candidateRole, candidateTargetId, candidateTargetType, createKnowledgeBaseShare, knowledgeBaseId, resetDraft, roleLabel, t, toast]);

  const handleUpdateRole = React.useCallback(async (shareId: string, role: ShareRole) => {
    setBusyShareId(shareId);
    setError(null);
    try {
      await updateKnowledgeBaseShare(knowledgeBaseId, shareId, { role });
      toast({
        title: t('knowledgeBase.sharing.updateSuccessTitle'),
        description: t('knowledgeBase.sharing.updateSuccessDescription', { role: roleLabel(role) }),
      });
    } catch (updateError) {
      setError(t(getKnowledgeBaseSharingErrorI18nKey(updateError)));
    } finally {
      setBusyShareId(null);
    }
  }, [knowledgeBaseId, roleLabel, t, toast, updateKnowledgeBaseShare]);

  const handleDeleteShare = React.useCallback(async (share: KnowledgeBaseShareSummary) => {
    setBusyShareId(share.id);
    setError(null);
    try {
      await deleteKnowledgeBaseShare(knowledgeBaseId, share.id);
      toast({
        title: t('knowledgeBase.sharing.deleteSuccessTitle'),
        description: share.targetLabel,
      });
    } catch (deleteError) {
      setError(t(getKnowledgeBaseSharingErrorI18nKey(deleteError)));
    } finally {
      setBusyShareId(null);
    }
  }, [deleteKnowledgeBaseShare, knowledgeBaseId, t, toast]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <FeatureHeader
        title={t('knowledgeBase.navigation.sharing')}
        icon={Share2}
        actions={(
          <Button
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setError(null);
              setIsAddDialogOpen(true);
            }}
            disabled={!canManage}
          >
            <UserPlus className="mr-1.5 h-3.5 w-3.5" />
            {t('knowledgeBase.sharing.addAction')}
          </Button>
        )}
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="space-y-6 bg-background p-6">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('knowledgeBase.sharing.description')}
          </p>

          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {shares.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-sm text-muted-foreground">
              {t('knowledgeBase.sharing.empty')}
            </div>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {shares.map((share) => (
                <div
                  key={share.id}
                  className="flex flex-col gap-3 rounded-md border border-border/60 bg-background/70 p-4 md:flex-row md:items-center md:justify-between"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium text-foreground">{share.targetLabel}</span>
                      <Badge variant={ROLE_BADGE_VARIANT[share.role]}>{roleLabel(share.role)}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('knowledgeBase.sharing.table.grantedBy')}: {share.grantedById} · {t('knowledgeBase.sharing.table.grantedAt')}: {formatDateTime(share.createdAt, i18nState.currentLanguage)}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Select
                      value={share.role}
                      onValueChange={(value: ShareRole) => {
                        if (value !== share.role) {
                          void handleUpdateRole(share.id, value);
                        }
                      }}
                      disabled={!canManage || isMutating || busyShareId === share.id}
                    >
                      <SelectTrigger className="w-[130px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!canManage || isMutating || busyShareId === share.id}
                      onClick={() => {
                        void handleDeleteShare(share);
                      }}
                    >
                      <X className="mr-2 h-4 w-4" />
                      {t('knowledgeBase.sharing.table.removeLabel')}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

      <Dialog
        open={isAddDialogOpen}
        onOpenChange={(open) => {
          setIsAddDialogOpen(open);
          if (!open) {
            resetDraft();
          }
        }}
      >
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogHeading icon={UserPlus}>
              {t('knowledgeBase.sharing.candidate.title')}
            </DialogHeading>
            <DialogDescription>{t('knowledgeBase.sharing.candidate.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label id="kb-share-target-type-label">
                {t('knowledgeBase.sharing.candidate.targetTypeLabel')}
              </Label>
              <div
                role="radiogroup"
                aria-labelledby="kb-share-target-type-label"
                className="grid grid-cols-2 gap-2"
              >
                <Button
                  type="button"
                  role="radio"
                  aria-checked={candidateTargetType === 'user'}
                  variant={candidateTargetType === 'user' ? 'default' : 'outline'}
                  onClick={() => handleTargetTypeChange('user')}
                >
                  <UserPlus className="mr-2 h-4 w-4" />
                  {t('knowledgeBase.sharing.candidate.targetTypes.user')}
                </Button>
                <Button
                  type="button"
                  role="radio"
                  aria-checked={candidateTargetType === 'user_group'}
                  variant={candidateTargetType === 'user_group' ? 'default' : 'outline'}
                  onClick={() => handleTargetTypeChange('user_group')}
                >
                  <UsersRound className="mr-2 h-4 w-4" />
                  {t('knowledgeBase.sharing.candidate.targetTypes.group')}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="kb-share-target">{candidateLabel}</Label>
              <Popover open={candidatePickerOpen} onOpenChange={setCandidatePickerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="kb-share-target"
                    type="button"
                    variant="outline"
                    role="combobox"
                    className={cn(
                      'w-full justify-between font-normal',
                      !selectedCandidate && !candidateQuery && 'text-muted-foreground',
                    )}
                  >
                    {selectedCandidate
                      ? selectedCandidate.label
                      : candidateQuery || candidatePlaceholder}
                    <UserPlus className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder={candidatePlaceholder}
                      value={candidateQuery}
                      onValueChange={(value) => {
                        setCandidateQuery(value);
                        setCandidateTargetId('');
                      }}
                    />
                    <CommandList>
                      {isSearchingCandidates ? (
                        <div className="px-3 py-6 text-sm text-muted-foreground">{t('knowledgeBase.sharing.candidate.searching')}</div>
                      ) : null}
                      {!isSearchingCandidates && candidateQuery.trim().length === 0 ? (
                        <CommandEmpty>{t('knowledgeBase.sharing.candidate.startTyping')}</CommandEmpty>
                      ) : null}
                      {!isSearchingCandidates && candidateQuery.trim().length > 0 && autocompleteCandidates.length === 0 ? (
                        <CommandEmpty>{candidateEmpty}</CommandEmpty>
                      ) : null}
                      {autocompleteCandidates.length > 0 ? (
                        <CommandGroup heading={t('knowledgeBase.sharing.candidate.results')}>
                          {autocompleteCandidates.map((candidate) => (
                            <CommandItem
                              key={candidate.id}
                              value={candidate.id}
                              onSelect={() => {
                                setCandidateTargetId(candidate.id);
                                setCandidateQuery(candidate.label);
                                setCandidatePickerOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  'h-4 w-4',
                                  candidate.id === candidateTargetId ? 'opacity-100' : 'opacity-0',
                                )}
                              />
                              <div className="min-w-0">
                                <div className="truncate font-medium">
                                  {candidate.label}
                                </div>
                                {candidate.description ? (
                                  <div className="truncate text-xs text-muted-foreground">
                                    {candidate.description}
                                  </div>
                                ) : null}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      ) : null}
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label htmlFor="kb-share-role">{t('knowledgeBase.sharing.candidate.roleLabel')}</Label>
              <Select value={candidateRole} onValueChange={(value: ShareRole) => setCandidateRole(value)}>
                <SelectTrigger id="kb-share-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {ROLE_OPTIONS.find((option) => option.value === candidateRole)?.description}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              {t('knowledgeBase.common.actions.cancel')}
            </Button>
            <Button onClick={() => { void handleCreateShare(); }} disabled={!candidateTargetId || isMutating}>
              {t('knowledgeBase.sharing.candidate.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
      </div>
    </div>
  );
};
