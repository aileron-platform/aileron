import React, { useMemo, useState } from 'react';
import { FolderGit, Puzzle, User, Wand2, ScrollText } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentFileTreeDataAdapter } from '../adapters/agentFileTreeDataAdapter';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentFileCollection, AgentSelectedFile, AgentToolConfig } from '../types';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { SettingsFileTreeWorkflow } from './SettingsFileTreeWorkflow';

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
  project: FolderGit,
  user: User,
  plugin: Puzzle,
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
  const scopes = capability?.scopes.length ? capability.scopes : ['project', 'user'];
  const [scope, setScope] = useState<AgentSelectedFile['scope']>(scopes[0] ?? 'project');
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
    enabled: Boolean(workspaceId && workspaceRuntime.runtimeBaseUrl && collectionType === 'skills' && scope === 'plugin' && capability?.supportsPlugin),
  });

  const pluginSkills = pluginSkillsData?.plugins ?? [];

  const fileTreeAdapter = useMemo(() => createAgentFileTreeDataAdapter({
    workspaceId,
    apiPrefix: config.apiPathPrefix,
    scope,
    collection: collectionType,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
  }), [collectionType, config.apiPathPrefix, scope, workspaceId, workspaceRuntime.runtimeBaseUrl]);

  const fileTreeAdapterKey = useMemo(
    () => JSON.stringify({
      workspaceId,
      apiPrefix: config.apiPathPrefix,
      scope,
      collection: collectionType,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
    }),
    [collectionType, config.apiPathPrefix, scope, workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: [collectionType],
    onRefresh: () => {
      setRefreshToken((current) => current + 1);
      return Promise.resolve();
    },
  });

  const scopeOptions = useMemo(() => scopes.map((scopeValue) => {
    const Icon = scopeIcons[scopeValue] ?? FolderGit;
    return {
      value: scopeValue,
      label: t(`${i18nPrefix}.scope.${scopeValue}`),
      icon: <Icon className="h-3 w-3" />,
    };
  }), [i18nPrefix, scopes, t]);

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
      readOnlyScopes={readOnlyScopes as AgentSelectedFile['scope'][]}
      labels={{
        title: t(`${i18nPrefix}.title`),
        scopeLabel: t(`${i18nPrefix}.scope.label`),
        searchPlaceholder: t(`${i18nPrefix}.searchPlaceholder`),
      }}
      icon={HeaderIcon}
      isCollapsed={isCollapsed}
      onToggleCollapse={toggleSecondColumn}
      onScopeChange={(value) => setScope(value)}
      onSelect={onSelect}
      toolbarRightContent={pluginSelector}
      loadEnabled={Boolean(workspaceRuntime.runtimeBaseUrl)}
      refreshSignal={`${workspaceRuntime.runtimeBaseUrl ?? ''}:${refreshToken}`}
      loggerContext={{ collectionType, apiPrefix: config.apiPathPrefix }}
    />
  );
};

export default AgentFileManager;
