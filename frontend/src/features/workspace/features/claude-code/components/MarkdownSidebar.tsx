import React, { useMemo, useState, useContext } from 'react';
import { ChevronLeft, Search, Puzzle, Layers, FolderGit, User, HardDrive, RefreshCw } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import { SCOPE_BADGE_CLASSES } from '../../agent-settings/constants/scopeStyles';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import type { ClaudeScope } from '../types';

export type MarkdownDocumentView = 'slash-commands' | 'output-styles' | 'subagents' | 'memory';

interface MarkdownSidebarProps {
  subView: MarkdownDocumentView;
  availableScopes?: ClaudeScope[];
}

const ClaudeCodeLoadingState: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
      <p>{t('workspace.claudeCode.documents.loading')}</p>
    </div>
  );
};

const MarkdownSidebarContent: React.FC<MarkdownSidebarProps> = ({ subView, availableScopes: availableScopesProp }) => {
  const { layout, toggleSecondColumn } = useWorkspace();
  const isCollapsed = layout.secondColumnCollapsed;
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState<'all' | 'project' | 'user' | 'local' | 'plugin'>('all');
  const { t } = useI18n();
  const { slashCommands, outputStyles, subagents, memory } = useClaudeCode();

  const collection = useMemo(() => {
    switch (subView) {
      case 'slash-commands':
        return slashCommands;
      case 'output-styles':
        return outputStyles;
      case 'subagents':
        return subagents;
      case 'memory':
        return memory;
      default:
        return slashCommands;
    }
  }, [subView, slashCommands, outputStyles, subagents, memory]);

  const showScopeFilter = subView !== 'memory';
  const showScopeBadges = subView !== 'memory';

  // Resolve available scope options for each subview.
  const availableScopes = useMemo<ReadonlyArray<'all' | 'project' | 'user' | 'local' | 'plugin'>>(() => {
    // Subview-level scope limits.
    let subViewScopes: ClaudeScope[];
    switch (subView) {
      case 'output-styles':
        subViewScopes = ['project', 'user'];
        break;
      case 'slash-commands':
      case 'subagents':
      case 'memory':
      default:
        subViewScopes = ['project', 'user', 'local', 'plugin'];
        break;
    }

    // Intersect explicit scope props with the subview limits when provided.
    const effectiveScopes = availableScopesProp
      ? subViewScopes.filter((s) => availableScopesProp.includes(s))
      : subViewScopes;

    return ['all', ...effectiveScopes] as ReadonlyArray<'all' | 'project' | 'user' | 'local' | 'plugin'>;
  }, [subView, availableScopesProp]);

  const documents = collection.items;
  const selectedId = collection.selectedId;

  // Pick an icon for the active subview.
  const Icon = useMemo(() => {
    switch (subView) {
      case 'slash-commands':
        return CLAUDE_CODE_ICONS['slash-commands'];
      case 'output-styles':
        return CLAUDE_CODE_ICONS['output-styles'];
      case 'subagents':
        return CLAUDE_CODE_ICONS['subagents'];
      case 'memory':
        return CLAUDE_CODE_ICONS['memory'];
      default:
        return CLAUDE_CODE_ICONS['slash-commands'];
    }
  }, [subView]);

  const metaLabelKey = `workspace.claudeCode.documents.meta.${subView}.title`;
  const translatedMetaLabel = t(metaLabelKey);
  const fallbackMetaLabel = t('workspace.claudeCode.documents.sidebar.defaultTitle');
  const metaLabel = translatedMetaLabel === metaLabelKey ? fallbackMetaLabel : translatedMetaLabel;

  const filteredDocs = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((doc) => {
      const matchesScope = !showScopeFilter || scope === 'all' || doc.scope === scope;
      const matchesSearch =
        query.length === 0 ||
        doc.title.toLowerCase().includes(query) ||
        doc.description.toLowerCase().includes(query) ||
        doc.content.toLowerCase().includes(query);
      return matchesScope && matchesSearch;
    });
  }, [documents, scope, search, showScopeFilter]);

  const activeId = selectedId ?? (filteredDocs[0]?.id ?? null);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div
        className={`flex items-center h-10 border-b border-border bg-card px-3 ${
          isCollapsed ? 'justify-center' : 'justify-between'
        }`}
      >
        {!isCollapsed ? (
          <div className="flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 text-primary" />
            <span className="text-sm font-medium">
              {metaLabel}
            </span>
          </div>
        ) : null}
        <div className="flex flex-shrink-0 items-center gap-1">
          {!isCollapsed ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => void collection.refresh()}
              disabled={collection.loading}
              aria-label={t('workspace.claudeCode.documents.actions.refresh')}
              title={t('workspace.claudeCode.documents.actions.refresh')}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${collection.loading ? 'animate-spin' : ''}`} />
            </Button>
          ) : null}
          <button
            onClick={toggleSecondColumn}
            className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
            aria-label={isCollapsed
              ? t('workspace.claudeCode.documents.sidebar.toggle.expand')
              : t('workspace.claudeCode.documents.sidebar.toggle.collapse')}
            title={isCollapsed
              ? t('workspace.claudeCode.documents.sidebar.toggle.expand')
              : t('workspace.claudeCode.documents.sidebar.toggle.collapse')}
          >
            <ChevronLeft className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder
          icon={Icon}
          className="text-primary"
          iconClassName="text-primary"
        />
      ) : (
        <>
          <div className="space-y-2 border-b border-border bg-muted/30 p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('workspace.claudeCode.documents.sidebar.searchPlaceholder')}
                className="h-7 pl-8 text-xs"
              />
            </div>
            {showScopeFilter && (
              <Select value={scope} onValueChange={(value) => setScope(value as typeof scope)}>
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableScopes.includes('all') && (
                    <SelectItem value="all">
                      <div className="flex items-center gap-2">
                        <Layers className="h-3 w-3" />
                        {t('workspace.claudeCode.documents.sidebar.scope.all')}
                      </div>
                    </SelectItem>
                  )}
                  {availableScopes.includes('project') && (
                    <SelectItem value="project">
                      <div className="flex items-center gap-2">
                        <FolderGit className="h-3 w-3" />
                        {t('workspace.claudeCode.documents.scope.values.project')}
                      </div>
                    </SelectItem>
                  )}
                  {availableScopes.includes('user') && (
                    <SelectItem value="user">
                      <div className="flex items-center gap-2">
                        <User className="h-3 w-3" />
                        {t('workspace.claudeCode.documents.scope.values.user')}
                      </div>
                    </SelectItem>
                  )}
                  {availableScopes.includes('local') && (
                    <SelectItem value="local">
                      <div className="flex items-center gap-2">
                        <HardDrive className="h-3 w-3" />
                        {t('workspace.claudeCode.documents.scope.values.local')}
                      </div>
                    </SelectItem>
                  )}
                  {availableScopes.includes('plugin') && (
                    <SelectItem value="plugin">
                      <div className="flex items-center gap-2">
                        <Puzzle className="h-3 w-3" />
                        {t('workspace.claudeCode.documents.scope.values.plugin')}
                      </div>
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto p-2">
            {collection.loading ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.claudeCode.documents.sidebar.loading')}
              </div>
            ) : filteredDocs.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {collection.error ?? t('workspace.claudeCode.documents.sidebar.empty')}
              </div>
            ) : (
              filteredDocs.map((doc) => {
                const isActive = doc.id === activeId;
                return (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => collection.select(doc.id)}
                    className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                      isActive
                        ? 'border-primary/60 bg-primary/10 shadow-sm'
                        : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{doc.title}</div>
                        <div className="truncate text-xs text-muted-foreground">{doc.description}</div>
                      </div>
                      {showScopeBadges && (
                        <Badge variant="outline" className={`text-[10px] whitespace-nowrap flex-shrink-0 px-1 py-0 ${SCOPE_BADGE_CLASSES[doc.scope]}`}>
                          {t(`workspace.claudeCode.documents.scope.values.${doc.scope}`)}
                        </Badge>
                      )}
                    </div>
                    {doc.size && (
                      <div className="mt-1.5 text-[10px] text-muted-foreground">
                        {t('workspace.claudeCode.documents.size.badge', { size: doc.size })}
                      </div>
                    )}
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

export const MarkdownSidebar: React.FC<MarkdownSidebarProps> = (props) => {
  const context = useContext(ClaudeCodeContext);

  if (!context) {
    return <ClaudeCodeLoadingState />;
  }

  return <MarkdownSidebarContent {...props} />;
};

export default MarkdownSidebar;
