import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, FileText, FolderGit, Layers, Puzzle, RefreshCw, Search, User } from 'lucide-react';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentDocument } from '../types';

type AgentDocumentResource = 'slash-commands' | 'subagents';
type AgentDocumentScopeFilter = 'all' | 'project' | 'user' | 'local' | 'plugin' | 'built_in';
type AgentDocumentSource = Exclude<AgentDocumentScopeFilter, 'all'>;

interface AgentDocumentSidebarProps {
  resource: AgentDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  apiPrefix?: string;
  availableScopes?: Array<'project' | 'user' | 'local' | 'plugin'>;
}

interface SelectableDocument {
  id: string;
  title: string;
  source: AgentDocumentSource;
  size?: string;
  metadata: Record<string, unknown>;
}

const sourceIconMap = {
  all: Layers,
  project: FolderGit,
  user: User,
  plugin: Puzzle,
  local: Puzzle,
  built_in: Puzzle,
} satisfies Record<AgentDocumentScopeFilter, React.ComponentType<{ className?: string }>>;

const sourceClass = (source: AgentDocumentScopeFilter) => (
  source === 'project'
    ? SCOPE_BADGE_CLASSES.project
    : source === 'user'
      ? SCOPE_BADGE_CLASSES.user
      : source === 'plugin'
        ? SCOPE_BADGE_CLASSES.plugin
        : source === 'local'
          ? SCOPE_BADGE_CLASSES.local
          : 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700'
);

const fileNameFromDocument = (document: SelectableDocument): string => {
  const fileName = document.metadata.fileName;
  return typeof fileName === 'string' ? fileName : document.title;
};

