import React, { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileCode2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  createAgentSettingsApi,
} from '../api/agentSettingsApi';
import {
  AgentSettingsDocumentSidebar,
  buildSidebarSourceOption,
  type AgentSettingsDocumentSidebarItem,
} from './shells/AgentSettingsDocumentSidebar';
import { createCodexDocumentSource } from '../capabilities/slash-commands/codexDocumentSource';
import { createCodexRulesSource } from '../capabilities/rules/codexRulesSource';
import { createCodexSubagentSource } from '../capabilities/subagents/codexSubagentSource';
import type { DocumentResourceItem } from '@/shared/components/document-resource';

type CodexDocumentResource = 'subagents' | 'prompts' | 'rules';
type CodexDocumentSource = 'project' | 'user' | 'plugin' | 'built_in';
type CodexDocumentScopeFilter = 'all' | CodexDocumentSource;

interface CodexDocumentSidebarProps {
  resource: CodexDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  collapsed?: boolean;
  showHeader?: boolean;
}

const mapDocumentSummary = (
  document: DocumentResourceItem,
  t: (key: string, params?: Record<string, unknown>) => string,
): AgentSettingsDocumentSidebarItem => ({
  id: document.id,
  label: document.title,
  description: typeof document.metadata?.relativePath === 'string'
    ? document.metadata.relativePath
    : document.title,
  source: document.scope,
  sourceLabel: t(
    `workspace.agentSettings.codex.documents.scope.values.${document.scope}`,
  ),
  readOnly: document.scope === 'plugin'
    || document.metadata?.readOnly === true,
  pluginName: document.pluginName,
  marketplaceName: document.marketplaceName,
  badges: document.metadata?.effective === true
    ? [{
      key: 'effective',
      label: t('workspace.agentSettings.codex.documents.status.effective'),
    }]
    : undefined,
});

const CodexDocumentSidebar: React.FC<CodexDocumentSidebarProps> = ({ resource, selectedId, onSelect, collapsed = false, showHeader = true }) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [filterValue, setFilterValue] = React.useState<CodexDocumentScopeFilter>(resource === 'rules' ? 'project' : 'all');
  const source = useMemo(() => {
    if (resource === 'subagents') {
      return createCodexSubagentSource(
        api,
        runtimeBaseUrl ?? '',
        workspaceId ?? '',
      );
    }
    if (resource === 'rules') {
      return createCodexRulesSource(
        api,
        runtimeBaseUrl ?? '',
        workspaceId ?? '',
      );
    }
    return createCodexDocumentSource(
      api,
      runtimeBaseUrl ?? '',
      workspaceId ?? '',
      'prompts',
    );
  }, [api, resource, runtimeBaseUrl, workspaceId]);

  const documentsQuery = useQuery({
    queryKey: [
      'document-resource',
      runtimeBaseUrl ?? '',
      workspaceId ?? '',
      resource,
      'codex',
    ],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: () => source.list(),
    staleTime: 30_000,
  });
  const items = useMemo(
    () => (documentsQuery.data?.items ?? [])
      .map((document) => mapDocumentSummary(document, t))
      .sort((a, b) =>
        (a.description ?? '').localeCompare(b.description ?? '')),
    [documentsQuery.data?.items, t],
  );

  const filterOptions = useMemo(() => {
    const baseValues: CodexDocumentScopeFilter[] = resource === 'rules'
      ? ['project', 'user']
      : ['all', 'project', 'user', 'plugin', 'built_in'];
    return baseValues.map((value) => (
      value === 'all'
        ? buildSidebarSourceOption(value, t('workspace.agentSettings.codex.documents.sidebar.scope.all'))
        : buildSidebarSourceOption(value, t(`workspace.agentSettings.codex.documents.scope.values.${value}`))
    ));
  }, [resource, t]);

  useEffect(() => {
    setFilterValue(resource === 'rules' ? 'project' : 'all');
  }, [resource]);

  return (
    <AgentSettingsDocumentSidebar
      title={t(`workspace.agentSettings.codex.documents.meta.${resource}.title`)}
      icon={FileCode2}
      items={items}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={documentsQuery.isLoading}
      isRefreshing={documentsQuery.isFetching}
      onRefresh={() => void documentsQuery.refetch()}
      filterValue={filterValue}
      onFilterChange={value => setFilterValue(value as CodexDocumentScopeFilter)}
      filterOptions={filterOptions}
      filterLabel={t('workspace.agentSettings.codex.hooks.filters.scope.label')}
      labels={{
        searchPlaceholder: t('workspace.agentSettings.codex.documents.sidebar.searchPlaceholder'),
        loading: t('workspace.agentSettings.codex.documents.sidebar.loading'),
        empty: t('workspace.agentSettings.codex.documents.sidebar.empty'),
        refresh: t('workspace.agentSettings.codex.documents.actions.refresh'),
        toggleCollapse: t('workspace.agentSettings.codex.documents.sidebar.toggle.collapse'),
        toggleExpand: t('workspace.agentSettings.codex.documents.sidebar.toggle.expand'),
        readOnly: t('workspace.agentSettings.common.sourceNotices.readOnly.title'),
      }}
      showHeader={showHeader}
      collapsed={collapsed}
    />
  );
};

export default CodexDocumentSidebar;
