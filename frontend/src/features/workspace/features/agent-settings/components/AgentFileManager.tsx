import React, { useMemo, useState } from 'react';
import { FolderGit, HardDrive, Puzzle, User, Wand2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/shared/hooks/useI18n';
import { createFileTreeResourceIdentity } from '@/shared/components/file-workbench';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentFileTreeDataAdapter } from '../adapters/agentFileTreeDataAdapter';
import { createAgentSettingsApi } from '../api/agentSettingsApi';
import type { AgentFileCollection, AgentSelectedFile } from '../model/documents';
import type { AgentToolConfig } from '../model/capabilities';
import { SettingsFileTreeWorkflow } from './SettingsFileTreeWorkflow';
import { sortAgentSettingsScopeValues } from './AgentSettingsSourceControls';
import { resolveAgentSettingsSelectedScope } from '../agentSettingsScopeModel';
import type { AgentFileTreeScope, AgentFileTreeVisibleScope } from '../adapters/agentFileTreeDataAdapter';
import { agentSettingsQueryKeys } from '../api/agentSettingsQueryKeys';

interface AgentFileManagerProps {
  config: AgentToolConfig;
  collectionType: AgentFileCollection;
  onSelect: (file: AgentSelectedFile) => void;
  workspaceId: string;
  collapsed?: boolean;
  showHeader?: boolean;
}

const collectionIcons = {
  skills: Wand2,
};

const scopeIcons = {
  all: FolderGit,
  project: FolderGit,
  user: User,
  local: HardDrive,
  plugin: Puzzle,
};

const AgentFileManager: React.FC<AgentFileManagerProps> = ({
  config,
  collectionType,
  onSelect,
  workspaceId,
  collapsed = false,
  showHeader = true,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime, permissions } = useWorkspace();
  const readOnly = !permissions.canWrite;
  const queryClient = useQueryClient();
  const capability = config.capabilities[collectionType];
  const [scope, setScope] = useState<AgentFileTreeVisibleScope>('all');

  const i18nPrefix = `${config.i18nNamespace}.${collectionType}`;
  const HeaderIcon = collectionIcons[collectionType];
  const isCollapsed = collapsed;
  const readOnlyScopes = capability?.readOnlyScopes ?? [];
  const api = useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);

  const effectiveScopes = useMemo(
    () => sortAgentSettingsScopeValues(capability?.scopes.length ? capability.scopes : ['project', 'user']),
    [capability?.scopes],
  );

  React.useEffect(() => {
    const nextScope = resolveAgentSettingsSelectedScope(scope, effectiveScopes);
    const nextVisibleScope: AgentFileTreeVisibleScope = nextScope === 'local'
      ? 'all'
      : nextScope;
    if (nextVisibleScope !== scope) {
      setScope(nextVisibleScope);
    }
  }, [effectiveScopes, scope]);

  const scopeLabels = useMemo(() => Object.fromEntries(
    effectiveScopes.map((scopeValue) => [scopeValue, t(`${i18nPrefix}.scope.${scopeValue}`)]),
  ) as Partial<Record<AgentFileTreeScope, string>>, [effectiveScopes, i18nPrefix, t]);

  const fileTreeAdapter = useMemo(() => createAgentFileTreeDataAdapter({
    workspaceId,
    apiPrefix: config.apiPathPrefix,
    scope,
    scopes: effectiveScopes,
    scopeLabels,
    collection: collectionType,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    queryClient,
  }), [
    collectionType,
    config.apiPathPrefix,
    effectiveScopes,
    scope,
    scopeLabels,
    workspaceId,
    workspaceRuntime.runtimeBaseUrl,
    queryClient,
  ]);
  const fileConflictTransport = useMemo(
    () => fileTreeAdapter.createConflictTransport(),
    [fileTreeAdapter],
  );

  const resourceIdentity = useMemo(
    () => createFileTreeResourceIdentity('agent-settings', {
      workspaceId,
      provider: config.apiPathPrefix,
      scope,
      scopes: effectiveScopes,
      collection: collectionType,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
    }),
    [collectionType, config.apiPathPrefix, effectiveScopes, scope, workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  const scopeOptions = useMemo(() => (['all', ...effectiveScopes] as AgentFileTreeVisibleScope[]).map((scopeValue) => {
    const Icon = scopeIcons[scopeValue] ?? FolderGit;
    return {
      value: scopeValue,
      label: t(`${i18nPrefix}.scope.${scopeValue}`),
      icon: <Icon className="h-3 w-3" />,
    };
  }), [effectiveScopes, i18nPrefix, t]);
  const visibleReadOnlyScopes = readOnlyScopes.filter(
    (scopeValue): scopeValue is AgentFileTreeScope => scopeValue !== 'local',
  );
  const effectiveReadOnlyScopes: AgentFileTreeVisibleScope[] = readOnly
    ? ['all', ...effectiveScopes]
    : ['all', ...visibleReadOnlyScopes];

  const refreshCollection = React.useCallback(async () => {
    if (readOnly) return;
    const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
    if (!runtimeBaseUrl) return;
    if (config.apiPathPrefix !== 'opencode') {
      await api.refreshCache(runtimeBaseUrl, workspaceId, {
        provider: config.apiPathPrefix,
        capability: collectionType,
        scope,
      });
    }
    await queryClient.removeQueries({
      queryKey: agentSettingsQueryKeys.collection({
        runtimeBaseUrl,
        workspaceId,
        provider: config.apiPathPrefix,
        capability: collectionType,
        scope,
      }),
      exact: true,
    });
  }, [
    api,
    collectionType,
    config.apiPathPrefix,
    queryClient,
    readOnly,
    scope,
    workspaceId,
    workspaceRuntime.runtimeBaseUrl,
  ]);

  return (
    <SettingsFileTreeWorkflow
      adapter={fileTreeAdapter}
      resourceIdentity={resourceIdentity}
      scope={scope}
      scopeOptions={scopeOptions}
      readOnlyScopes={effectiveReadOnlyScopes}
      labels={{
        title: t(`${i18nPrefix}.title`),
        scopeLabel: t(`${i18nPrefix}.scope.label`),
        searchPlaceholder: t(`${i18nPrefix}.searchPlaceholder`),
      }}
      icon={HeaderIcon}
      showHeader={showHeader}
      isCollapsed={isCollapsed}
      onToggleCollapse={() => undefined}
      onScopeChange={(value) => setScope(value)}
      onSelect={(file) => onSelect(file as AgentSelectedFile)}
      loadEnabled={Boolean(workspaceRuntime.runtimeBaseUrl)}
      refreshSignal={workspaceRuntime.runtimeBaseUrl}
      onRefresh={readOnly ? undefined : refreshCollection}
      loggerContext={{ collectionType, apiPrefix: config.apiPathPrefix }}
      fileConflictTransport={fileConflictTransport}
    />
  );
};

export default AgentFileManager;
