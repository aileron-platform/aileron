import React, { useMemo, useState } from 'react';
import { FolderGit, HardDrive, Puzzle, User, Wand2, ScrollText } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentFileTreeDataAdapter } from '../adapters/agentFileTreeDataAdapter';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentFileCollection, AgentSelectedFile, AgentToolConfig } from '../types';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { SettingsFileTreeWorkflow } from './SettingsFileTreeWorkflow';
import { sortAgentSettingsScopeValues } from './SettingsSourcePrimitives';
import type { AgentFileTreeScope, AgentFileTreeVisibleScope } from '../adapters/agentFileTreeDataAdapter';

interface AgentFileManagerProps {
  config: AgentToolConfig;
  collectionType: AgentFileCollection;
  onSelect: (file: AgentSelectedFile) => void;
  workspaceId: string;
}

const collectionIcons = {
  skills: Wand2,
  scripts: ScrollText,
};

const scopeIcons = {
  all: FolderGit,
  project: FolderGit,
  user: User,
  local: HardDrive,
  plugin: Puzzle,
  extension: Puzzle,
};

const AgentFileManager: React.FC<AgentFileManagerProps> = ({
  config,
  collectionType,
  onSelect,
  workspaceId,
}) => {
  const { t } = useI18n();
  const { layout, toggleSecondColumn, workspaceRuntime } = useWorkspace();
  const capability = config.capabilities[collectionType];
  const [scope, setScope] = useState<AgentFileTreeVisibleScope>('all');
  const [selectedPlugin, setSelectedPlugin] = useState('all');
  const [refreshToken, setRefreshToken] = useState(0);

  const i18nPrefix = `${config.i18nNamespace}.${collectionType}`;
  const HeaderIcon = collectionIcons[collectionType];
  const isCollapsed = layout.secondColumnCollapsed;
  const readOnlyScopes = capability?.readOnlyScopes ?? [];
  const api = useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);

  const { data: pluginSkillsData } = useQuery({
    queryKey: ['agent-plugin-skills', config.apiPathPrefix, workspaceId],
    queryFn: () => api.listPluginSkills(workspaceRuntime.runtimeBaseUrl || '', workspaceId),
    enabled: Boolean(
      workspaceId
      && workspaceRuntime.runtimeBaseUrl
      && config.apiPathPrefix !== 'codex'
      && collectionType === 'skills'
      && scope === 'plugin'
      && capability?.supportsPlugin,
    ),
  });

  const pluginSkills = pluginSkillsData?.plugins ?? [];

  const effectiveScopes = useMemo(
    () => sortAgentSettingsScopeValues(capability?.scopes.length ? capability.scopes : ['project', 'user']),
    [capability?.scopes],
  );

  React.useEffect(() => {
    if (scope !== 'all' && !effectiveScopes.includes(scope)) {
      setScope('all');
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
  }), [collectionType, config.apiPathPrefix, effectiveScopes, scope, scopeLabels, workspaceId, workspaceRuntime.runtimeBaseUrl]);

  const fileTreeAdapterKey = useMemo(
    () => JSON.stringify({
      workspaceId,
      apiPrefix: config.apiPathPrefix,
      scope,
      scopes: effectiveScopes,
      collection: collectionType,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
    }),
    [collectionType, config.apiPathPrefix, effectiveScopes, scope, workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: [collectionType],
    onRefresh: () => {
      setRefreshToken((current) => current + 1);
      return Promise.resolve();
    },
  });

  const scopeOptions = useMemo(() => (['all', ...effectiveScopes] as AgentFileTreeVisibleScope[]).map((scopeValue) => {
    const Icon = scopeIcons[scopeValue] ?? FolderGit;
    return {
      value: scopeValue,
      label: t(`${i18nPrefix}.scope.${scopeValue}`),
      icon: <Icon className="h-3 w-3" />,
    };
  }), [effectiveScopes, i18nPrefix, t]);

  const pluginSelector = scope === 'plugin' && pluginSkills.length > 0 ? (
    <div className="flex items-center gap-2">
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {t(`${i18nPrefix}.plugin.label`)}
      </span>
      <Select value={selectedPlugin} onValueChange={setSelectedPlugin}>
        <SelectTrigger className="h-7 w-32 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t(`${i18nPrefix}.plugin.all`)}</SelectItem>
          {pluginSkills.map((plugin) => {
            const pluginKey = `${plugin.pluginName}@${plugin.marketplaceName}:${plugin.skillName}`;
            return (
              <SelectItem key={pluginKey} value={pluginKey}>
                {plugin.pluginName} - {plugin.skillName}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  ) : null;

  return (
    <SettingsFileTreeWorkflow
      adapter={fileTreeAdapter}
      adapterKey={fileTreeAdapterKey}
      scope={scope}
      scopeOptions={scopeOptions}
      readOnlyScopes={['all', ...readOnlyScopes] as AgentFileTreeVisibleScope[]}
      labels={{
        title: t(`${i18nPrefix}.title`),
        scopeLabel: t(`${i18nPrefix}.scope.label`),
        searchPlaceholder: t(`${i18nPrefix}.searchPlaceholder`),
      }}
      icon={HeaderIcon}
      isCollapsed={isCollapsed}
      onToggleCollapse={toggleSecondColumn}
      onScopeChange={(value) => setScope(value)}
      onSelect={(file) => onSelect(file as AgentSelectedFile)}
      toolbarRightContent={pluginSelector}
      loadEnabled={Boolean(workspaceRuntime.runtimeBaseUrl)}
      refreshSignal={`${workspaceRuntime.runtimeBaseUrl ?? ''}:${refreshToken}`}
      loggerContext={{ collectionType, apiPrefix: config.apiPathPrefix }}
    />
  );
};

export default AgentFileManager;
