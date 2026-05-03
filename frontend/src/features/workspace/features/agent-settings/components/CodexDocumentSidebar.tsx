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
import {
  createAgentSettingsApi,
  type CodexFileSummary,
  type CodexRulesFileSummary,
  type CodexSubagentItem,
} from '../services/agentSettingsApi';

type CodexDocumentResource = 'subagents' | 'prompts' | 'rules';
type CodexDocumentSource = CodexFileSummary['source'] | CodexSubagentItem['source'];
type CodexDocumentScopeFilter = 'all' | CodexDocumentSource;

interface CodexSidebarDocument {
  id: string;
  name: string;
  path: string;
  sizeBytes: number;
  source: CodexDocumentSource;
  readOnly: boolean;
  metadata: Record<string, unknown>;
}

interface CodexDocumentSidebarProps {
  resource: CodexDocumentResource;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const EDITABLE_LAYERS = ['project', 'user'] as const;

const buildDocumentId = (source: string, path: string) => `${source}:${path}`;

const fileNameFromPath = (path: string) => path.split('/').filter(Boolean).pop() || path;

const sourceIconMap = {
  all: Layers,
  project: FolderGit,
  user: User,
  plugin: Puzzle,
  built_in: Puzzle,
} satisfies Record<CodexDocumentScopeFilter, React.ComponentType<{ className?: string }>>;

const sourceClass = (source: CodexDocumentSource) => (
  source === 'built_in'
    ? 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700'
    : source === 'project' || source === 'user' || source === 'plugin'
    ? SCOPE_BADGE_CLASSES[source]
    : SCOPE_BADGE_CLASSES.plugin
);

const mapRulesSummary = (source: 'project' | 'user', summary: CodexRulesFileSummary): CodexSidebarDocument => ({
  id: buildDocumentId(source, summary.path),
  ...summary,
  source,
  readOnly: false,
  metadata: {},
});

const mapFileSummary = (summary: CodexFileSummary): CodexSidebarDocument => ({
  id: buildDocumentId(summary.source, summary.path),
  name: summary.name,
  path: summary.path,
  sizeBytes: summary.sizeBytes,
  source: summary.source,
  readOnly: summary.readOnly,
  metadata: summary.metadata,
});

const mapSubagentSummary = (item: CodexSubagentItem): CodexSidebarDocument => ({
  id: item.id,
  name: item.name,
  path: item.relativePath,
  sizeBytes: item.content.length,
  source: item.source,
  readOnly: item.readOnly,
  metadata: item.metadata,
});

const CodexDocumentSidebar: React.FC<CodexDocumentSidebarProps> = ({ resource, selectedId, onSelect }) => {
  const { t } = useI18n();
  const { layout, toggleSecondColumn, workspaceRuntime } = useWorkspace();
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState<CodexDocumentScopeFilter>(resource === 'rules' ? 'project' : 'all');
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const isCollapsed = layout.secondColumnCollapsed;
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const Icon = resource === 'subagents'
    ? CLAUDE_CODE_ICONS.subagents
    : resource === 'rules'
      ? CLAUDE_CODE_ICONS.rules
      : CLAUDE_CODE_ICONS['slash-commands'];

  const documentsQuery = useQuery({
    queryKey: ['codex-document-sidebar', runtimeBaseUrl, workspaceId, resource],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      if (resource === 'subagents') {
        const response = await api.listCodexSubagents(runtimeBaseUrl || '', workspaceId || '');
        return response.items.map(mapSubagentSummary).sort((a, b) => a.path.localeCompare(b.path));
      }

      const summariesById = new Map<string, CodexSidebarDocument>();
      for (const layer of EDITABLE_LAYERS) {
        const response = resource === 'rules'
          ? await api.listCodexRules(runtimeBaseUrl || '', workspaceId || '', layer)
          : await api.listCodexFiles(runtimeBaseUrl || '', workspaceId || '', resource, layer);
        const files = resource === 'rules'
          ? response.files.map((summary) => mapRulesSummary(layer, summary as CodexRulesFileSummary))
          : response.files.map((summary) => mapFileSummary(summary as CodexFileSummary));
        for (const summary of files) {
          if (!summariesById.has(summary.id)) {
            summariesById.set(summary.id, summary);
          }
        }
      }
      return Array.from(summariesById.values()).sort((a, b) => a.path.localeCompare(b.path));
    },
  });

  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);
  const scopeOptions: CodexDocumentScopeFilter[] = resource === 'rules'
    ? ['project', 'user']
    : ['all', 'project', 'user', 'plugin', 'built_in'];
  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((document) => {
      const matchesScope = scope === 'all' || document.source === scope;
      const matchesSearch = query.length === 0
        || document.path.toLowerCase().includes(query)
        || document.name.toLowerCase().includes(query);
      return matchesScope && matchesSearch;
    });
  }, [documents, scope, search]);

  useEffect(() => {
    setScope(resource === 'rules' ? 'project' : 'all');
  }, [resource]);

  useEffect(() => {
    const selectedExists = selectedId
      ? documents.some((document) => document.id === selectedId)
      : false;
    if (filteredDocuments.length > 0 && (!selectedId || !selectedExists)) {
      onSelect(filteredDocuments[0].id);
    }
  }, [documents, filteredDocuments, onSelect, selectedId]);

  const title = t(`workspace.agentSettings.codex.documents.meta.${resource}.title`);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div className={`flex h-10 items-center border-b border-border bg-card px-3 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!isCollapsed ? (
          <div className="flex min-w-0 items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
            <span className="truncate text-sm font-medium">{title}</span>
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
              aria-label={t('workspace.agentSettings.codex.documents.actions.refresh')}
              title={t('workspace.agentSettings.codex.documents.actions.refresh')}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${documentsQuery.isFetching ? 'animate-spin' : ''}`} />
            </Button>
          ) : null}
          <button
            type="button"
            onClick={toggleSecondColumn}
            className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
            aria-label={isCollapsed
              ? t('workspace.agentSettings.codex.documents.sidebar.toggle.expand')
              : t('workspace.agentSettings.codex.documents.sidebar.toggle.collapse')}
            title={isCollapsed
              ? t('workspace.agentSettings.codex.documents.sidebar.toggle.expand')
              : t('workspace.agentSettings.codex.documents.sidebar.toggle.collapse')}
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
                placeholder={t('workspace.agentSettings.codex.documents.sidebar.searchPlaceholder')}
                className="h-7 pl-8 text-xs"
              />
            </div>
            <Select value={scope} onValueChange={(value) => setScope(value as CodexDocumentScopeFilter)}>
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
                          ? t('workspace.agentSettings.codex.documents.sidebar.scope.all')
                          : t(`workspace.agentSettings.codex.documents.scope.values.${value}`)}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto p-2">
            {documentsQuery.isFetching && documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.agentSettings.codex.documents.sidebar.loading')}
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.agentSettings.codex.documents.sidebar.empty')}
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
                          <div className="truncate text-sm font-medium">{fileNameFromPath(document.path)}</div>
                        </div>
                        <div className="truncate text-xs text-muted-foreground">{document.path}</div>
                      </div>
                      <Badge variant="outline" className={`flex-shrink-0 whitespace-nowrap px-1 py-0 text-[10px] ${sourceClass(document.source)}`}>
                        {t(`workspace.agentSettings.codex.documents.scope.values.${document.source}`)}
                      </Badge>
                    </div>
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

export default CodexDocumentSidebar;
