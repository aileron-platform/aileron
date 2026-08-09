import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, FileCode2, Loader2, RefreshCw, Save } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { SettingsDocumentEditor } from '../SettingsDocumentEditor';
import type { RawSettingsSource } from '../../model/rawSettingsSource';

export interface RawSettingsWorkflowProps {
  queryKey: readonly unknown[];
  source: RawSettingsSource;
  titleKey: string;
  scopeLabelKey: string;
  dirtyLabelKey: string;
  refreshLabelKey: string;
  saveLabelKey: string;
  savingLabelKey: string;
  saveSuccessKey: string;
  saveFailedKey: string;
  loadFailedKey: string;
  unsavedChangesConfirmKey: string;
  runtimeUnavailableKey?: string;
  runtimeLoadingKey?: string;
  runtimeMissingKey?: string;
}

const DEFAULT_RUNTIME_UNAVAILABLE_KEY = 'workspace.agentSettings.common.agentsMd.status.runtimeUnavailable';
const DEFAULT_RUNTIME_LOADING_KEY = 'workspace.agentSettings.common.agentsMd.status.runtimeLoading';
const DEFAULT_RUNTIME_MISSING_KEY = 'workspace.agentSettings.common.agentsMd.status.runtimeMissing';

const RawSettingsWorkflow: React.FC<RawSettingsWorkflowProps> = ({
  queryKey,
  source,
  titleKey,
  scopeLabelKey,
  dirtyLabelKey,
  refreshLabelKey,
  saveLabelKey,
  savingLabelKey,
  saveSuccessKey,
  saveFailedKey,
  loadFailedKey,
  unsavedChangesConfirmKey,
  runtimeUnavailableKey = DEFAULT_RUNTIME_UNAVAILABLE_KEY,
  runtimeLoadingKey = DEFAULT_RUNTIME_LOADING_KEY,
  runtimeMissingKey = DEFAULT_RUNTIME_MISSING_KEY,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const { workspaceId, runtimeBaseUrl, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;
  const [scopeId, setScopeId] = React.useState(source.scopes[0]?.id ?? '');
  const [draftContent, setDraftContent] = React.useState('');
  const [savedContent, setSavedContent] = React.useState('');
  const isRuntimeReady = Boolean(workspaceId && runtimeBaseUrl);
  const settingsQueryKey = [
    ...queryKey,
    runtimeBaseUrl ?? '',
    workspaceId ?? '',
    scopeId,
  ];

  const settingsQuery = useQuery({
    queryKey: settingsQueryKey,
    enabled: Boolean(scopeId && isRuntimeReady),
    queryFn: ({ signal }) => source.load(scopeId, signal),
  });

  React.useEffect(() => {
    if (!settingsQuery.data) return;
    setSavedContent(settingsQuery.data.content);
    setDraftContent(settingsQuery.data.content);
  }, [settingsQuery.data]);

  const isDirty = draftContent !== savedContent;
  const isLoading = settingsQuery.isFetching && !settingsQuery.data;
  const controlsDisabled = runtimeLoading || !isRuntimeReady || isLoading;

  const saveMutation = useMutation({
    mutationFn: () => source.save(scopeId, draftContent),
    onSuccess: async () => {
      setSavedContent(draftContent);
      toast({ title: t(saveSuccessKey) });
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: t(saveFailedKey),
        description: error instanceof Error ? error.message : String(error),
      });
    },
  });

  const handleScopeChange = React.useCallback(
    (nextScopeId: string) => {
      if (nextScopeId === scopeId || controlsDisabled) return;
      if (isDirty && !window.confirm(t(unsavedChangesConfirmKey))) return;
      setScopeId(nextScopeId);
    },
    [controlsDisabled, isDirty, scopeId, t, unsavedChangesConfirmKey],
  );

  const statusMessage = React.useMemo(() => {
    if (runtimeError) return t(runtimeUnavailableKey, { message: runtimeError });
    if (runtimeLoading && !isRuntimeReady) return t(runtimeLoadingKey);
    if (!isRuntimeReady) return t(runtimeMissingKey);
    if (settingsQuery.error) return t(loadFailedKey);
    return null;
  }, [
    isRuntimeReady,
    loadFailedKey,
    runtimeError,
    runtimeLoading,
    runtimeLoadingKey,
    runtimeMissingKey,
    runtimeUnavailableKey,
    settingsQuery.error,
    t,
  ]);

  return (
    <SettingsWorkflowShell
      title={t(titleKey)}
      icon={FileCode2}
      summary={isDirty ? <SettingsWorkflowCountBadge label={t(dirtyLabelKey)} /> : null}
      headerActions={(
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
            <span className="text-xs text-muted-foreground">{t(scopeLabelKey)}</span>
            <Select value={scopeId} onValueChange={handleScopeChange} disabled={controlsDisabled}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {source.scopes.map((scope) => (
                  <SelectItem key={scope.id} value={scope.id}>
                    {t(scope.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => void settingsQuery.refetch()}
            disabled={controlsDisabled}
          >
            <RefreshCw className={`mr-1 h-3 w-3 ${settingsQuery.isFetching ? 'animate-spin' : ''}`} />
            {t(refreshLabelKey)}
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => saveMutation.mutate()}
            disabled={controlsDisabled || !isDirty || saveMutation.isPending}
          >
            {saveMutation.isPending ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Save className="mr-1 h-3 w-3" />
            )}
            {saveMutation.isPending ? t(savingLabelKey) : t(saveLabelKey)}
          </Button>
        </div>
      )}
      hasItems
      emptyTitle={t(titleKey)}
      emptyDescription={t(titleKey)}
      contentClassName="h-full overflow-hidden"
    >
      <div className="flex h-full min-h-0 flex-col gap-4">
        {statusMessage ? (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{statusMessage}</span>
          </div>
        ) : null}
        <div className="relative min-h-0 flex-1 overflow-hidden">
          {isLoading ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : null}
          <SettingsDocumentEditor
            value={draftContent}
            format={source.format}
            onChange={setDraftContent}
            readOnly={controlsDisabled}
          />
        </div>
      </div>
    </SettingsWorkflowShell>
  );
};

export default RawSettingsWorkflow;
