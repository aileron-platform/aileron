import React, { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileCode2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../api/agentSettingsApi';
import { createSlashCommandSource } from '../capabilities/slash-commands/slashCommandSource';
import { createOutputStyleSource } from '../capabilities/output-styles/outputStyleSource';
import { createSubagentSource } from '../capabilities/subagents/subagentSource';
import { createMemorySource } from '../capabilities/memory/memorySource';
import { agentSettingsQueryKeys } from '../api/agentSettingsQueryKeys';
import { sortAgentSettingsScopeValues } from './AgentSettingsSourceControls';
import { getAgentDocumentActionPolicy } from '../agentSettingsScopeModel';
import {
  AgentSettingsDocumentSidebar,
  buildSidebarSourceOption,
  type AgentSettingsDocumentSidebarItem,
} from './shells/AgentSettingsDocumentSidebar';
import type { AgentDocument, AgentScope } from '../model/documents';

type AgentDocumentResource = 'slash-commands' | 'output-styles' | 'subagents' | 'memory';
type AgentDocumentScopeFilter = 'all' | 'project' | 'user' | 'local' | 'plugin';

interface AgentDocumentSidebarProps {
  resource: AgentDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  apiPrefix?: string;
  availableScopes?: AgentScope[];
  collapsed?: boolean;
  showHeader?: boolean;
}

const mapDocumentToSidebarItem = (
  document: AgentDocument,
  i18nNamespace: string,
  t: (key: string, params?: Record<string, unknown>) => string,
): AgentSettingsDocumentSidebarItem => ({
  id: document.id,
  label: document.title,
  description: typeof document.metadata?.fileName === 'string' ? document.metadata.fileName : document.title,
  source: document.scope,
  sourceLabel: t(`${i18nNamespace}.documents.scope.values.${document.scope}`, { defaultValue: document.scope }),
  sizeLabel: document.size ? t(`${i18nNamespace}.documents.size.badge`, { size: document.size }) : undefined,
  readOnly: getAgentDocumentActionPolicy(document).readOnly,
  pluginName: document.pluginName,
  marketplaceName: document.marketplaceName,
});

const AgentDocumentSidebar: React.FC<AgentDocumentSidebarProps> = ({
  resource,
  selectedId,
  onSelect,
  apiPrefix = 'claude-code',
  availableScopes,
  collapsed = false,
  showHeader = true,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [filterValue, setFilterValue] = React.useState<AgentDocumentScopeFilter>('all');
  const source = useMemo(() => {
    const runtime = runtimeBaseUrl ?? '';
    const workspace = workspaceId ?? '';
    if (resource === 'subagents') {
      return createSubagentSource(api, runtime, workspace);
    }
    if (resource === 'output-styles') {
      return createOutputStyleSource(api, runtime, workspace);
    }
    if (resource === 'memory') {
      return createMemorySource(api, runtime, workspace);
    }
    return createSlashCommandSource(api, runtime, workspace);
  }, [api, resource, runtimeBaseUrl, workspaceId]);

  const documentsQuery = useQuery({
    queryKey: agentSettingsQueryKeys.documentCollection(
      runtimeBaseUrl ?? '',
      workspaceId ?? '',
      resource,
      apiPrefix,
    ),
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: () => source.list(),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (filterValue !== 'all' && availableScopes?.length && !availableScopes.includes(filterValue as AgentScope)) {
      setFilterValue('all');
    }
  }, [availableScopes, filterValue]);

  const i18nNamespace = apiPrefix === 'claude-code' ? 'workspace.claudeCode' : 'workspace.agentSettings.common';
  const items = useMemo<AgentSettingsDocumentSidebarItem[]>(
    () => (documentsQuery.data?.items ?? [])
      .filter((document: AgentDocument) => (
        !availableScopes?.length || availableScopes.includes(document.scope)
      ))
      .map((document: AgentDocument) => mapDocumentToSidebarItem(document, i18nNamespace, t)),
    [availableScopes, documentsQuery.data?.items, i18nNamespace, t],
  );

  const filterOptions = useMemo(() => {
    const values = new Set<AgentDocumentScopeFilter>(['all']);
    for (const item of items) {
      if (
        item.source === 'project'
        || item.source === 'user'
        || item.source === 'local'
        || item.source === 'plugin'
      ) {
        values.add(item.source);
      }
    }
    for (const scope of availableScopes ?? []) {
      values.add(scope);
    }
    const sortedValues = [
      'all' as AgentDocumentScopeFilter,
      ...sortAgentSettingsScopeValues(Array.from(values).filter((value) => value !== 'all')),
    ];
    return sortedValues.map((value) => (
      value === 'all'
        ? buildSidebarSourceOption(value, t(`${i18nNamespace}.documents.sidebar.scope.all`))
        : buildSidebarSourceOption(value, t(`${i18nNamespace}.documents.scope.values.${value}`, { defaultValue: value }))
    ));
  }, [availableScopes, i18nNamespace, items, t]);

  return (
    <AgentSettingsDocumentSidebar
      title={t(`${i18nNamespace}.documents.meta.${resource}.title`)}
      icon={FileCode2}
      items={items}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={documentsQuery.isLoading}
      isRefreshing={documentsQuery.isFetching}
      onRefresh={() => void documentsQuery.refetch()}
      filterValue={filterValue}
      onFilterChange={(value) => setFilterValue(value as AgentDocumentScopeFilter)}
      filterOptions={filterOptions}
      filterLabel={t(`${i18nNamespace}.documents.sidebar.scope.label`, { defaultValue: '' })}
      labels={{
        searchPlaceholder: t(`${i18nNamespace}.documents.sidebar.searchPlaceholder`),
        loading: t(`${i18nNamespace}.documents.sidebar.loading`),
        empty: t(`${i18nNamespace}.documents.sidebar.empty`),
        refresh: t(`${i18nNamespace}.documents.actions.refresh`),
        toggleCollapse: t(`${i18nNamespace}.documents.sidebar.toggle.collapse`),
        toggleExpand: t(`${i18nNamespace}.documents.sidebar.toggle.expand`),
        readOnly: t('workspace.agentSettings.common.sourceNotices.readOnly.title'),
      }}
      showHeader={showHeader}
      collapsed={collapsed}
    />
  );
};

export default AgentDocumentSidebar;