const AgentDocumentSidebar: React.FC<AgentDocumentSidebarProps> = ({
  resource,
  selectedId,
  onSelect,
  apiPrefix = 'claude-code',
  availableScopes,
}) => {
  const { t } = useI18n();
  const { layout, toggleSecondColumn, workspaceRuntime } = useWorkspace();
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState<AgentDocumentScopeFilter>('all');
  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const isCollapsed = layout.secondColumnCollapsed;
  const Icon = resource === 'subagents'
    ? CLAUDE_CODE_ICONS.subagents
    : CLAUDE_CODE_ICONS['slash-commands'];
  const title = t(`workspace.agentSettings.common.documents.meta.${resource}.title`);

  const documentsQuery = useQuery({
    queryKey: ['agent-document-sidebar', runtimeBaseUrl, workspaceId, apiPrefix, resource],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      const documents = resource === 'subagents'
        ? await api.listSubagents(runtimeBaseUrl || '', workspaceId || '')
        : await api.listSlashCommands(runtimeBaseUrl || '', workspaceId || '');

      const docs = [...documents];
      if (availableScopes?.length) {
        return docs.filter((document) => availableScopes.includes(document.scope as never));
      }
      return docs;
    },
  });

  const documents = useMemo<SelectableDocument[]>(() => {
    return (documentsQuery.data ?? []).map((document) => ({
      id: document.id,
      title: document.title,
      source: (document.scope as AgentDocumentSource) ?? 'project',
      size: document.size,
      metadata: document.metadata ?? {},
    }));
  }, [documentsQuery.data]);

  const scopeOptions: AgentDocumentScopeFilter[] = useMemo(() => {
    const scopes = new Set<AgentDocumentScopeFilter>(['all']);
    for (const scopeValue of documents.map((document) => document.source)) {
      scopes.add(scopeValue);
    }
    if (availableScopes?.includes('project')) scopes.add('project');
    if (availableScopes?.includes('user')) scopes.add('user');
    if (availableScopes?.includes('local')) scopes.add('local');
    if (availableScopes?.includes('plugin')) scopes.add('plugin');
    return ['all', ...Array.from(scopes).filter((item) => item !== 'all')] as AgentDocumentScopeFilter[];
  }, [availableScopes, documents]);

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const sourceMatch = scope === 'all' || document.source === scope;
      const titleMatch = document.title.toLowerCase().includes(query);
      const fileNameMatch = fileNameFromDocument(document).toLowerCase().includes(query);

      return sourceMatch && (query.length === 0 || titleMatch || fileNameMatch);
    });
  }, [documents, scope, search]);

  useEffect(() => {
    if (!documents.length) return;
    const selectedExists = documents.some((document) => document.id === selectedId);
    if (!selectedId || !selectedExists) {
      onSelect(documents[0]?.id ?? null);
    }
  }, [documents, onSelect, selectedId]);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div className={`flex h-10 items-center border-b border-border bg-card px-3 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!isCollapsed ? (
          <div className="flex min-w-0 items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
            <span className="truncate text-sm font-medium">{title || t('workspace.agentSettings.common.documents.sidebar.defaultTitle')}</span>
          </div>
        ) : null}
        <div className="flex flex-shrink-0 items-center gap-1">
          {!isCollapsed ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => void documentsQuery.refetch()}
              disabled={documentsQuery.isFetching}
              aria-label={t('workspace.agentSettings.common.documents.actions.refresh')}
              title={t('workspace.agentSettings.common.documents.actions.refresh')}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${documentsQuery.isFetching ? 'animate-spin' : ''}`} />
            </Button>
          ) : null}
          <button
            type="button"
            onClick={toggleSecondColumn}
            className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
            aria-label={isCollapsed
              ? t('workspace.agentSettings.common.documents.sidebar.toggle.expand')
              : t('workspace.agentSettings.common.documents.sidebar.toggle.collapse')}
            title={isCollapsed
              ? t('workspace.agentSettings.common.documents.sidebar.toggle.expand')
              : t('workspace.agentSettings.common.documents.sidebar.toggle.collapse')}
          >
            <ChevronLeft className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder icon={Icon} className="text-primary" iconClassName="text-primary" />
      ) : (
        <>
          <div className="space-y-2 border-b border-border bg-muted/30 p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('workspace.agentSettings.common.documents.sidebar.searchPlaceholder')}
                className="h-7 pl-8 text-xs"
              />
            </div>
            <Select value={scope} onValueChange={(value) => setScope(value as AgentDocumentScopeFilter)}>
              <SelectTrigger className="h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {scopeOptions.map((value) => {
                  const SourceIcon = sourceIconMap[value];
                  return (
                    <SelectItem key={value} value={value}>
                      <div className="flex items-center gap-2">
                        <SourceIcon className="h-3 w-3" />
                        {value === 'all'
                          ? t('workspace.agentSettings.common.documents.sidebar.scope.all')
                          : t(`workspace.agentSettings.common.documents.scope.values.${value}`, { defaultValue: value })}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto p-2">
            {documentsQuery.isLoading && documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.agentSettings.common.documents.sidebar.loading')}
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.agentSettings.common.documents.sidebar.empty')}
              </div>
            ) : (
              filteredDocuments.map((document) => {
                const isActive = document.id === selectedId;
                return (
                  <button
                    key={document.id}
                    type="button"
                    onClick={() => onSelect(document.id)}
                    className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                      isActive
                        ? 'border-primary/60 bg-primary/10 shadow-sm'
                        : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                          <div className="truncate text-sm font-medium">{document.title}</div>
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {fileNameFromDocument(document)}
                        </div>
                      </div>
                      <Badge variant="outline" className={`flex-shrink-0 whitespace-nowrap px-1 py-0 text-[10px] ${sourceClass(document.source)}`}>
                        {t(`workspace.agentSettings.common.documents.scope.values.${document.source}`, { defaultValue: document.source })}
                      </Badge>
                    </div>
                    {document.size ? (
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {t('workspace.agentSettings.common.documents.size.badge', { size: document.size })}
                      </div>
                    ) : null}
                  </button>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default AgentDocumentSidebar;
