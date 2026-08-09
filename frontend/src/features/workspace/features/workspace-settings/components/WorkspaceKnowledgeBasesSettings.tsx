import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React from 'react';
import { Check, Database, FolderTree, Link2, Plus, Save, Unplug, Workflow } from 'lucide-react';
import { ApiError, apiClient } from '@/shared/api/apiClient';
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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { useToast } from '@/shared/components/ui/use-toast';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type {
  WorkspaceDetailResponse,
  WorkspaceKnowledgeBaseAttachmentCreatePayload,
  WorkspaceKnowledgeBaseAttachmentListResponse,
  WorkspaceKnowledgeBaseAttachmentMutationResponse,
  WorkspaceKnowledgeBaseAttachmentSummary,
  WorkspaceKnowledgeBaseAttachmentUpdatePayload,
  WorkspaceKnowledgeBaseCandidateSummary,
  WorkspaceKnowledgeBaseMountSync,
  WorkspaceKnowledgeBaseMountSyncResponse,
} from '@/features/workspace/api/workspaceApiTypes';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  getWorkspaceKnowledgeBaseErrorTranslationKey,
  MountedKnowledgeBasesPanel,
} from './MountedKnowledgeBasesPanel';

const MOUNT_SYNC_POLL_BASE_INTERVAL_MS = 2_000;
const MOUNT_SYNC_POLL_MAX_INTERVAL_MS = 16_000;
const MOUNT_SYNC_POLL_MAX_CONSECUTIVE_FAILURES = 4;

const isMountSyncInProgress = (
  mountSync: WorkspaceKnowledgeBaseMountSync | null,
): boolean => (
  mountSync?.status === 'syncing'
  || Boolean(mountSync?.compensating)
);

const getMountSyncPollRetryDelay = (failureCount: number): number => (
  Math.min(
    MOUNT_SYNC_POLL_BASE_INTERVAL_MS * (2 ** failureCount),
    MOUNT_SYNC_POLL_MAX_INTERVAL_MS,
  )
);

const replaceAttachment = (
  current: WorkspaceKnowledgeBaseAttachmentSummary[],
  replacement: WorkspaceKnowledgeBaseAttachmentSummary,
): WorkspaceKnowledgeBaseAttachmentSummary[] => (
  current.some((attachment) => attachment.id === replacement.id)
    ? current.map((attachment) => (attachment.id === replacement.id ? replacement : attachment))
    : [...current, replacement]
);

