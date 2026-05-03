import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Package, Power } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { CodexLayerSelect } from '../components/CodexLayerSelect';
import { NewThreadNotice } from '../components/SettingsSourcePrimitives';
import { createAgentSettingsApi } from '../services/agentSettingsApi';

type CodexLayer = 'user' | 'project';

const CodexPluginsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const [layer, setLayer] = useState<CodexLayer>('user');
  const [showNewThreadNotice, setShowNewThreadNotice] = useState(false);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const pluginsQuery = useQuery({
    queryKey: ['codex-plugins', runtimeBaseUrl, workspaceId],
    queryFn: () => api.listCodexPlugins(runtimeBaseUrl || '', workspaceId || ''),
    enabled: Boolean(runtimeBaseUrl && workspaceId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ pluginId, enabled }: { pluginId: string; enabled: boolean }) =>
      api.setCodexPluginEnabled(runtimeBaseUrl || '', workspaceId || '', pluginId, layer, enabled),
    onSuccess: () => {
      setShowNewThreadNotice(true);
      void queryClient.invalidateQueries({ queryKey: ['codex-plugins', runtimeBaseUrl, workspaceId] });
      toast({ title: t('workspace.agentSettings.codex.plugins.notifications.saved') });
    },
  });

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={t('workspace.agentSettings.codex.plugins.title')}
        icon={Package}
        actions={<CodexLayerSelect value={layer} onChange={setLayer} t={t} />}
      />
      <div className="flex-1 space-y-4 overflow-auto p-4">
        <Alert>
          <AlertDescription>{t('workspace.agentSettings.codex.plugins.installReserved')}</AlertDescription>
        </Alert>
        {showNewThreadNotice && <NewThreadNotice />}
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {pluginsQuery.data?.plugins.map((plugin) => (
            <Card key={plugin.id}>
              <CardHeader>
                <CardTitle className="flex items-start justify-between gap-3 text-base">
                  <span className="min-w-0 truncate">{plugin.name}</span>
                  <Badge variant={plugin.enabled ? 'default' : 'secondary'}>
                    {plugin.enabled
                      ? t('workspace.agentSettings.codex.plugins.enabled')
                      : t('workspace.agentSettings.codex.plugins.disabled')}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{plugin.id}</Badge>
                  {plugin.marketplace && <Badge variant="outline">{plugin.marketplace}</Badge>}
                  {plugin.listed && <Badge variant="secondary">{t('workspace.agentSettings.codex.plugins.listed')}</Badge>}
                  {plugin.installed && <Badge variant="secondary">{t('workspace.agentSettings.codex.plugins.installed')}</Badge>}
                </div>
                <pre className="max-h-32 overflow-auto rounded bg-muted p-2 text-xs">
                  {JSON.stringify(plugin.bundled, null, 2)}
                </pre>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => toggleMutation.mutate({ pluginId: plugin.id, enabled: !plugin.enabled })}
                  disabled={toggleMutation.isPending}
                >
                  <Power className="mr-2 h-4 w-4" />
                  {plugin.enabled
                    ? t('workspace.agentSettings.codex.plugins.actions.disable')
                    : t('workspace.agentSettings.codex.plugins.actions.enable')}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
        {pluginsQuery.data?.plugins.length === 0 && (
          <p className="text-sm text-muted-foreground">{t('workspace.agentSettings.codex.plugins.empty')}</p>
        )}
      </div>
    </div>
  );
};

export default CodexPluginsPage;
