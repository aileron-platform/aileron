import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Boxes, ChevronDown, Loader2, RefreshCw } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { createAgentSettingsApi, type GeminiExtensionDetail } from '../services/agentSettingsApi';

const I18N_PREFIX = 'workspace.agentSettings.geminiExtensions';

const GeminiExtensionsPage: React.FC = () => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const queryClient = useQueryClient();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(() => createAgentSettingsApi('gemini'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const enabled = Boolean(runtimeBaseUrl && workspaceId);

  const listQuery = useQuery({
    queryKey: ['gemini-extensions', runtimeBaseUrl, workspaceId],
    queryFn: () => api.listGeminiExtensions(runtimeBaseUrl || '', workspaceId || ''),
    enabled,
  });

  const detailQuery = useQuery({
    queryKey: ['gemini-extension-detail', runtimeBaseUrl, workspaceId, selectedName],
    queryFn: () => api.getGeminiExtension(runtimeBaseUrl || '', workspaceId || '', selectedName || ''),
    enabled: enabled && Boolean(selectedName),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ name, scope, enabledHere }: { name: string; scope: 'workspace' | 'user'; enabledHere: boolean }) => {
      setError(null);
      return enabledHere
        ? api.disableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name, scope)
        : api.enableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name, scope);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['gemini-extensions', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['gemini-extension-detail', runtimeBaseUrl, workspaceId] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t(`${I18N_PREFIX}.errors.commandFailed`));
    },
  });

  const extensions = listQuery.data?.extensions ?? [];
  const detail = detailQuery.data?.extension;
  const loading = listQuery.isLoading || workspaceRuntime.isLoading;

  return (
    <SettingsWorkflowShell
      title={t(`${I18N_PREFIX}.title`)}
      icon={Boxes}
      headerActions={
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => void listQuery.refetch()}
          disabled={!enabled || listQuery.isFetching}
        >
          <RefreshCw className={`mr-1 h-3 w-3 ${listQuery.isFetching ? 'animate-spin' : ''}`} />
          {t(`${I18N_PREFIX}.actions.refresh`)}
        </Button>
      }
      hasItems={extensions.length > 0}
      emptyTitle={t(`${I18N_PREFIX}.empty.title`)}
      emptyDescription={t(`${I18N_PREFIX}.empty.description`)}
      contentClassName="h-full overflow-y-auto"
    >
      <div className="grid gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {loading && (
            <div className="grid h-40 place-content-center text-sm text-muted-foreground">
              <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
              {t(`${I18N_PREFIX}.loading`)}
            </div>
          )}
          {!loading && extensions.length === 0 && (
            <div className="grid h-48 place-content-center rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              {t(`${I18N_PREFIX}.empty.installHint`)}
            </div>
          )}
          {extensions.map((extension) => (
            <Card key={extension.name} className={selectedName === extension.name ? 'border-primary' : undefined}>
              <CardHeader className="space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{extension.name}</CardTitle>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{extension.version ?? t(`${I18N_PREFIX}.unknownVersion`)}</span>
                      {extension.installSource && <span>{extension.installSource}</span>}
                      {extension.installType && <span>{extension.installType}</span>}
                      {extension.releaseTag && <span>{extension.releaseTag}</span>}
                    </div>
                  </div>
                  <Badge variant={extension.enabledHere ? 'default' : 'secondary'}>
                    {extension.enabledHere ? t(`${I18N_PREFIX}.status.enabledHere`) : t(`${I18N_PREFIX}.status.disabledHere`)}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={toggleMutation.isPending}
                    onClick={() => toggleMutation.mutate({ name: extension.name, scope: 'workspace', enabledHere: extension.enabledHere })}
                  >
                    {t(`${I18N_PREFIX}.actions.toggleWorkspace`)}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={toggleMutation.isPending}
                    onClick={() => toggleMutation.mutate({ name: extension.name, scope: 'user', enabledHere: extension.enabledHere })}
                  >
                    {t(`${I18N_PREFIX}.actions.toggleUser`)}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setSelectedName(extension.name)}>
                    {t(`${I18N_PREFIX}.actions.details`)}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {Object.entries(extension.resourceCounts).map(([key, count]) => (
                    <Badge key={key} variant="outline">
                      {t(`${I18N_PREFIX}.counts.${key}`, { count })}
                    </Badge>
                  ))}
                  <Badge variant="outline">{t(`${I18N_PREFIX}.counts.excludeTools`, { count: extension.excludeToolsCount })}</Badge>
                </div>
                <details className="rounded-md border border-border p-3 text-xs">
                  <summary className="flex cursor-pointer items-center gap-2 text-muted-foreground">
                    <ChevronDown className="h-3 w-3" />
                    {t(`${I18N_PREFIX}.advanced.overrides`)}
                  </summary>
                  <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3">
                    {extension.overrides.length ? extension.overrides.join('\n') : t(`${I18N_PREFIX}.advanced.noOverrides`)}
                  </pre>
                </details>
              </CardContent>
            </Card>
          ))}
        </div>
        <ExtensionDetailPanel detail={detail} loading={detailQuery.isLoading} />
      </div>
    </SettingsWorkflowShell>
  );
};

const ExtensionDetailPanel: React.FC<{ detail?: GeminiExtensionDetail; loading: boolean }> = ({ detail, loading }) => {
  const { t } = useI18n();

  if (loading) {
    return <div className="rounded-lg border border-border p-6 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.loading`)}</div>;
  }
  if (!detail) {
    return <div className="rounded-lg border border-border p-6 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.empty`)}</div>;
  }

  return (
    <aside className="space-y-4 rounded-lg border border-border p-6">
      <div>
        <h2 className="text-base font-semibold">{t(`${I18N_PREFIX}.detail.title`, { name: detail.name })}</h2>
        <p className="mt-1 text-xs text-muted-foreground">{detail.installInfo?.source ?? t(`${I18N_PREFIX}.detail.noInstallSource`)}</p>
      </div>
      <section>
        <h3 className="mb-2 text-sm font-medium">{t(`${I18N_PREFIX}.detail.context`)}</h3>
        <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
          {detail.contextFile?.content ?? t(`${I18N_PREFIX}.detail.noContext`)}
        </pre>
      </section>
      <section>
        <h3 className="mb-2 text-sm font-medium">{t(`${I18N_PREFIX}.detail.policies`)}</h3>
        <div className="space-y-2">
          {detail.policies.length
            ? detail.policies.map((policy) => (
                <pre key={policy.path} className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
                  {policy.content}
                </pre>
              ))
            : <p className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noPolicies`)}</p>}
        </div>
      </section>
      <section>
        <h3 className="mb-2 text-sm font-medium">{t(`${I18N_PREFIX}.detail.excludeTools`)}</h3>
        <div className="flex flex-wrap gap-2">
          {detail.excludeTools.length
            ? detail.excludeTools.map((tool) => <Badge key={tool} variant="outline">{tool}</Badge>)
            : <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noExcludeTools`)}</span>}
        </div>
      </section>
    </aside>
  );
};

export default GeminiExtensionsPage;
