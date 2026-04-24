import React from 'react';
import { Check, Link2, Plus, Unplug, Workflow } from 'lucide-react';
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
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  KnowledgeBaseAttachmentMode,
  KnowledgeBaseRole,
} from '@/shared/types/knowledgeBase';
import { cn } from '@/shared/utils/cn';
import type { WorkspaceListResponse } from '@/features/workspace/providers/workspaceState.types';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

interface KnowledgeBaseAttachmentsTabProps {
  knowledgeBaseId: string;
  accessRole: KnowledgeBaseRole;
}

interface WorkspaceCandidate {
  id: string;
  name?: string;
  description?: string | null;
  accessRole?: 'owner' | 'manager' | 'editor' | 'viewer';
}

export const KnowledgeBaseAttachmentsTab: React.FC<KnowledgeBaseAttachmentsTabProps> = ({
  knowledgeBaseId,
  accessRole,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const {
    attachmentsById,
    isMutating,
    loadKnowledgeBaseAttachments,
    createKnowledgeBaseAttachment,
    updateKnowledgeBaseAttachment,
    deleteKnowledgeBaseAttachment,
  } = useKnowledgeBase();
  const [error, setError] = React.useState<string | null>(null);
  const [busyAttachmentId, setBusyAttachmentId] = React.useState<string | null>(null);
  const [isAttachDialogOpen, setIsAttachDialogOpen] = React.useState(false);
  const [workspacePickerOpen, setWorkspacePickerOpen] = React.useState(false);
  const [workspaceQuery, setWorkspaceQuery] = React.useState('');
  const [workspaceCandidates, setWorkspaceCandidates] = React.useState<WorkspaceCandidate[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = React.useState('');
  const [mountAlias, setMountAlias] = React.useState('');
  const [mode, setMode] = React.useState<KnowledgeBaseAttachmentMode>(accessRole === 'viewer' ? 'ro' : 'rw');

  const attachments = attachmentsById[knowledgeBaseId] ?? [];
  const canEditMode = accessRole !== 'viewer';
  const modeLabel = React.useCallback(
    (value: KnowledgeBaseAttachmentMode) => t(`knowledgeBase.common.mode.${value}`),
    [t],
  );

  React.useEffect(() => {
    if (attachmentsById[knowledgeBaseId] === undefined) {
      void loadKnowledgeBaseAttachments(knowledgeBaseId);
    }
  }, [attachmentsById, knowledgeBaseId, loadKnowledgeBaseAttachments]);

  React.useEffect(() => {
    if (!isAttachDialogOpen) {
      setWorkspaceCandidates([]);
      return;
    }

    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiClient.get<WorkspaceListResponse>('/workspaces/?page=1&pageSize=100');
        if (!active) {
          return;
        }
        setWorkspaceCandidates(response.items ?? []);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : t('knowledgeBase.attachments.loadWorkspacesFailed'));
      }
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [isAttachDialogOpen, t]);

  React.useEffect(() => {
    if (!canEditMode) {
      setMode('ro');
    }
  }, [canEditMode]);

  const workspaceMap = React.useMemo(
    () => Object.fromEntries(workspaceCandidates.map((workspace) => [workspace.id, workspace])),
    [workspaceCandidates],
  );

  const filteredCandidates = React.useMemo(() => {
    const query = workspaceQuery.trim().toLowerCase();
    return workspaceCandidates.filter((workspace) => {
      if (attachments.some((attachment) => attachment.workspaceId === workspace.id)) {
        return false;
      }

      if (!query) {
        return true;
      }

      return [
        workspace.name ?? '',
        workspace.id,
        workspace.description ?? '',
      ].some((value) => value.toLowerCase().includes(query));
    });
  }, [attachments, workspaceCandidates, workspaceQuery]);

  const resetDraft = React.useCallback(() => {
    setWorkspacePickerOpen(false);
    setWorkspaceQuery('');
    setSelectedWorkspaceId('');
    setMountAlias('');
    setMode(accessRole === 'viewer' ? 'ro' : 'rw');
  }, [accessRole]);

  const handleAttach = React.useCallback(async () => {
    if (!selectedWorkspaceId) {
      return;
    }

    setError(null);
    try {
      await createKnowledgeBaseAttachment(knowledgeBaseId, {
        workspaceId: selectedWorkspaceId,
        mountAlias: mountAlias.trim() || undefined,
        mode: canEditMode ? mode : 'ro',
      });
      const workspaceName = workspaceMap[selectedWorkspaceId]?.name || selectedWorkspaceId;
      toast({
        title: t('knowledgeBase.attachments.attachSuccessTitle'),
        description: workspaceName,
      });
      setIsAttachDialogOpen(false);
      resetDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.attachments.attachFailed'));
    }
  }, [canEditMode, createKnowledgeBaseAttachment, knowledgeBaseId, mode, mountAlias, resetDraft, selectedWorkspaceId, t, toast, workspaceMap]);

  const handleAliasUpdate = React.useCallback(async (attachmentId: string, nextAlias: string) => {
    setBusyAttachmentId(attachmentId);
    setError(null);
    try {
      await updateKnowledgeBaseAttachment(knowledgeBaseId, attachmentId, {
        mountAlias: nextAlias.trim() || undefined,
      });
      toast({
        title: t('knowledgeBase.attachments.aliasUpdatedTitle'),
        description: nextAlias || t('knowledgeBase.attachments.aliasUpdatedFallback', { id: attachmentId }),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.attachments.aliasUpdateFailed'));
    } finally {
      setBusyAttachmentId(null);
    }
  }, [knowledgeBaseId, t, toast, updateKnowledgeBaseAttachment]);

  const handleModeUpdate = React.useCallback(async (
    attachmentId: string,
    nextMode: KnowledgeBaseAttachmentMode,
  ) => {
    setBusyAttachmentId(attachmentId);
    setError(null);
    try {
      await updateKnowledgeBaseAttachment(knowledgeBaseId, attachmentId, {
        mode: nextMode,
      });
      toast({
        title: t('knowledgeBase.attachments.modeUpdatedTitle'),
        description: modeLabel(nextMode),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.attachments.modeUpdateFailed'));
    } finally {
      setBusyAttachmentId(null);
    }
  }, [knowledgeBaseId, modeLabel, t, toast, updateKnowledgeBaseAttachment]);

  const handleDetach = React.useCallback(async (attachmentId: string) => {
    setBusyAttachmentId(attachmentId);
    setError(null);
    try {
      await deleteKnowledgeBaseAttachment(knowledgeBaseId, attachmentId);
      toast({
        title: t('knowledgeBase.attachments.detachSuccessTitle'),
        description: attachmentId,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('knowledgeBase.attachments.detachFailed'));
    } finally {
      setBusyAttachmentId(null);
    }
  }, [deleteKnowledgeBaseAttachment, knowledgeBaseId, t, toast]);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Link2 className="h-4 w-4 text-sky-600" />
              {t('knowledgeBase.attachments.title')}
            </CardTitle>
            <CardDescription>{t('knowledgeBase.attachments.description')}</CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setError(null);
              setIsAttachDialogOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            {t('knowledgeBase.attachments.attachAction')}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {attachments.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-sm text-muted-foreground">
              {t('knowledgeBase.attachments.empty')}
            </div>
          ) : (
            <div className="space-y-3">
              {attachments.map((attachment) => {
                const workspace = workspaceMap[attachment.workspaceId];
                return (
                  <div
                    key={attachment.id}
                    className="flex flex-col gap-4 rounded-xl border border-border/60 bg-card/60 p-4"
                  >
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate font-medium text-foreground">
                            {workspace?.name || attachment.workspaceId}
                          </span>
                          <Badge variant="outline">{attachment.workspaceId}</Badge>
                          <Badge variant={attachment.mode === 'rw' ? 'secondary' : 'outline'}>
                            {attachment.mode.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {t('knowledgeBase.attachments.attachedMeta', {
                            userId: attachment.attachedById,
                            date: new Date(attachment.createdAt).toLocaleString('zh-TW'),
                          })}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isMutating || busyAttachmentId === attachment.id}
                        onClick={() => {
                          void handleDetach(attachment.id);
                        }}
                      >
                        <Unplug className="mr-2 h-4 w-4" />
                        {t('knowledgeBase.common.actions.detach')}
                      </Button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                      <div className="space-y-2">
                        <Label htmlFor={`alias-${attachment.id}`}>{t('knowledgeBase.attachments.labels.mountAlias')}</Label>
                        <div className="flex gap-2">
                          <Input
                            id={`alias-${attachment.id}`}
                            defaultValue={attachment.mountAlias}
                            disabled={isMutating || busyAttachmentId === attachment.id}
                            onBlur={(event) => {
                              const nextAlias = event.target.value.trim();
                              if (nextAlias && nextAlias !== attachment.mountAlias) {
                                void handleAliasUpdate(attachment.id, nextAlias);
                              }
                            }}
                          />
                          <Badge variant="outline" className="shrink-0 self-center">
                            /knowledge/{attachment.mountAlias}
                          </Badge>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`mode-${attachment.id}`}>{t('knowledgeBase.attachments.labels.mode')}</Label>
                        <Select
                          value={attachment.mode}
                          onValueChange={(value: KnowledgeBaseAttachmentMode) => {
                            if (value !== attachment.mode) {
                              void handleModeUpdate(attachment.id, value);
                            }
                          }}
                          disabled={!canEditMode || isMutating || busyAttachmentId === attachment.id}
                        >
                          <SelectTrigger id={`mode-${attachment.id}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ro">{t('knowledgeBase.common.mode.ro')}</SelectItem>
                            <SelectItem value="rw">{t('knowledgeBase.common.mode.rw')}</SelectItem>
                          </SelectContent>
                        </Select>
                        {!canEditMode ? (
                          <p className="text-xs text-muted-foreground">
                            {t('knowledgeBase.attachments.modeLocked')}
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
              {t('knowledgeBase.attachments.dialog.title')}
            </DialogTitle>
            <DialogDescription>{t('knowledgeBase.attachments.dialog.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="kb-attach-workspace">{t('knowledgeBase.attachments.labels.workspace')}</Label>
              <Popover open={workspacePickerOpen} onOpenChange={setWorkspacePickerOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="kb-attach-workspace"
                    type="button"
                    variant="outline"
                    role="combobox"
                    className={cn(
                      'w-full justify-between font-normal',
                      !selectedWorkspaceId && 'text-muted-foreground',
                    )}
                  >
                    {selectedWorkspaceId
                      ? (workspaceMap[selectedWorkspaceId]?.name || selectedWorkspaceId)
                      : t('knowledgeBase.attachments.dialog.workspacePlaceholder')}
                    <Workflow className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder={t('knowledgeBase.attachments.dialog.workspaceSearchPlaceholder')}
                      value={workspaceQuery}
                      onValueChange={setWorkspaceQuery}
                    />
                    <CommandList>
                      {filteredCandidates.length === 0 ? (
                        <CommandEmpty>{t('knowledgeBase.attachments.dialog.workspaceEmpty')}</CommandEmpty>
                      ) : (
                        <CommandGroup heading={t('knowledgeBase.attachments.dialog.workspaceGroup')}>
                          {filteredCandidates.map((workspace) => (
                            <CommandItem
                              key={workspace.id}
                              value={workspace.id}
                              onSelect={() => {
                                setSelectedWorkspaceId(workspace.id);
                                setWorkspacePickerOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  'h-4 w-4',
                                  workspace.id === selectedWorkspaceId ? 'opacity-100' : 'opacity-0',
                                )}
                              />
                              <div className="min-w-0">
                                <div className="truncate font-medium">
                                  {workspace.name || workspace.id}
                                </div>
                                <div className="truncate text-xs text-muted-foreground">
                                  {workspace.id}
                                  {workspace.accessRole ? ` · ${workspace.accessRole}` : ''}
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
              <Label htmlFor="kb-attach-alias">{t('knowledgeBase.attachments.labels.mountAlias')}</Label>
              <Input
                id="kb-attach-alias"
                value={mountAlias}
                onChange={(event) => setMountAlias(event.target.value)}
                placeholder={t('knowledgeBase.attachments.dialog.aliasPlaceholder')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="kb-attach-mode">{t('knowledgeBase.attachments.labels.mode')}</Label>
              <Select
                value={canEditMode ? mode : 'ro'}
                onValueChange={(value: KnowledgeBaseAttachmentMode) => setMode(value)}
                disabled={!canEditMode}
              >
                <SelectTrigger id="kb-attach-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ro">{t('knowledgeBase.common.mode.ro')}</SelectItem>
                  <SelectItem value="rw">{t('knowledgeBase.common.mode.rw')}</SelectItem>
                </SelectContent>
              </Select>
              {!canEditMode ? (
                <p className="text-xs text-muted-foreground">
                  {t('knowledgeBase.attachments.modeLocked')}
                </p>
              ) : null}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAttachDialogOpen(false)}>
              {t('knowledgeBase.common.actions.cancel')}
            </Button>
            <Button onClick={() => { void handleAttach(); }} disabled={!selectedWorkspaceId || isMutating}>
              {t('knowledgeBase.attachments.dialog.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
};

export default KnowledgeBaseAttachmentsTab;
