import React, { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, Settings, UserRound, UsersRound } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { apiClient } from '@/shared/api/apiClient';
import { cn } from '@/shared/utils/cn';
import type {
  WorkspaceDetailResponse,
  WorkspaceShareListResponse,
  WorkspaceShareResponse,
  WorkspaceShareTargetType,
} from '@/features/workspace/api/workspaceApiTypes';
import { WORKSPACE_ACCESS_SOURCE_BADGE_KEYS } from '@/features/workspace/model/workspaceTypes';

interface WorkspaceShareDraft {
  targetType: WorkspaceShareTargetType;
  targetId: string;
  query: string;
  role: 'reader' | 'manager';
}

interface WorkspaceShareCandidate {
  id: string;
  label: string;
}

interface WorkspaceShareCandidateListResponse {
  items?: WorkspaceShareCandidate[];
}

export const WorkspaceAccessSettings: React.FC = () => {
  const { t } = useI18n();
  const { workspaceRuntime, permissions } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;
  const canManageSharing = permissions.canManageSettings;

  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetailResponse | null>(null);
  const [shares, setShares] = useState<WorkspaceShareResponse[]>([]);
  const [candidates, setCandidates] = useState<WorkspaceShareCandidate[]>([]);
  const [shareDraft, setShareDraft] = useState<WorkspaceShareDraft>({
    targetType: 'user',
    targetId: '',
    query: '',
    role: 'reader',
  });
  const [targetPickerOpen, setTargetPickerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sharesLoading, setSharesLoading] = useState(false);
  const [isSearchingCandidates, setIsSearchingCandidates] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sharingBusyId, setSharingBusyId] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const load = async () => {
      if (!workspaceId) {
        setWorkspaceDetail(null);
        setShares([]);
        setError(null);
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const detail = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`
        );
        if (!isActive) {
          return;
        }
        setWorkspaceDetail(detail);

        if (!canManageSharing) {
          setShares([]);
          return;
        }

        setSharesLoading(true);
        const shareList = await apiClient.get<WorkspaceShareListResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/shares`
        );
        if (!isActive) {
          return;
        }
        setShares(shareList.items ?? []);

      } catch (err) {
        if (!isActive) {
          return;
        }
        setWorkspaceDetail(null);
        setShares([]);
        setCandidates([]);
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.access.notifications.loadFailed')
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
          setSharesLoading(false);
        }
      }
    };

    void load();

    return () => {
      isActive = false;
    };
  }, [canManageSharing, workspaceId, t]);

  const accessRole = permissions.accessRole;
  const accessSource = workspaceDetail?.accessSource;

  useEffect(() => {
    if (!canManageSharing || !targetPickerOpen) {
      setCandidates([]);
      setIsSearchingCandidates(false);
      return;
    }

    const query = shareDraft.query.trim();
    if (!query) {
      setCandidates([]);
      setIsSearchingCandidates(false);
      return;
    }

    let isActive = true;
    setIsSearchingCandidates(true);
    const timer = window.setTimeout(async () => {
      try {
        const targetPath = shareDraft.targetType === 'user'
          ? 'share-candidate-users'
          : 'share-candidate-groups';
        const response = await apiClient.get<WorkspaceShareCandidateListResponse>(
          `/workspaces/${encodeURIComponent(workspaceId ?? '')}/${targetPath}?query=${encodeURIComponent(query)}&limit=8`
        );
        if (!isActive) {
          return;
        }
        setCandidates(response.items ?? []);
      } catch (err) {
        if (!isActive) {
          return;
        }
        setCandidates([]);
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.access.notifications.candidateSearchFailed')
        );
      } finally {
        if (isActive) {
          setIsSearchingCandidates(false);
        }
      }
    }, 250);

    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [canManageSharing, shareDraft.query, shareDraft.targetType, t, targetPickerOpen, workspaceId]);

  const autocompleteCandidates = useMemo(
    () => candidates.filter((candidate) => !shares.some(
      (share) => share.targetType === shareDraft.targetType && share.targetId === candidate.id,
    )),
    [candidates, shareDraft.targetType, shares],
  );

  const handleCreateShare = async () => {
    if (!workspaceId || !shareDraft.targetId || !canManageSharing) {
      return;
    }

    setSharingBusyId('create');
    setError(null);
    try {
      const created = await apiClient.post<WorkspaceShareResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/shares`,
        {
          targetType: shareDraft.targetType,
          targetId: shareDraft.targetId,
          role: shareDraft.role,
        }
      );
      setShares((current) => [...current, created]);
      setShareDraft({ targetType: 'user', targetId: '', query: '', role: 'reader' });
      setCandidates([]);
      setTargetPickerOpen(false);
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.access.notifications.createFailed')
      );
    } finally {
      setSharingBusyId(null);
    }
  };

  const handleShareRoleChange = async (
    shareId: string,
    role: WorkspaceShareResponse['role']
  ) => {
    if (!workspaceId || !canManageSharing) {
      return;
    }

    setSharingBusyId(shareId);
    setError(null);
    try {
      const updated = await apiClient.patch<WorkspaceShareResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/shares/${encodeURIComponent(shareId)}`,
        { role }
      );
      setShares((current) =>
        current.map((share) => (share.id === shareId ? updated : share))
      );
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.access.notifications.updateFailed')
      );
    } finally {
      setSharingBusyId(null);
    }
  };

  const handleDeleteShare = async (shareId: string) => {
    if (!workspaceId || !canManageSharing) {
      return;
    }

    setSharingBusyId(shareId);
    setError(null);
    try {
      await apiClient.delete(
        `/workspaces/${encodeURIComponent(workspaceId)}/shares/${encodeURIComponent(shareId)}`
      );
      setShares((current) => current.filter((share) => share.id !== shareId));
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.access.notifications.deleteFailed')
      );
    } finally {
      setSharingBusyId(null);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <FeatureHeader title={t('workspace.workspaceSettings.access.header.title')} icon={Settings} />
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {error ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          ) : null}

          {isLoading ? (
            <p className="text-sm text-muted-foreground">
              {t('workspace.workspaceSettings.access.status.loading')}
            </p>
          ) : workspaceDetail ? (
            <>
              <div className="space-y-3 rounded-lg border border-border/60 bg-card/70 p-4">
                <div>
                  <h3 className="text-sm font-semibold">
                    {t('workspace.workspaceSettings.access.currentAccess.title')}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.workspaceSettings.access.currentAccess.description')}
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.access.currentAccess.ownerLabel')}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {workspaceDetail.owner?.displayName ??
                          t('workspace.workspaceSettings.access.currentAccess.unknownOwner')}
                      </span>
                      {workspaceDetail.owner?.email ? (
                        <span className="text-xs text-muted-foreground">
                          {workspaceDetail.owner.email}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.access.currentAccess.yourAccessLabel')}
                    </p>
                    {accessRole ? (
                      <Badge variant="secondary" className="w-fit text-[11px] uppercase">
                        {accessSource
                          ? t(WORKSPACE_ACCESS_SOURCE_BADGE_KEYS[accessSource], {
                              role: t(`workspace.workspaceSettings.access.roles.${accessRole}`),
                            })
                          : null}
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </div>

              {(
                <div className="space-y-3 rounded-lg border border-border/60 bg-card/70 p-4">
                  <div>
                    <h3 className="text-sm font-semibold">
                      {t('workspace.workspaceSettings.access.sharing.title')}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.access.sharing.description')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        type="button"
                        variant={shareDraft.targetType === 'user' ? 'default' : 'outline'}
                        onClick={() => {
                          setShareDraft((current) => ({
                            ...current,
                            targetType: 'user',
                            targetId: '',
                            query: '',
                          }));
                          setCandidates([]);
                        }}
                        disabled={!canManageSharing || sharingBusyId === 'create'}
                      >
                        <UserRound className="mr-2 h-4 w-4" />
                        {t('workspace.workspaceSettings.access.sharing.targetTypes.user')}
                      </Button>
                      <Button
                        type="button"
                        variant={shareDraft.targetType === 'user_group' ? 'default' : 'outline'}
                        onClick={() => {
                          setShareDraft((current) => ({
                            ...current,
                            targetType: 'user_group',
                            targetId: '',
                            query: '',
                          }));
                          setCandidates([]);
                        }}
                        disabled={!canManageSharing || sharingBusyId === 'create'}
                      >
                        <UsersRound className="mr-2 h-4 w-4" />
                        {t('workspace.workspaceSettings.access.sharing.targetTypes.group')}
                      </Button>
                    </div>
                    <div className="grid items-end gap-3 md:grid-cols-[minmax(0,2fr)_180px_auto]">
                    <div className="space-y-2">
                      <Label htmlFor="share-target-trigger">
                        {t('workspace.workspaceSettings.access.sharing.targetLabel')}
                      </Label>
                      <Popover open={targetPickerOpen} onOpenChange={setTargetPickerOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            id="share-target-trigger"
                            variant="outline"
                            role="combobox"
                            aria-label={t('workspace.workspaceSettings.access.sharing.targetLabel')}
                            aria-expanded={targetPickerOpen}
                            className="w-full justify-between font-normal"
                            disabled={!canManageSharing || sharingBusyId === 'create'}
                          >
                            <span className="truncate">
                              {shareDraft.query ||
                                t('workspace.workspaceSettings.access.sharing.targetPlaceholder')}
                            </span>
                            <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
                          <Command shouldFilter={false}>
                            <CommandInput
                              value={shareDraft.query}
                              onValueChange={(value) =>
                                setShareDraft((current) => ({
                                  ...current,
                                  targetId: '',
                                  query: value,
                                }))
                              }
                              placeholder={t(
                                'workspace.workspaceSettings.access.sharing.searchPlaceholder'
                              )}
                            />
                            <CommandList>
                              {isSearchingCandidates ? (
                                <div className="px-3 py-2 text-xs text-muted-foreground">
                                  {t('workspace.workspaceSettings.access.sharing.searching')}
                                </div>
                              ) : null}
                              <CommandEmpty>
                                {shareDraft.query.trim()
                                  ? t('workspace.workspaceSettings.access.sharing.noMatches')
                                  : t('workspace.workspaceSettings.access.sharing.startTyping')}
                              </CommandEmpty>
                              <CommandGroup>
                                {autocompleteCandidates.slice(0, 8).map((candidate) => (
                                    <CommandItem
                                      key={candidate.id}
                                      value={candidate.id}
                                      onSelect={() => {
                                        setShareDraft((current) => ({
                                          ...current,
                                          targetId: candidate.id,
                                          query: candidate.label,
                                        }));
                                        setTargetPickerOpen(false);
                                      }}
                                    >
                                      <Check
                                        className={cn(
                                          'h-4 w-4 shrink-0',
                                          shareDraft.targetId === candidate.id
                                            ? 'opacity-100'
                                            : 'opacity-0'
                                        )}
                                      />
                                      <span className="truncate">{candidate.label}</span>
                                    </CommandItem>
                                ))}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('workspace.workspaceSettings.access.sharing.roleLabel')}</Label>
                      <Select
                        value={shareDraft.role}
                        onValueChange={(value) =>
                          setShareDraft((current) => ({
                            ...current,
                            role: value as WorkspaceShareResponse['role'],
                          }))
                        }
                        disabled={!canManageSharing || sharingBusyId === 'create'}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="reader">
                            {t('workspace.workspaceSettings.access.roles.reader')}
                          </SelectItem>
                          <SelectItem value="manager">
                            {t('workspace.workspaceSettings.access.roles.manager')}
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-end">
                      <Button
                        variant="outline"
                        className="w-full md:w-auto"
                        onClick={handleCreateShare}
                        disabled={!canManageSharing || !shareDraft.targetId || sharingBusyId === 'create'}
                      >
                        {t('workspace.workspaceSettings.access.sharing.addAction')}
                      </Button>
                    </div>
                  </div>
                  </div>

                  <div className="space-y-2">
                    {sharesLoading ? (
                      <p className="text-sm text-muted-foreground">
                        {t('workspace.workspaceSettings.access.sharing.loading')}
                      </p>
                    ) : shares.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        {t('workspace.workspaceSettings.access.sharing.empty')}
                      </p>
                    ) : (
                      shares.map((share) => (
                        <div
                          key={share.id}
                          className="grid gap-3 rounded-md border border-border/60 bg-background/70 p-3 md:grid-cols-[minmax(0,2fr)_180px_auto]"
                        >
                          <div className="space-y-1">
                            <p className="text-sm font-medium">{share.targetLabel}</p>
                            <p className="text-xs text-muted-foreground">
                              {t(`workspace.workspaceSettings.access.sharing.targetTypes.${share.targetType === 'user_group' ? 'group' : 'user'}`)}
                            </p>
                          </div>
                          <Select
                            value={share.role}
                            onValueChange={(value) =>
                              void handleShareRoleChange(
                                share.id,
                                value as WorkspaceShareResponse['role']
                              )
                            }
                            disabled={!canManageSharing || sharingBusyId === share.id}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="reader">
                                {t('workspace.workspaceSettings.access.roles.reader')}
                              </SelectItem>
                              <SelectItem value="manager">
                                {t('workspace.workspaceSettings.access.roles.manager')}
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <div className="flex items-center justify-end">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void handleDeleteShare(share.id)}
                              disabled={!canManageSharing || sharingBusyId === share.id}
                            >
                              {t('workspace.workspaceSettings.access.sharing.removeAction')}
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('workspace.workspaceSettings.access.status.unavailable')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