export const WorkspaceKnowledgeBasesSettings: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, permissions } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;
  const [workspaceDetail, setWorkspaceDetail] = React.useState<WorkspaceDetailResponse | null>(null);
  const [attachments, setAttachments] = React.useState<WorkspaceKnowledgeBaseAttachmentSummary[]>([]);
  const [mountSync, setMountSync] = React.useState<WorkspaceKnowledgeBaseMountSync | null>(null);
  const [availableKnowledgeBases, setAvailableKnowledgeBases] = React.useState<WorkspaceKnowledgeBaseCandidateSummary[]>([]);
  const [aliasDrafts, setAliasDrafts] = React.useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = React.useState(false);
  const [isMutating, setIsMutating] = React.useState(false);
  const [isRetrying, setIsRetrying] = React.useState(false);
  const [busyAttachmentId, setBusyAttachmentId] = React.useState<string | null>(null);
  const [errorKey, setErrorKey] = React.useState<string | null>(null);
  const [isAttachDialogOpen, setIsAttachDialogOpen] = React.useState(false);
  const [knowledgeBasePickerOpen, setKnowledgeBasePickerOpen] = React.useState(false);
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = React.useState('');
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = React.useState('');
  const [mountAlias, setMountAlias] = React.useState('');
  const serverAliasesRef = React.useRef<Record<string, string>>({});
  const attachmentRequestGenerationRef = React.useRef(0);
  const workspaceGenerationRef = React.useRef(0);
  const isMountedRef = React.useRef(false);

  const isWorkspaceRequestActive = React.useCallback((workspaceGeneration: number) => (
    isMountedRef.current
    && workspaceGenerationRef.current === workspaceGeneration
  ), []);

  React.useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      workspaceGenerationRef.current += 1;
      attachmentRequestGenerationRef.current += 1;
    };
  }, []);

  const setMutationError = React.useCallback((error: unknown, fallbackKey: string) => {
    if (!isMountedRef.current) {
      return;
    }
    setErrorKey(
      error instanceof ApiError && error.errorCode
        ? getWorkspaceKnowledgeBaseErrorTranslationKey(error.errorCode)
        : fallbackKey,
    );
  }, []);

  const applyAttachmentListResponse = React.useCallback((
    response: WorkspaceKnowledgeBaseAttachmentListResponse,
  ) => {
    if (!isMountedRef.current) {
      return;
    }
    const previousServerAliases = serverAliasesRef.current;
    const nextServerAliases = Object.fromEntries(
      response.items.map((attachment) => [attachment.id, attachment.mountAlias]),
    );

    setAttachments(response.items);
    setMountSync(response.knowledgeBaseMountSync);
    setAliasDrafts((current) => Object.fromEntries(
      response.items.map((attachment) => {
        const currentDraft = current[attachment.id];
        const previousServerAlias = previousServerAliases[attachment.id];
        const hasUnsavedDraft = currentDraft !== undefined
          && previousServerAlias !== undefined
          && currentDraft !== previousServerAlias;
        return [
          attachment.id,
          hasUnsavedDraft ? currentDraft : attachment.mountAlias,
        ];
      }),
    ));
    serverAliasesRef.current = nextServerAliases;
    setErrorKey(null);
  }, []);

  React.useEffect(() => {
    const controller = new AbortController();
    const workspaceGeneration = workspaceGenerationRef.current + 1;
    const requestGeneration = attachmentRequestGenerationRef.current + 1;
    workspaceGenerationRef.current = workspaceGeneration;
    attachmentRequestGenerationRef.current = requestGeneration;
    serverAliasesRef.current = {};
    setWorkspaceDetail(null);
    setAttachments([]);
    setMountSync(null);
    setAliasDrafts({});
    setIsMutating(false);
    setIsRetrying(false);
    setBusyAttachmentId(null);
    setErrorKey(null);

    if (!workspaceId) {
      setIsLoading(false);
      return () => controller.abort();
    }

    setIsLoading(true);
    void Promise.all([
      apiClient.get<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
        { signal: controller.signal },
      ),
      apiClient.get<WorkspaceKnowledgeBaseAttachmentListResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases`,
        { signal: controller.signal },
      ),
    ])
      .then(([detail, attachmentResponse]) => {
        if (
          controller.signal.aborted
          || !isWorkspaceRequestActive(workspaceGeneration)
          || attachmentRequestGenerationRef.current !== requestGeneration
        ) {
          return;
        }
        setWorkspaceDetail(detail);
        applyAttachmentListResponse(attachmentResponse);
      })
      .catch((error) => {
        if (
          controller.signal.aborted
          || !isWorkspaceRequestActive(workspaceGeneration)
          || attachmentRequestGenerationRef.current !== requestGeneration
        ) {
          return;
        }
        setMutationError(
          error,
          'workspace.workspaceSettings.knowledgeBases.notifications.loadFailed',
        );
      })
      .finally(() => {
        if (
          !controller.signal.aborted
          && isWorkspaceRequestActive(workspaceGeneration)
          && attachmentRequestGenerationRef.current === requestGeneration
        ) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [
    applyAttachmentListResponse,
    isWorkspaceRequestActive,
    setMutationError,
    workspaceId,
  ]);

  React.useEffect(() => {
    if (!workspaceId || !isMountSyncInProgress(mountSync)) {
      return undefined;
    }

    const controller = new AbortController();
    const workspaceGeneration = workspaceGenerationRef.current;
    let timerId: number | undefined;
    let consecutiveFailures = 0;

    const scheduleRefresh = (delay: number) => {
      timerId = window.setTimeout(() => {
        const requestGeneration = attachmentRequestGenerationRef.current + 1;
        attachmentRequestGenerationRef.current = requestGeneration;
        void apiClient.get<WorkspaceKnowledgeBaseAttachmentListResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases`,
          { signal: controller.signal },
        )
          .then((response) => {
            if (
              controller.signal.aborted
              || !isWorkspaceRequestActive(workspaceGeneration)
            ) {
              return;
            }
            if (attachmentRequestGenerationRef.current !== requestGeneration) {
              scheduleRefresh(MOUNT_SYNC_POLL_BASE_INTERVAL_MS);
              return;
            }

            consecutiveFailures = 0;
            applyAttachmentListResponse(response);
            if (isMountSyncInProgress(response.knowledgeBaseMountSync)) {
              scheduleRefresh(MOUNT_SYNC_POLL_BASE_INTERVAL_MS);
            }
          })
          .catch((error) => {
            if (
              controller.signal.aborted
              || !isWorkspaceRequestActive(workspaceGeneration)
              || attachmentRequestGenerationRef.current !== requestGeneration
            ) {
              return;
            }

            consecutiveFailures += 1;
            setMutationError(
              error,
              'workspace.workspaceSettings.knowledgeBases.notifications.loadFailed',
            );
            if (consecutiveFailures < MOUNT_SYNC_POLL_MAX_CONSECUTIVE_FAILURES) {
              scheduleRefresh(getMountSyncPollRetryDelay(consecutiveFailures));
            }
          });
      }, delay);
    };

    scheduleRefresh(MOUNT_SYNC_POLL_BASE_INTERVAL_MS);
    return () => {
      controller.abort();
      if (timerId !== undefined) {
        window.clearTimeout(timerId);
      }
    };
  }, [
    applyAttachmentListResponse,
    isWorkspaceRequestActive,
    mountSync,
    setMutationError,
    workspaceId,
  ]);

  React.useEffect(() => {
    if (!isAttachDialogOpen || !permissions.canWriteAttachments) {
      setAvailableKnowledgeBases([]);
      return;
    }

    const controller = new AbortController();
    void apiClient.get<{ items: WorkspaceKnowledgeBaseCandidateSummary[] }>(
      '/knowledge-bases',
      { signal: controller.signal },
    )
      .then((response) => {
        if (!controller.signal.aborted) {
          setAvailableKnowledgeBases(response.items ?? []);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setMutationError(
            error,
            'workspace.workspaceSettings.knowledgeBases.notifications.loadFailed',
          );
        }
      });

    return () => {
      controller.abort();
    };
  }, [isAttachDialogOpen, permissions.canWriteAttachments, setMutationError]);

  const canManageAttachments = permissions.canWriteAttachments;
  const selectedKnowledgeBase = availableKnowledgeBases.find((kb) => kb.id === selectedKnowledgeBaseId);

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
  }, []);

  const applyMutationResponse = React.useCallback((response: WorkspaceKnowledgeBaseAttachmentMutationResponse) => {
    if (!isMountedRef.current) {
      return;
    }
    attachmentRequestGenerationRef.current += 1;
    serverAliasesRef.current = {
      ...serverAliasesRef.current,
      [response.attachment.id]: response.attachment.mountAlias,
    };
    setAttachments((current) => replaceAttachment(current, response.attachment));
    setAliasDrafts((current) => ({
      ...current,
      [response.attachment.id]: response.attachment.mountAlias,
    }));
    setMountSync(response.knowledgeBaseMountSync);
  }, []);

  const handleAttach = React.useCallback(async () => {
    if (!workspaceId || !selectedKnowledgeBaseId || !mountAlias || !canManageAttachments) {
      return;
    }

    const workspaceGeneration = workspaceGenerationRef.current;
    setIsMutating(true);
    setErrorKey(null);
    try {
      const payload: WorkspaceKnowledgeBaseAttachmentCreatePayload = {
        kbId: selectedKnowledgeBaseId,
        mountAlias,
      };
      const response = await apiClient.post<WorkspaceKnowledgeBaseAttachmentMutationResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases`,
        payload,
      );
      if (!isWorkspaceRequestActive(workspaceGeneration)) {
        return;
      }
      applyMutationResponse(response);
      setIsAttachDialogOpen(false);
      resetDraft();
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.notifications.attachAcceptedTitle'),
        description: selectedKnowledgeBase?.name ?? selectedKnowledgeBaseId,
      });
    } catch (error) {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setMutationError(
          error,
          'workspace.workspaceSettings.knowledgeBases.notifications.attachFailed',
        );
      }
    } finally {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setIsMutating(false);
      }
    }
  }, [
    applyMutationResponse,
    canManageAttachments,
    isWorkspaceRequestActive,
    mountAlias,
    resetDraft,
    selectedKnowledgeBase?.name,
    selectedKnowledgeBaseId,
    setMutationError,
    t,
    toast,
    workspaceId,
  ]);

  const handleAliasUpdate = React.useCallback(async (attachment: WorkspaceKnowledgeBaseAttachmentSummary) => {
    const alias = aliasDrafts[attachment.id] ?? '';
    if (
      !workspaceId
      || !canManageAttachments
      || attachment.status !== 'active'
      || !alias
      || alias === attachment.mountAlias
    ) {
      return;
    }

    const workspaceGeneration = workspaceGenerationRef.current;
    setBusyAttachmentId(attachment.id);
    setErrorKey(null);
    try {
      const payload: WorkspaceKnowledgeBaseAttachmentUpdatePayload = { mountAlias: alias };
      const response = await apiClient.patch<WorkspaceKnowledgeBaseAttachmentMutationResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases/${encodeURIComponent(attachment.id)}`,
        payload,
      );
      if (!isWorkspaceRequestActive(workspaceGeneration)) {
        return;
      }
      applyMutationResponse(response);
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.notifications.aliasUpdateAcceptedTitle'),
        description: response.attachment.name,
      });
    } catch (error) {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setMutationError(
          error,
          'workspace.workspaceSettings.knowledgeBases.notifications.updateFailed',
        );
      }
    } finally {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setBusyAttachmentId(null);
      }
    }
  }, [
    aliasDrafts,
    applyMutationResponse,
    canManageAttachments,
    isWorkspaceRequestActive,
    setMutationError,
    t,
    toast,
    workspaceId,
  ]);

  const handleDetach = React.useCallback(async (attachment: WorkspaceKnowledgeBaseAttachmentSummary) => {
    if (!workspaceId || !canManageAttachments || attachment.status !== 'active') {
      return;
    }

    const workspaceGeneration = workspaceGenerationRef.current;
    setBusyAttachmentId(attachment.id);
    setErrorKey(null);
    try {
      const response = await apiClient.delete<WorkspaceKnowledgeBaseAttachmentMutationResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases/${encodeURIComponent(attachment.id)}`,
      );
      if (!isWorkspaceRequestActive(workspaceGeneration)) {
        return;
      }
      applyMutationResponse(response);
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.notifications.detachAcceptedTitle'),
        description: attachment.name,
      });
    } catch (error) {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setMutationError(
          error,
          'workspace.workspaceSettings.knowledgeBases.notifications.detachFailed',
        );
      }
    } finally {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setBusyAttachmentId(null);
      }
    }
  }, [
    applyMutationResponse,
    canManageAttachments,
    isWorkspaceRequestActive,
    setMutationError,
    t,
    toast,
    workspaceId,
  ]);

  const handleRetry = React.useCallback(async () => {
    if (
      !workspaceId
      || !canManageAttachments
      || mountSync?.status !== 'degraded'
      || mountSync.compensating
    ) {
      return;
    }

    const workspaceGeneration = workspaceGenerationRef.current;
    setIsRetrying(true);
    setErrorKey(null);
    try {
      const response = await apiClient.post<WorkspaceKnowledgeBaseMountSyncResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-base-mount-sync/retry`,
      );
      if (!isWorkspaceRequestActive(workspaceGeneration)) {
        return;
      }
      setMountSync(response.knowledgeBaseMountSync);
      if (response.knowledgeBaseMountSync.status === 'ready') {
        const requestGeneration = attachmentRequestGenerationRef.current + 1;
        attachmentRequestGenerationRef.current = requestGeneration;
        const attachmentResponse = await apiClient.get<WorkspaceKnowledgeBaseAttachmentListResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/knowledge-bases`,
        );
        if (
          !isWorkspaceRequestActive(workspaceGeneration)
          || attachmentRequestGenerationRef.current !== requestGeneration
        ) {
          return;
        }
        applyAttachmentListResponse(attachmentResponse);
      }
      toast({
        title: t('workspace.workspaceSettings.knowledgeBases.notifications.retryAcceptedTitle'),
      });
    } catch (error) {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setMutationError(
          error,
          'workspace.workspaceSettings.knowledgeBases.notifications.retryFailed',
        );
      }
    } finally {
      if (isWorkspaceRequestActive(workspaceGeneration)) {
        setIsRetrying(false);
      }
    }
  }, [
    applyAttachmentListResponse,
    canManageAttachments,
    isWorkspaceRequestActive,
    mountSync?.compensating,
    mountSync?.status,
    setMutationError,
    t,
    toast,
    workspaceId,
  ]);

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('workspace.workspaceSettings.knowledgeBases.header.title')}
        icon={Database}
      />
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
          <MountedKnowledgeBasesPanel
            mountSync={mountSync}
            runtimeAccessRevision={workspaceDetail?.runtimeAccessRevision}
            runtimeAccessObservedRevision={workspaceDetail?.runtimeAccessObservedRevision}
            canRetry={canManageAttachments}
            isRetrying={isRetrying}
            onRetry={handleRetry}
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
                  disabled={isMutating}
                  onClick={() => {
                    setErrorKey(null);
                    setIsAttachDialogOpen(true);
                  }}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.workspaceSettings.knowledgeBases.desired.attachAction')}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {errorKey ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {t(errorKey)}
                </div>
              ) : null}

              {!canManageAttachments && workspaceDetail ? (
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
                    const aliasDraft = aliasDrafts[attachment.id] ?? attachment.mountAlias;
                    const isPendingMutation = attachment.status !== 'active';
                    const isBusy = busyAttachmentId === attachment.id;
                    const canSaveAlias = canManageAttachments
                      && !isPendingMutation
                      && !isMutating
                      && !isBusy
                      && aliasDraft.length > 0
                      && aliasDraft !== attachment.mountAlias;

                    return (
                      <div key={attachment.id} className="space-y-3 px-4 py-4 sm:px-6">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <Database className="h-4 w-4 shrink-0 text-sky-600" />
                            <span className="truncate font-medium text-foreground">
                              {attachment.name}
                            </span>
                            <Badge variant="outline">{attachment.slug}</Badge>
                            <Badge variant={isPendingMutation ? 'outline' : 'secondary'}>
                              {t(`workspace.workspaceSettings.knowledgeBases.attachmentStatus.${attachment.status}`)}
                            </Badge>
                          </div>
                          {canManageAttachments ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={isMutating || isBusy || isPendingMutation}
                              onClick={() => {
                                void handleDetach(attachment);
                              }}
                            >
                              <Unplug className="mr-2 h-4 w-4" />
                              {t('workspace.workspaceSettings.knowledgeBases.desired.detachAction')}
                            </Button>
                          ) : null}
                        </div>

                        {isPendingMutation ? (
                          <p className="text-xs text-muted-foreground">
                            {t(
                              `workspace.workspaceSettings.knowledgeBases.attachmentStatusDescription.${attachment.status}`,
                            )}
                          </p>
                        ) : null}

                        <div className="space-y-2">
                          <Label htmlFor={`workspace-kb-alias-${attachment.id}`}>
                            {t('workspace.workspaceSettings.knowledgeBases.form.aliasLabel')}
                          </Label>
                          <div className="flex flex-col gap-2 sm:flex-row">
                            <Input
                              id={`workspace-kb-alias-${attachment.id}`}
                              value={aliasDraft}
                              onChange={(event) => {
                                setAliasDrafts((current) => ({
                                  ...current,
                                  [attachment.id]: event.target.value,
                                }));
                              }}
                              disabled={!canManageAttachments || isPendingMutation || isBusy}
                            />
                            {canManageAttachments ? (
                              <Button
                                type="button"
                                variant="outline"
                                disabled={!canSaveAlias}
                                onClick={() => {
                                  void handleAliasUpdate(attachment);
                                }}
                              >
                                <Save className="mr-2 h-4 w-4" />
                                {isBusy
                                  ? t('workspace.workspaceSettings.knowledgeBases.desired.savingAlias')
                                  : t('workspace.workspaceSettings.knowledgeBases.desired.saveAlias')}
                              </Button>
                            ) : null}
                          </div>
                          <p className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground">
                            <FolderTree className="h-3.5 w-3.5" />
                            /knowledge/{attachment.mountAlias}
                          </p>
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
            <DialogHeading icon={Link2}>
              {t('workspace.workspaceSettings.knowledgeBases.dialog.title')}
            </DialogHeading>
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
                                setMountAlias(kb.slug);
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
                                <div className="truncate text-xs text-muted-foreground">{kb.slug}</div>
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
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAttachDialogOpen(false)}>
              {t('workspace.workspaceSettings.knowledgeBases.dialog.cancel')}
            </Button>
            <Button
              onClick={() => {
                void handleAttach();
              }}
              disabled={!selectedKnowledgeBaseId || !mountAlias || isMutating || !canManageAttachments}
            >
              {t('workspace.workspaceSettings.knowledgeBases.dialog.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
