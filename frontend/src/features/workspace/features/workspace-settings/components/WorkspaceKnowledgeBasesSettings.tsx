import React from 'react';
import { Check, Database, FolderTree, Link2, Plus, Unplug, Workflow } from 'lucide-react';
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
import { Input } from '@/shared/components/ui/input';
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
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type {
  KnowledgeBaseAttachmentMode,
  KnowledgeBaseSummary,
  WorkspaceKnowledgeBaseAttachmentSummary,
} from '@/shared/types/knowledgeBase';
import type { WorkspaceDetailResponse } from '@/features/workspace/providers/workspaceState.types';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { MountedKnowledgeBasesPanel } from '@/features/workspace/components/MountedKnowledgeBasesPanel';

export const WorkspaceKnowledgeBasesSettings: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;
  const [workspaceDetail, setWorkspaceDetail] = React.useState<WorkspaceDetailResponse | null>(null);
  const [availableKnowledgeBases, setAvailableKnowledgeBases] = React.useState<KnowledgeBaseSummary[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isMutating, setIsMutating] = React.useState(false);
  const [busyAttachmentId, setBusyAttachmentId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isAttachDialogOpen, setIsAttachDialogOpen] = React.useState(false);
  const [knowledgeBasePickerOpen, setKnowledgeBasePickerOpen] = React.useState(false);
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = React.useState('');
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = React.useState('');
  const [mountAlias, setMountAlias] = React.useState('');
  const [mode, setMode] = React.useState<KnowledgeBaseAttachmentMode>('rw');

  const loadWorkspaceDetail = React.useCallback(async () => {
    if (!workspaceId) {
      setWorkspaceDetail(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const detail = await apiClient.get<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
      );
      setWorkspaceDetail(detail);
    } catch (err) {
      setWorkspaceDetail(null);
      setError(
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.knowledgeBases.notifications.loadFailed'),
      );
    } finally {
      setIsLoading(false);
    }
  }, [t, workspaceId]);

  React.useEffect(() => {
    void loadWorkspaceDetail();
  }, [loadWorkspaceDetail]);

  React.useEffect(() => {
    if (!isAttachDialogOpen) {
      setAvailableKnowledgeBases([]);
      return;
    }

    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiClient.get<{ items: KnowledgeBaseSummary[] }>('/knowledge-bases');
        if (!active) {
          return;
        }
        setAvailableKnowledgeBases(response.items ?? []);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.knowledgeBases.notifications.loadFailed'),
        );
      }
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [isAttachDialogOpen, t]);

  const attachments = workspaceDetail?.attachedKnowledgeBases ?? [];
  const accessRole = workspaceDetail?.accessRole ?? 'owner';
  const canManageAttachments = accessRole === 'owner' || accessRole === 'manager' || accessRole === 'editor';
  const selectedKnowledgeBase = availableKnowledgeBases.find((kb) => kb.id === selectedKnowledgeBaseId);
  const selectedKnowledgeBaseRole = selectedKnowledgeBase?.accessRole ?? null;
  const canEditMode = selectedKnowledgeBaseRole !== 'viewer';
  const modeLabel = React.useCallback(
    (value: KnowledgeBaseAttachmentMode) => t(`knowledgeBase.common.mode.${value}`),
    [t],
  );

  React.useEffect(() => {
    if (!canEditMode) {
      setMode('ro');
    }
  }, [canEditMode]);

  const filteredKnowledgeBases = React.useMemo(() => {
    const query = knowledgeBaseQuery.trim().toLowerCase();
    return availableKnowledgeBases.filter((kb) => {
      if (attachments.some((attachment) => attachment.kbId === kb.id)) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [kb.name, kb.slug, kb.description ?? ''].some((value) =>
        value.toLowerCase().includes(query),
      );
    });
  }, [attachments, availableKnowledgeBases, knowledgeBaseQuery]);

  const resetDraft = React.useCallback(() => {
    setKnowledgeBasePickerOpen(false);
    setKnowledgeBaseQuery('');
    setSelectedKnowledgeBaseId('');
    setMountAlias('');
    setMode('rw');
  }, []);

  const handleAttach = React.useCallback(async () => {
    if (!workspaceId || !selectedKnowledgeBaseId || !canManageAttachments) {
      return;
    }

    setIsMutating(true);
    setError(null);
    try {
      await apiClient.post(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases`,
        {
          kbId: selectedKnowledgeBaseId,
          mountAlias: mountAlias.trim() || undefined,
          mode: canEditMode ? mode : 'ro',
        },
      );
      await loadWorkspaceDetail();
      setIsAttachDialogOpen(false);
      resetDraft();
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.notifications.attachSuccessTitle'),
        description: selectedKnowledgeBase?.name ?? selectedKnowledgeBaseId,
      });
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.knowledgeBases.notifications.attachFailed'),
      );
    } finally {
      setIsMutating(false);
    }
  }, [
    canEditMode,
    canManageAttachments,
    loadWorkspaceDetail,
    mode,
    mountAlias,
    resetDraft,
    selectedKnowledgeBase?.name,
    selectedKnowledgeBaseId,
    t,
    toast,
    workspaceId,
  ]);

  const handleModeUpdate = React.useCallback(
    async (attachmentId: string, attachment: WorkspaceKnowledgeBaseAttachmentSummary, nextMode: KnowledgeBaseAttachmentMode) => {
      if (!workspaceId || !canManageAttachments) {
        return;
      }

      setBusyAttachmentId(attachmentId);
      setError(null);
      try {
        await apiClient.patch(
          `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases/${encodeURIComponent(attachmentId)}`,
          {
            mode: attachment.role === 'viewer' ? 'ro' : nextMode,
          },
        );
        await loadWorkspaceDetail();
        toast({
          title: t('workspace.workspaceSettings.knowledgeBases.notifications.modeUpdatedTitle'),
          description: modeLabel(attachment.role === 'viewer' ? 'ro' : nextMode),
        });
      } catch (err) {
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.knowledgeBases.notifications.updateFailed'),
        );
      } finally {
        setBusyAttachmentId(null);
      }
    },
    [canManageAttachments, loadWorkspaceDetail, modeLabel, t, toast, workspaceId],
  );

  const handleDetach = React.useCallback(
    async (attachmentId: string, attachmentName: string) => {
      if (!workspaceId || !canManageAttachments) {
        return;
      }

      setBusyAttachmentId(attachmentId);
      setError(null);
      try {
        await apiClient.delete(
          `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases/${encodeURIComponent(attachmentId)}`,
        );
        await loadWorkspaceDetail();
        toast({
          title: t('workspace.workspaceSettings.knowledgeBases.notifications.detachSuccessTitle'),
          description: attachmentName,
        });
      } catch (err) {
        setError(
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.knowledgeBases.notifications.detachFailed'),
        );
      } finally {
        setBusyAttachmentId(null);
      }
    },
    [canManageAttachments, loadWorkspaceDetail, t, toast, workspaceId],
  );

  return (
    <div className="h-full flex flex-col">
      <FeatureHeader
        title={t('workspace.workspaceSettings.knowledgeBases.header.title')}
        icon={Database}
      />
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
          <MountedKnowledgeBasesPanel
            workspaceId={workspaceId}
            attachments={attachments}
            mountedKbSignature={workspaceDetail?.mountedKbSignature}
            hasPendingKbChanges={workspaceDetail?.hasPendingKbChanges}
            onRefresh={loadWorkspaceDetail}
          />

          <Card>
            <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Link2 className="h-4 w-4 text-sky-600" />
                  {t('workspace.workspaceSettings.knowledgeBases.desired.title')}
                </CardTitle>
                <CardDescription>
                  {t('workspace.workspaceSettings.knowledgeBases.desired.description')}
                </CardDescription>
              </div>
              {canManageAttachments ? (
                <Button
                  size="sm"
                  onClick={() => {
                    setError(null);
                    setIsAttachDialogOpen(true);
                  }}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.workspaceSettings.knowledgeBases.desired.attachAction')}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {error ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              {!canManageAttachments ? (
                <div className="rounded-lg border border-dashed bg-muted/40 p-4 text-sm text-muted-foreground">
                  {t('workspace.workspaceSettings.knowledgeBases.readOnlyNotice')}
                </div>
              ) : null}

              {isLoading ? (
                <div className="rounded-lg border border-dashed bg-muted/40 p-5 text-sm text-muted-foreground">
                  {t('workspace.workspaceSettings.knowledgeBases.status.loading')}
                </div>
              ) : attachments.length === 0 ? (
                <div className="rounded-lg border border-dashed bg-muted/40 p-5 text-sm text-muted-foreground">
                  {t('workspace.workspaceSettings.knowledgeBases.desired.empty')}
                </div>
              ) : (
                <div className="-mx-4 divide-y divide-border/60 border-y border-border/60 sm:-mx-6">
                  {attachments.map((attachment) => {
                    const modeLocked = attachment.role === 'viewer';
                    return (
                      <div key={attachment.id} className="space-y-3 px-4 py-4 sm:px-6">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <Database className="h-4 w-4 shrink-0 text-sky-600" />
                            <span className="truncate font-medium text-foreground">
                              {attachment.name}
                            </span>
                            <Badge variant="outline">{attachment.slug}</Badge>
                            {attachment.role ? (
                              <Badge variant="outline">{attachment.role}</Badge>
                            ) : null}
                          </div>
                          {canManageAttachments ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={isMutating || busyAttachmentId === attachment.id}
                              onClick={() => {
                                void handleDetach(attachment.id, attachment.name);
                              }}
                            >
                              <Unplug className="mr-2 h-4 w-4" />
                              {t('workspace.workspaceSettings.knowledgeBases.desired.detachAction')}
                            </Button>
                          ) : null}
                        </div>

                        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                          <div className="space-y-2">
                            <Label htmlFor={`workspace-kb-alias-${attachment.id}`}>
                              {t('workspace.workspaceSettings.knowledgeBases.form.aliasLabel')}
                            </Label>
                            <Input
                              id={`workspace-kb-alias-${attachment.id}`}
                              value={attachment.mountAlias}
                              readOnly
                              disabled
                            />
                            <p className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground">
                              <FolderTree className="h-3.5 w-3.5" />
                              /knowledge/{attachment.mountAlias}
                            </p>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor={`workspace-kb-mode-${attachment.id}`}>
                              {t('workspace.workspaceSettings.knowledgeBases.form.modeLabel')}
                            </Label>
                            <Select
                              value={attachment.mode}
                              onValueChange={(value: KnowledgeBaseAttachmentMode) => {
                                if (value !== attachment.mode) {
                                  void handleModeUpdate(attachment.id, attachment, value);
                                }
                              }}
                              disabled={modeLocked || !canManageAttachments || isMutating || busyAttachmentId === attachment.id}
                            >
                              <SelectTrigger id={`workspace-kb-mode-${attachment.id}`}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="ro">{t('knowledgeBase.common.mode.ro')}</SelectItem>
                                <SelectItem value="rw">{t('knowledgeBase.common.mode.rw')}</SelectItem>
                              </SelectContent>
                            </Select>
                            {modeLocked ? (
                              <p className="text-xs text-muted-foreground">
                                {t('workspace.workspaceSettings.knowledgeBases.modeLocked')}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog
        open={isAttachDialogOpen}
        onOpenChange={(open) => {
          setIsAttachDialogOpen(open);
          if (!open) {
            resetDraft();
          }
        }}
      >
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-primary" />
              {t('workspace.workspaceSettings.knowledgeBases.dialog.title')}
            </DialogTitle>
            <DialogDescription>
              {t('workspace.workspaceSettings.knowledgeBases.dialog.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="workspace-kb-select">
                {t('workspace.workspaceSettings.knowledgeBases.form.knowledgeBaseLabel')}
              </Label>
              <Popover open={knowledgeBasePickerOpen} onOpenChange={setKnowledgeBasePickerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="workspace-kb-select"
                    type="button"
                    variant="outline"
                    role="combobox"
                    className={cn(
                      'w-full justify-between font-normal',
                      !selectedKnowledgeBaseId && 'text-muted-foreground',
                    )}
                  >
                    {selectedKnowledgeBase
                      ? `${selectedKnowledgeBase.name} (${selectedKnowledgeBase.slug})`
                      : t('workspace.workspaceSettings.knowledgeBases.dialog.placeholder')}
                    <Workflow className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder={t('workspace.workspaceSettings.knowledgeBases.dialog.searchPlaceholder')}
                      value={knowledgeBaseQuery}
                      onValueChange={setKnowledgeBaseQuery}
                    />
                    <CommandList>
                      {filteredKnowledgeBases.length === 0 ? (
                        <CommandEmpty>
                          {t('workspace.workspaceSettings.knowledgeBases.dialog.empty')}
                        </CommandEmpty>
                      ) : (
                        <CommandGroup heading={t('workspace.workspaceSettings.knowledgeBases.header.title')}>
                          {filteredKnowledgeBases.map((kb) => (
                            <CommandItem
                              key={kb.id}
                              value={kb.id}
                              onSelect={() => {
                                setSelectedKnowledgeBaseId(kb.id);
                                setKnowledgeBasePickerOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  'h-4 w-4',
                                  kb.id === selectedKnowledgeBaseId ? 'opacity-100' : 'opacity-0',
                                )}
                              />
                              <div className="min-w-0">
                                <div className="truncate font-medium">{kb.name}</div>
                                <div className="truncate text-xs text-muted-foreground">
                                  {kb.slug}
                                  {kb.accessRole ? ` · ${kb.accessRole}` : ''}
                                </div>
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      )}
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label htmlFor="workspace-kb-alias">
                {t('workspace.workspaceSettings.knowledgeBases.form.aliasLabel')}
              </Label>
              <Input
                id="workspace-kb-alias"
                value={mountAlias}
                onChange={(event) => setMountAlias(event.target.value)}
                placeholder={t('workspace.workspaceSettings.knowledgeBases.form.aliasPlaceholder')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="workspace-kb-mode">
                {t('workspace.workspaceSettings.knowledgeBases.form.modeLabel')}
              </Label>
              <Select
                value={canEditMode ? mode : 'ro'}
                onValueChange={(value: KnowledgeBaseAttachmentMode) => setMode(value)}
                disabled={!canEditMode}
              >
                <SelectTrigger id="workspace-kb-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ro">{t('knowledgeBase.common.mode.ro')}</SelectItem>
                  <SelectItem value="rw">{t('knowledgeBase.common.mode.rw')}</SelectItem>
                </SelectContent>
              </Select>
              {!canEditMode && selectedKnowledgeBaseId ? (
                <p className="text-xs text-muted-foreground">
                  {t('workspace.workspaceSettings.knowledgeBases.modeLocked')}
                </p>
              ) : null}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAttachDialogOpen(false)}>
              {t('workspace.workspaceSettings.knowledgeBases.dialog.cancel')}
            </Button>
            <Button
              onClick={() => {
                void handleAttach();
              }}
              disabled={!selectedKnowledgeBaseId || isMutating || !canManageAttachments}
            >
              {t('workspace.workspaceSettings.knowledgeBases.dialog.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WorkspaceKnowledgeBasesSettings;
