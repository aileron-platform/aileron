import React, { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, Settings } from 'lucide-react';
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
} from '@/features/workspace/providers/workspaceState.types';

interface WorkspaceShareDraft {
  email: string;
  role: 'viewer' | 'editor' | 'manager';
}

interface UserDirectoryResponse {
  items?: Array<{
    id: string;
    email: string;
    username?: string | null;
    displayName?: string | null;
  }>;
}

export const WorkspaceAccessSettings: React.FC = () => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;

  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetailResponse | null>(null);
  const [shares, setShares] = useState<WorkspaceShareResponse[]>([]);
  const [userDirectory, setUserDirectory] = useState<UserDirectoryResponse['items']>([]);
  const [shareDraft, setShareDraft] = useState<WorkspaceShareDraft>({
    email: '',
    role: 'viewer',
  });
  const [emailPickerOpen, setEmailPickerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sharesLoading, setSharesLoading] = useState(false);
  const [isSearchingUsers, setIsSearchingUsers] = useState(false);
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

        const canManageSharing =
          detail.accessRole === 'owner' || detail.accessRole === 'manager';
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
        setUserDirectory([]);
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
  }, [workspaceId, t]);

  const accessRole = workspaceDetail?.accessRole ?? 'owner';
  const accessSource = workspaceDetail?.accessSource ?? 'owned';
  const canManageSharing = accessRole === 'owner' || accessRole === 'manager';

  useEffect(() => {
    if (!canManageSharing || !emailPickerOpen) {
      setUserDirectory([]);
      setIsSearchingUsers(false);
      return;
    }

    const query = shareDraft.email.trim();
    if (!query) {
      setUserDirectory([]);
      setIsSearchingUsers(false);
      return;
    }

    let isActive = true;
    setIsSearchingUsers(true);
    const timer = window.setTimeout(async () => {
      try {
        const users = await apiClient.get<UserDirectoryResponse>(
          `/users?query=${encodeURIComponent(query)}&limit=8`
        );
        if (!isActive) {
          return;
        }
        setUserDirectory(users.items ?? []);
      } catch (err) {
        if (!isActive) {
          return;
        }
        setUserDirectory([]);
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.access.notifications.userSearchFailed')
        );
      } finally {
        if (isActive) {
          setIsSearchingUsers(false);
        }
      }
    }, 250);

    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [canManageSharing, emailPickerOpen, shareDraft.email, t]);

  const autocompleteCandidates = useMemo(
    () =>
      userDirectory.filter((user) => {
        const normalizedQuery = shareDraft.email.trim().toLowerCase();
        const normalizedEmail = user.email.toLowerCase();
        const matchesQuery =
          normalizedQuery.length === 0 ||
          normalizedEmail.includes(normalizedQuery) ||
          (user.displayName ?? '').toLowerCase().includes(normalizedQuery) ||
          (user.username ?? '').toLowerCase().includes(normalizedQuery);

        if (!matchesQuery) {
          return false;
        }

        if (workspaceDetail?.owner?.email?.toLowerCase() === normalizedEmail) {
          return false;
        }

        return !shares.some((share) => share.user.email?.toLowerCase() === normalizedEmail);
      }),
    [shareDraft.email, shares, userDirectory, workspaceDetail?.owner?.email]
  );

  const handleCreateShare = async () => {
    if (!workspaceId || !shareDraft.email.trim() || !canManageSharing) {
      return;
    }

    setSharingBusyId('create');
    setError(null);
    try {
      const created = await apiClient.post<WorkspaceShareResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/shares`,
        {
          email: shareDraft.email.trim(),
          role: shareDraft.role,
        }
      );
      setShares((current) => [...current, created]);
      setShareDraft({ email: '', role: 'viewer' });
      setUserDirectory([]);
      setEmailPickerOpen(false);
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
                    <Badge variant="secondary" className="w-fit text-[11px] uppercase">
                      {accessSource === 'shared'
                        ? t('workspace.workspaceSettings.access.badges.shared', {
                            role: t(`workspace.workspaceSettings.access.roles.${accessRole}`),
                          })
                        : t('workspace.workspaceSettings.access.badges.owned')}
                    </Badge>
                  </div>
                </div>
              </div>

              {canManageSharing ? (
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
                    <div className="grid items-end gap-3 md:grid-cols-[minmax(0,2fr)_180px_auto]">
                    <div className="space-y-2">
                      <Label htmlFor="share-user-email-trigger">
                        {t('workspace.workspaceSettings.access.sharing.emailLabel')}
                      </Label>
                      <Popover open={emailPickerOpen} onOpenChange={setEmailPickerOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            id="share-user-email-trigger"
                            variant="outline"
                            role="combobox"
                            aria-label={t('workspace.workspaceSettings.access.sharing.emailLabel')}
                            aria-expanded={emailPickerOpen}
                            className="w-full justify-between font-normal"
                            disabled={sharingBusyId === 'create'}
                          >
                            <span className="truncate">
                              {shareDraft.email ||
                                t('workspace.workspaceSettings.access.sharing.emailPlaceholder')}
                            </span>
                            <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
                          <Command shouldFilter={false}>
                            <CommandInput
                              value={shareDraft.email}
                              onValueChange={(value) =>
                                setShareDraft((current) => ({ ...current, email: value }))
                              }
                              placeholder={t(
                                'workspace.workspaceSettings.access.sharing.searchPlaceholder'
                              )}
                            />
                            <CommandList>
                              {isSearchingUsers ? (
                                <div className="px-3 py-2 text-xs text-muted-foreground">
                                  {t('workspace.workspaceSettings.access.sharing.searching')}
                                </div>
                              ) : null}
                              <CommandEmpty>
                                {shareDraft.email.trim()
                                  ? t('workspace.workspaceSettings.access.sharing.noMatches')
                                  : t('workspace.workspaceSettings.access.sharing.startTyping')}
                              </CommandEmpty>
                              <CommandGroup>
                                {autocompleteCandidates.slice(0, 8).map((user) => {
                                  const secondaryLine = [user.email, user.username]
                                    .filter(Boolean)
                                    .join(' · ');

                                  return (
                                    <CommandItem
                                      key={user.id}
                                      value={`${user.displayName ?? ''} ${user.email} ${user.username ?? ''}`}
                                      onSelect={() => {
                                        setShareDraft((current) => ({
                                          ...current,
                                          email: user.email,
                                        }));
                                        setEmailPickerOpen(false);
                                      }}
                                      className="items-start"
                                    >
                                      <Check
                                        className={cn(
                                          'mt-1 h-4 w-4 shrink-0',
                                          shareDraft.email.toLowerCase() === user.email.toLowerCase()
                                            ? 'opacity-100'
                                            : 'opacity-0'
                                        )}
                                      />
                                      <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-medium">
                                          {user.displayName || user.email}
                                        </p>
                                        <p className="truncate text-xs text-muted-foreground">
                                          {secondaryLine}
                                        </p>
                                      </div>
                                    </CommandItem>
                                  );
                                })}
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
                        disabled={sharingBusyId === 'create'}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="viewer">
                            {t('workspace.workspaceSettings.access.roles.viewer')}
                          </SelectItem>
                          <SelectItem value="editor">
                            {t('workspace.workspaceSettings.access.roles.editor')}
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
                        disabled={!shareDraft.email.trim() || sharingBusyId === 'create'}
                      >
                        {t('workspace.workspaceSettings.access.sharing.addAction')}
                      </Button>
                    </div>
                  </div>
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.access.sharing.emailAutocompleteHint')}
                    </p>
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
                            <p className="text-sm font-medium">{share.user.displayName}</p>
                            <p className="text-xs text-muted-foreground">
                              {share.user.email || share.user.username || share.user.id}
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
                            disabled={sharingBusyId === share.id}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="viewer">
                                {t('workspace.workspaceSettings.access.roles.viewer')}
                              </SelectItem>
                              <SelectItem value="editor">
                                {t('workspace.workspaceSettings.access.roles.editor')}
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
                              disabled={sharingBusyId === share.id}
                            >
                              {t('workspace.workspaceSettings.access.sharing.removeAction')}
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                  {t('workspace.workspaceSettings.access.readOnlyNotice')}
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
