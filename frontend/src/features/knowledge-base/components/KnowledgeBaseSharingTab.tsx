import React from 'react';
import { Check, Shield, Share2, UserPlus, X } from 'lucide-react';
import { apiClient } from '@/shared/api/apiClient';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
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
  KnowledgeBaseRole,
  KnowledgeBaseShareSummary,
} from '@/shared/types/knowledgeBase';
import { cn } from '@/shared/utils/cn';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

type ShareRole = Exclude<KnowledgeBaseRole, 'owner'>;

interface KnowledgeBaseSharingTabProps {
  knowledgeBaseId: string;
  accessRole: KnowledgeBaseRole;
}

interface UserDirectoryItem {
  id: string;
  email: string;
  username?: string | null;
  displayName?: string | null;
}

interface UserDirectoryResponse {
  items?: UserDirectoryItem[];
}

const ROLE_BADGE_VARIANT: Record<ShareRole, 'outline' | 'secondary' | 'default'> = {
  viewer: 'outline',
  editor: 'secondary',
  manager: 'default',
};

const formatDateTime = (value: string): string => new Date(value).toLocaleString('zh-TW');

export const KnowledgeBaseSharingTab: React.FC<KnowledgeBaseSharingTabProps> = ({
  knowledgeBaseId,
  accessRole,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
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
  const [candidateQuery, setCandidateQuery] = React.useState('');
  const [candidateUserId, setCandidateUserId] = React.useState('');
  const [candidateRole, setCandidateRole] = React.useState<ShareRole>('viewer');
  const [candidatePickerOpen, setCandidatePickerOpen] = React.useState(false);
  const [candidates, setCandidates] = React.useState<UserDirectoryItem[]>([]);
  const [isSearchingUsers, setIsSearchingUsers] = React.useState(false);
  const [busyShareId, setBusyShareId] = React.useState<string | null>(null);
  const ROLE_OPTIONS: Array<{ value: ShareRole; label: string; description: string }> = React.useMemo(() => ([
    { value: 'viewer', label: t('knowledgeBase.sharing.roles.viewer.label'), description: t('knowledgeBase.sharing.roles.viewer.description') },
    { value: 'editor', label: t('knowledgeBase.sharing.roles.editor.label'), description: t('knowledgeBase.sharing.roles.editor.description') },
    { value: 'manager', label: t('knowledgeBase.sharing.roles.manager.label'), description: t('knowledgeBase.sharing.roles.manager.description') },
  ]), [t]);
  const roleLabel = React.useCallback((role: ShareRole) => t(`knowledgeBase.sharing.roles.${role}.label`), [t]);

  const canManageSharing = accessRole === 'owner' || accessRole === 'manager';
  const shares = sharesById[knowledgeBaseId] ?? [];

  React.useEffect(() => {
    if (sharesById[knowledgeBaseId] === undefined) {
      void loadKnowledgeBaseShares(knowledgeBaseId);
    }
  }, [knowledgeBaseId, loadKnowledgeBaseShares, sharesById]);

  React.useEffect(() => {
    if (!canManageSharing || !candidatePickerOpen) {
      setCandidates([]);
      setIsSearchingUsers(false);
      return;
    }

    const query = candidateQuery.trim();
    if (!query) {
      setCandidates([]);
      setIsSearchingUsers(false);
      return;
    }

    let active = true;
    setIsSearchingUsers(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiClient.get<UserDirectoryResponse>(
          `/users?query=${encodeURIComponent(query)}&limit=8`,
        );
        if (!active) {
          return;
        }
        setCandidates(response.items ?? []);
      } catch (err) {
        if (!active) {
          return;
        }
        setCandidates([]);
        setError(err instanceof Error ? err.message : t('knowledgeBase.sharing.searchUsersFailed'));
      } finally {
        if (active) {
          setIsSearchingUsers(false);
        }
      }
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [candidatePickerOpen, candidateQuery, canManageSharing, t]);

  const selectedCandidate = React.useMemo(
    () => candidates.find((item) => item.id === candidateUserId) ?? null,
    [candidateUserId, candidates],
  );

  const autocompleteCandidates = React.useMemo(
    () => candidates.filter((user) => !shares.some((share) => share.userId === user.id)),
    [candidates, shares],
  );

  const resetDraft = React.useCallback(() => {
    setCandidateQuery('');
    setCandidateUserId('');
    setCandidateRole('viewer');
    setCandidates([]);
    setCandidatePickerOpen(false);
  }, []);

  const handleCreateShare = React.useCallback(async () => {
    if (!candidateUserId || !canManageSharing) {
      return;
    }

    setError(null);
    try {
      await createKnowledgeBaseShare(knowledgeBaseId, {
        userId: candidateUserId,
        role: candidateRole,
      });
      const label = selectedCandidate?.displayName || selectedCandidate?.email || candidateUserId;
      toast({
        title: t('knowledgeBase.sharing.createSuccessTitle'),
        description: t('knowledgeBase.sharing.createSuccessDescription', { name: label, role: roleLabel(candidateRole) }),
      });
      setIsAddDialogOpen(false);
      resetDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.sharing.createFailed'));
    }
  }, [candidateRole, candidateUserId, canManageSharing, createKnowledgeBaseShare, knowledgeBaseId, resetDraft, roleLabel, selectedCandidate, t, toast]);

  const handleUpdateRole = React.useCallback(async (shareId: string, role: ShareRole) => {
    setBusyShareId(shareId);
    setError(null);
    try {
      await updateKnowledgeBaseShare(knowledgeBaseId, shareId, { role });
      toast({
        title: t('knowledgeBase.sharing.updateSuccessTitle'),
        description: t('knowledgeBase.sharing.updateSuccessDescription', { role: roleLabel(role) }),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.sharing.updateFailed'));
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
        description: share.userId,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.sharing.deleteFailed'));
    } finally {
      setBusyShareId(null);
    }
  }, [deleteKnowledgeBaseShare, knowledgeBaseId, t, toast]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Share2 className="h-4 w-4 text-sky-600" />
              {t('knowledgeBase.sharing.title')}
            </CardTitle>
            <CardDescription>{t('knowledgeBase.sharing.description')}</CardDescription>
          </div>
          {canManageSharing ? (
            <Button
              size="sm"
              onClick={() => {
                setError(null);
                setIsAddDialogOpen(true);
              }}
            >
              <UserPlus className="mr-2 h-4 w-4" />
              {t('knowledgeBase.sharing.addAction')}
            </Button>
          ) : (
            <Badge variant="outline" className="w-fit gap-1">
              <Shield className="h-3.5 w-3.5" />
              {t('knowledgeBase.sharing.readOnlyBadge')}
            </Badge>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {!canManageSharing ? (
            <div className="rounded-lg border border-dashed bg-muted/40 p-4 text-sm text-muted-foreground">
              {t('knowledgeBase.sharing.readOnlyNotice')}
            </div>
          ) : null}

          {shares.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-sm text-muted-foreground">
              {t('knowledgeBase.sharing.empty')}
            </div>
          ) : (
            <div className="space-y-3">
              {shares.map((share) => (
                <div
                  key={share.id}
                  className="flex flex-col gap-3 rounded-xl border border-border/60 bg-card/60 p-4 md:flex-row md:items-center md:justify-between"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium text-foreground">{share.userId}</span>
                      <Badge variant={ROLE_BADGE_VARIANT[share.role]}>{roleLabel(share.role)}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('knowledgeBase.sharing.table.grantedBy')}: {share.grantedById} · {t('knowledgeBase.sharing.table.grantedAt')}: {formatDateTime(share.createdAt)}
                    </div>
                  </div>

                  {canManageSharing ? (
                    <div className="flex items-center gap-2">
                      <Select
                        value={share.role}
                        onValueChange={(value: ShareRole) => {
                          if (value !== share.role) {
                            void handleUpdateRole(share.id, value);
                          }
                        }}
                        disabled={isMutating || busyShareId === share.id}
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
                        disabled={isMutating || busyShareId === share.id}
                        onClick={() => {
                          void handleDeleteShare(share);
                        }}
                      >
                        <X className="mr-2 h-4 w-4" />
                        {t('knowledgeBase.sharing.table.removeLabel')}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
            <DialogTitle>{t('knowledgeBase.sharing.candidate.title')}</DialogTitle>
            <DialogDescription>{t('knowledgeBase.sharing.candidate.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="kb-share-user">{t('knowledgeBase.sharing.candidate.userLabel')}</Label>
              <Popover open={candidatePickerOpen} onOpenChange={setCandidatePickerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="kb-share-user"
                    type="button"
                    variant="outline"
                    role="combobox"
                    className={cn(
                      'w-full justify-between font-normal',
                      !selectedCandidate && !candidateQuery && 'text-muted-foreground',
                    )}
                  >
                    {selectedCandidate
                      ? (selectedCandidate.displayName || selectedCandidate.email)
                      : candidateQuery || t('knowledgeBase.sharing.candidate.userPlaceholder')}
                    <UserPlus className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder={t('knowledgeBase.sharing.candidate.userPlaceholder')}
                      value={candidateQuery}
                      onValueChange={(value) => {
                        setCandidateQuery(value);
                        if (!value.trim()) {
                          setCandidateUserId('');
                        }
                      }}
                    />
                    <CommandList>
                      {isSearchingUsers ? (
                        <div className="px-3 py-6 text-sm text-muted-foreground">{t('workspace.workspaceSettings.access.sharing.searching')}</div>
                      ) : null}
                      {!isSearchingUsers && candidateQuery.trim().length === 0 ? (
                        <CommandEmpty>{t('workspace.workspaceSettings.access.sharing.startTyping')}</CommandEmpty>
                      ) : null}
                      {!isSearchingUsers && candidateQuery.trim().length > 0 && autocompleteCandidates.length === 0 ? (
                        <CommandEmpty>{t('knowledgeBase.sharing.candidate.userEmpty')}</CommandEmpty>
                      ) : null}
                      {autocompleteCandidates.length > 0 ? (
                        <CommandGroup heading={t('workspace.workspaceSettings.access.sharing.searchPlaceholder')}>
                          {autocompleteCandidates.map((candidate) => (
                            <CommandItem
                              key={candidate.id}
                              value={candidate.id}
                              onSelect={() => {
                                setCandidateUserId(candidate.id);
                                setCandidateQuery(candidate.email);
                                setCandidatePickerOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  'h-4 w-4',
                                  candidate.id === candidateUserId ? 'opacity-100' : 'opacity-0',
                                )}
                              />
                              <div className="min-w-0">
                                <div className="truncate font-medium">
                                  {candidate.displayName || candidate.email}
                                </div>
                                <div className="truncate text-xs text-muted-foreground">
                                  {candidate.email}
                                  {candidate.username ? ` · ${candidate.username}` : ''}
                                </div>
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
            <Button onClick={() => { void handleCreateShare(); }} disabled={!candidateUserId || isMutating}>
              {t('knowledgeBase.sharing.candidate.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default KnowledgeBaseSharingTab;
