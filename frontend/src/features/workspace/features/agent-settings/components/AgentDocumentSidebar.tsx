import React, { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileCode2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import { buildSidebarSourceOption, DocumentSidebar, type SidebarItem } from './shells/DocumentSidebar';
import type { AgentDocument, AgentScope } from '../types';

type AgentDocumentResource = 'slash-commands' | 'subagents';
type AgentDocumentScopeFilter = 'all' | 'project' | 'user' | 'local' | 'plugin' | 'extension';

interface AgentDocumentSidebarProps {
  resource: AgentDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  apiPrefix?: string;
  availableScopes?: AgentScope[];
}

const mapDocumentToSidebarItem = (document: AgentDocument, i18nNamespace: string, t: (key: string, params?: Record<string, unknown>) => string): SidebarItem => ({
  id: document.id,
  label: document.title,
  description: typeof document.metadata?.fileName === 'string' ? document.metadata.fileName : document.title,
  source: document.scope,
  sourceLabel: t(`${i18nNamespace}.documents.scope.values.${document.scope}`, { defaultValue: document.scope }),
  sizeLabel: document.size ? t(`${i18nNamespace}.documents.size.badge`, { size: document.size }) : undefined,
  readOnly: document.scope === 'plugin' || document.scope === 'extension',
  pluginName: document.pluginName,
  marketplaceName: document.marketplaceName,
  extensionName: document.extensionName,
  extensionVersion: document.extensionVersion,
});

const AgentDocumentSidebar: React.FC<AgentDocumentSidebarProps> = ({
  resource,
  selectedId,
  onSelect,
  apiPrefix = 'claude-code',
  availableScopes,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [filterValue, setFilterValue] = React.useState<AgentDocumentScopeFilter>('all');

  const documentsQuery = useQuery({
    queryKey: ['agent-document-sidebar', runtimeBaseUrl, workspaceId, apiPrefix, resource],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      const documents = resource === 'subagents'
        ? await api.listSubagents(runtimeBaseUrl || '', workspaceId || '')
        : await api.listSlashCommands(runtimeBaseUrl || '', workspaceId || '');

      if (!availableScopes?.length) {
        return documents;
      }
      return documents.filter((document) => availableScopes.includes(document.scope));
    },
  });

  useEffect(() => {
    if (filterValue !== 'all' && availableScopes?.length && !availableScopes.includes(filterValue as AgentScope)) {
      setFilterValue('all');
    }
  }, [availableScopes, filterValue]);

  const i18nNamespace = 'workspace.agentSettings.common';
  const items = useMemo(
    () => (documentsQuery.data ?? []).map((document) => mapDocumentToSidebarItem(document, i18nNamespace, t)),
    [documentsQuery.data, t],
  );

  const filterOptions = useMemo(() => {
    const values = new Set<AgentDocumentScopeFilter>(['all']);
    for (const item of items) {
      values.add(item.source);
    }
    for (const scope of availableScopes ?? []) {
      values.add(scope);
    }
    return Array.from(values).map((value) => (
      value === 'all'
        ? buildSidebarSourceOption(value, t(`${i18nNamespace}.documents.sidebar.scope.all`))
        : buildSidebarSourceOption(value, t(`${i18nNamespace}.documents.scope.values.${value}`, { defaultValue: value }))
    ));
  }, [availableScopes, items, t]);

  return (
    <DocumentSidebar
      title={t(`${i18nNamespace}.documents.meta.${resource}.title`)}
      icon={FileCode2}
      items={items}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={documentsQuery.isLoading}
      isRefreshing={documentsQuery.isFetching}
      onRefresh={() => void documentsQuery.refetch()}
      filterValue={filterValue}
      onFilterChange={setFilterValue}
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
    />
  );
};

export default AgentDocumentSidebar;
