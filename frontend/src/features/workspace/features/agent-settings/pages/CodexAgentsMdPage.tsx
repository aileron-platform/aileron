import React, { useCallback, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';

type CodexAgentsMdScope = 'project' | 'user';

const scopeOptions: CodexAgentsMdScope[] = ['project', 'user'];

const CodexAgentsMdPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const [scope, setScope] = useState<CodexAgentsMdScope>('project');
  const [content, setContent] = useState('');
  const [initialContent, setInitialContent] = useState('');
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !workspaceRuntime.error);
  const hasChanges = content !== initialContent;

  const documentQuery = useQuery({
    queryKey: ['codex-agents-md', runtimeBaseUrl, workspaceId, scope],
    queryFn: () => api.getCodexAgentsMd(runtimeBaseUrl || '', workspaceId || '', scope),
    enabled: isRuntimeReady,
  });

  React.useEffect(() => {
    if (documentQuery.data) {
      setContent(documentQuery.data.content);
      setInitialContent(documentQuery.data.content);
    }
  }, [documentQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => api.updateCodexAgentsMd(runtimeBaseUrl || '', workspaceId || '', { scope, content }),
    onSuccess: () => {
      setInitialContent(content);
      void queryClient.invalidateQueries({ queryKey: ['codex-agents-md', runtimeBaseUrl, workspaceId, scope] });
      toast({ title: t('workspace.agentSettings.codex.agentsMd.notifications.saveSuccess') });
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: t('workspace.agentSettings.codex.agentsMd.notifications.saveFailed'),
        description: error instanceof Error ? error.message : undefined,
      });
    },
  });

  const confirmDiscard = useCallback(() => {
    if (!hasChanges) return true;
    return window.confirm(t('workspace.agentSettings.codex.agentsMd.confirmDiscard'));
  }, [hasChanges, t]);

  const handleScopeChange = useCallback((value: string) => {
    if (!confirmDiscard()) return;
    setScope(value as CodexAgentsMdScope);
  }, [confirmDiscard]);

  const caveatStatus = documentQuery.data?.caveats.length ? (
    <div className="space-y-2">
      {documentQuery.data.caveats.map((caveat) => (
        <Alert key={`${caveat.type}:${caveat.path ?? ''}`}>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{t(`workspace.agentSettings.codex.agentsMd.caveatTitles.${caveat.type}`)}</AlertTitle>
          <AlertDescription>
            {t(caveat.messageKey, {
              path: caveat.path ?? '',
              sizeBytes: caveat.metadata?.sizeBytes,
              maxBytes: caveat.metadata?.maxBytes,
            })}
          </AlertDescription>
        </Alert>
      ))}
    </div>
  ) : null;

  return (
    <MarkdownDocumentShell
      title={t('workspace.agentSettings.codex.agentsMd.title')}
      refreshLabel={t('workspace.agentSettings.codex.common.actions.refresh')}
      saveLabel={t('workspace.agentSettings.codex.common.actions.save')}
      runtimeLoadingLabel={t('workspace.agentSettings.common.loading')}
      loadingLabel={t('workspace.agentSettings.common.loading')}
      runtimeStatusMessage={workspaceRuntime.error ?? null}
      runtimeLoading={workspaceRuntime.isLoading}
      isRuntimeReady={isRuntimeReady}
      isLoading={documentQuery.isLoading}
      isSaving={saveMutation.isPending}
      isStale={false}
      statusMessage={caveatStatus}
      staleMessage=""
      value={content}
      onChange={setContent}
      onRefresh={() => {
        if (!confirmDiscard()) return;
        void documentQuery.refetch();
      }}
      onSave={() => saveMutation.mutate()}
      refreshDisabled={!isRuntimeReady || documentQuery.isFetching || saveMutation.isPending}
      saveDisabled={!isRuntimeReady || documentQuery.isFetching || saveMutation.isPending || !hasChanges}
      headerExtras={(
        <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
          <span className="text-xs text-muted-foreground">
            {t('workspace.agentSettings.codex.common.layer')}
          </span>
          <Select value={scope} onValueChange={handleScopeChange} disabled={documentQuery.isFetching || saveMutation.isPending}>
            <SelectTrigger className="h-7 w-32 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopeOptions.map((option) => (
                <SelectItem key={option} value={option}>
                  {t(`workspace.agentSettings.codex.common.layers.${option}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      footerExtras={documentQuery.data ? (
        <span>
          {t('workspace.agentSettings.codex.agentsMd.footer', {
            path: documentQuery.data.path,
            sizeBytes: documentQuery.data.sizeBytes,
            maxBytes: documentQuery.data.maxBytes,
          })}
        </span>
      ) : null}
    />
  );
};

export default CodexAgentsMdPage;
