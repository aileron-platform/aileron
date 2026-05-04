import React, { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileCode2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  createAgentSettingsApi,
  type CodexFileSummary,
  type CodexRulesFileSummary,
  type CodexSubagentItem,
} from '../services/agentSettingsApi';
import { buildSidebarSourceOption, DocumentSidebar, type SidebarItem } from './shells/DocumentSidebar';

type CodexDocumentResource = 'subagents' | 'prompts' | 'rules';
type CodexDocumentSource = CodexFileSummary['source'] | CodexSubagentItem['source'];
type CodexDocumentScopeFilter = 'all' | CodexDocumentSource;

interface CodexDocumentSidebarProps {
  resource: CodexDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const EDITABLE_LAYERS = ['project', 'user'] as const;

const buildDocumentId = (source: string, path: string) => `${source}:${path}`;
const fileNameFromPath = (path: string) => path.split('/').filter(Boolean).pop() || path;

const mapRulesSummary = (source: 'project' | 'user', summary: CodexRulesFileSummary, t: (key: string, params?: Record<string, unknown>) => string): SidebarItem => ({
  id: buildDocumentId(source, summary.path),
  label: fileNameFromPath(summary.path),
  description: summary.path,
  source,
  sourceLabel: t(`workspace.agentSettings.codex.documents.scope.values.${source}`),
});

const mapFileSummary = (summary: CodexFileSummary, t: (key: string, params?: Record<string, unknown>) => string): SidebarItem => ({
  id: buildDocumentId(summary.source, summary.path),
  label: fileNameFromPath(summary.path),
  description: summary.path,
  source: summary.source,
  sourceLabel: t(`workspace.agentSettings.codex.documents.scope.values.${summary.source}`),
  readOnly: summary.readOnly,
  pluginName: typeof summary.metadata?.pluginName === 'string' ? summary.metadata.pluginName : undefined,
  marketplaceName: typeof summary.metadata?.marketplaceName === 'string' ? summary.metadata.marketplaceName : undefined,
});

const mapSubagentSummary = (item: CodexSubagentItem, t: (key: string, params?: Record<string, unknown>) => string): SidebarItem => ({
  id: item.id,
  label: fileNameFromPath(item.relativePath),
  description: item.relativePath,
  source: item.source,
  sourceLabel: t(`workspace.agentSettings.codex.documents.scope.values.${item.source}`),
  readOnly: item.readOnly,
  pluginName: item.pluginName ?? undefined,
  marketplaceName: item.marketplaceName ?? undefined,
  badges: item.effective ? [{ key: 'effective', label: t('workspace.agentSettings.codex.documents.status.effective') }] : undefined,
});

const CodexDocumentSidebar: React.FC<CodexDocumentSidebarProps> = ({ resource, selectedId, onSelect }) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [filterValue, setFilterValue] = React.useState<CodexDocumentScopeFilter>(resource === 'rules' ? 'project' : 'all');

  const documentsQuery = useQuery({
    queryKey: ['codex-document-sidebar', runtimeBaseUrl, workspaceId, resource],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      if (resource === 'subagents') {
        const response = await api.listCodexSubagents(runtimeBaseUrl || '', workspaceId || '');
        return response.items.map((item) => mapSubagentSummary(item, t)).sort((a, b) => a.description?.localeCompare(b.description ?? '') ?? 0);
      }

      const itemsById = new Map<string, SidebarItem>();
      for (const layer of EDITABLE_LAYERS) {
        if (resource === 'rules') {
          const response = await api.listCodexRules(runtimeBaseUrl || '', workspaceId || '', layer);
          for (const file of response.files) {
            const item = mapRulesSummary(layer, file, t);
            if (!itemsById.has(item.id)) {
              itemsById.set(item.id, item);
            }
          }
          continue;
        }

        const response = await api.listCodexFiles(runtimeBaseUrl || '', workspaceId || '', resource, layer);
        for (const file of response.files) {
          const item = mapFileSummary(file, t);
          if (!itemsById.has(item.id)) {
            itemsById.set(item.id, item);
          }
        }
      }
      return Array.from(itemsById.values()).sort((a, b) => (a.description ?? '').localeCompare(b.description ?? ''));
    },
  });

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
    <DocumentSidebar
      title={t(`workspace.agentSettings.codex.documents.meta.${resource}.title`)}
      icon={FileCode2}
      items={documentsQuery.data ?? []}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={documentsQuery.isLoading}
      isRefreshing={documentsQuery.isFetching}
      onRefresh={() => void documentsQuery.refetch()}
      filterValue={filterValue}
      onFilterChange={setFilterValue}
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
    />
  );
};

export default CodexDocumentSidebar;
