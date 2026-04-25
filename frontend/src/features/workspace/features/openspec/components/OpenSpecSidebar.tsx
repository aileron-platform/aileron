import React, { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  CheckSquare,
  ChevronDown,
  ChevronLeft,
  CircleDot,
  FileCode2,
  FileText,
  FolderGit2,
  RefreshCw,
  Search,
  Sparkles,
} from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useChatPanelStateContext } from '../../../components/ChatPanel/chatPanelStateContext';
import { useOpenSpecWorkspace } from '../OpenSpecWorkspaceContext';

const normalize = (value: string) => value.trim().toLowerCase();

const truncateCommandCanvas = (value: string, maxLength = 32) => {
  const normalized = value.trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 3)}...`;
};

export const OpenSpecSidebar: React.FC = () => {
  const {
    state,
    layout,
    toggleSecondColumn,
    openFileInTab,
    dispatch,
  } = useWorkspace();
  const { t } = useI18n();
  const [, chatUiActions] = useChatPanelStateContext();
  const {
    state: openSpecState,
    actions,
    changes,
    recommendedActions,
    focusChangeName,
    isLoading: isRefreshing,
    refresh,
  } = useOpenSpecWorkspace();
  const [expandedChangeIds, setExpandedChangeIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const isCollapsed = layout.secondColumnCollapsed;
  const currentStatus = state.openspec.subView;
  const currentStatusLabel = useMemo(() => {
    if (currentStatus === 'complete') {
      return t('workspace.navigation.sub.openspec.complete');
    }
    if (currentStatus === 'archived') {
      return t('workspace.navigation.sub.openspec.archived');
    }
    return t('workspace.navigation.sub.openspec.inProgress');
  }, [currentStatus, t]);
  const currentStatusTagClassName = useMemo(() => {
    if (currentStatus === 'complete') {
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    }
    if (currentStatus === 'archived') {
      return 'border-slate-200 bg-slate-100 text-slate-700';
    }
    return 'border-sky-200 bg-sky-50 text-sky-700';
  }, [currentStatus]);

  const sidebarRecommendedAction = useMemo(() => {
    if (currentStatus === 'archived') {
      return null;
    }
    return recommendedActions[0] ?? null;
  }, [currentStatus, recommendedActions]);

  const canOpenComposerActions = useMemo(
    () => currentStatus !== 'archived' && actions.some((action) => action.availability === 'enabled'),
    [actions, currentStatus],
  );
  const recommendedCommandCanvas = useMemo(
    () => (sidebarRecommendedAction
      ? truncateCommandCanvas(sidebarRecommendedAction.draftTemplate)
      : null),
    [sidebarRecommendedAction],
  );

  const hasOpenSpec = Boolean(openSpecState?.initialized);

  const filteredChanges = useMemo(() => {
    const keyword = normalize(query);
    if (!keyword) {
      return changes;
    }

    return changes.filter((change) => {
      if (normalize(change.name).includes(keyword)) {
        return true;
      }

      return (
        change.specs.some((spec) => normalize(spec.capabilityName).includes(keyword)) ||
        ['proposal', 'design', 'tasks'].some((label) => label.includes(keyword))
      );
    });
  }, [changes, query]);

  const statusFilteredChanges = useMemo(() => {
    return filteredChanges.filter((change) => change.status === currentStatus);
  }, [currentStatus, filteredChanges]);

  const currentOpenSpecPath = useMemo(() => {
    return (
      state.openspec.openTabs.find((tab) => tab.id === state.openspec.activeTabId)?.path ??
      state.openspec.activeTabId ??
      null
    );
  }, [state.openspec.activeTabId, state.openspec.openTabs]);

  useEffect(() => {
    setExpandedChangeIds((prev) => {
      const availableIds = new Set(
        statusFilteredChanges.map((change) => `${change.archived ? 'archive' : 'active'}:${change.name}`),
      );
      const next = prev.filter((id) => availableIds.has(id));
      if (next.length > 0) {
        return next;
      }
      return statusFilteredChanges
        .slice(0, 3)
        .map((change) => `${change.archived ? 'archive' : 'active'}:${change.name}`);
    });
  }, [statusFilteredChanges]);

  useEffect(() => {
    if (!hasOpenSpec) {
      return;
    }

    const hasOpenSpecTab = state.openspec.openTabs.some((tab) => tab.path.startsWith('/openspec/'));
    const firstDocumentPath =
      statusFilteredChanges.flatMap((change) => [
        change.proposalPath,
        change.designPath,
        change.tasksPath,
        ...change.specs.map((spec) => spec.path),
      ]).find(Boolean) ?? null;

    if (!hasOpenSpecTab && firstDocumentPath) {
      openFileInTab(firstDocumentPath, undefined, 'openspec');
    }
  }, [hasOpenSpec, openFileInTab, state.openspec.openTabs, statusFilteredChanges]);

  useEffect(() => {
    dispatch({ type: 'SET_OPENSPEC_SELECTED_PATH', payload: currentOpenSpecPath });
  }, [currentOpenSpecPath, dispatch]);

  const toggleChange = (changeId: string) => {
    setExpandedChangeIds((prev) =>
      prev.includes(changeId)
        ? prev.filter((id) => id !== changeId)
        : [...prev, changeId],
    );
  };

  const handleOpenComposerActions = () => {
    if (!canOpenComposerActions) {
      return;
    }
    if (state.rightChatCollapsed) {
      dispatch({ type: 'SET_RIGHT_CHAT_COLLAPSED', payload: false });
    }
    chatUiActions.openOpenSpecDialog();
  };

  const renderDocumentButton = (
    icon: React.ReactNode,
    label: string,
    path?: string,
    extra?: React.ReactNode,
  ) => {
    if (!path) {
      return null;
    }

    const isActive = currentOpenSpecPath === path;
    return (
      <button
        key={path}
        type="button"
        onClick={() => openFileInTab(path, undefined, 'openspec')}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
          isActive
            ? 'bg-primary/10 text-primary'
            : 'text-foreground hover:bg-muted/50',
        )}
      >
        {icon}
        <span className="flex-1 truncate">{label}</span>
        {extra}
      </button>
    );
  };

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <div
        className={`flex items-center h-10 border-b border-border bg-card px-3 ${
          isCollapsed ? 'justify-center' : 'justify-between'
        }`}
      >
        {!isCollapsed ? (
          <div className="flex items-center justify-between gap-2 flex-1 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <BookOpen className="h-3.5 w-3.5 text-primary" />
              <span className="text-sm font-medium">{t('workspace.openspec.sidebar.title')}</span>
              <Badge
                variant="outline"
                className={cn('h-5 border px-2 text-[11px] font-medium', currentStatusTagClassName)}
              >
                {currentStatusLabel}
              </Badge>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={() => void refresh({ reloadActiveDocument: true })}
              disabled={isRefreshing}
              title={isRefreshing ? t('workspace.openspec.sidebar.refreshing') : t('workspace.openspec.sidebar.refresh')}
              aria-label={isRefreshing ? t('workspace.openspec.sidebar.refreshing') : t('workspace.openspec.sidebar.refresh')}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin')} />
            </Button>
          </div>
        ) : null}
        <button
          onClick={toggleSecondColumn}
          className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
          aria-label={isCollapsed
            ? t('workspace.openspec.sidebar.expand')
            : t('workspace.openspec.sidebar.collapse')}
        >
          <ChevronLeft className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder
          icon={BookOpen}
          className="text-primary"
          iconClassName="text-primary"
        />
      ) : (
        <>
          <div className="space-y-2 border-b border-border bg-muted/30 p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('workspace.openspec.sidebar.searchPlaceholder')}
                className="h-7 pl-8 text-xs"
              />
            </div>

            <div className="rounded-lg border border-border/70 bg-card/80 px-2.5 py-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  <Badge variant={openSpecState?.initialized ? 'secondary' : 'outline'} className="h-5">
                    <Sparkles className="mr-1 h-3 w-3" />
                    {openSpecState?.initialized
                      ? t('workspace.openspec.sidebar.initialized')
                      : t('workspace.openspec.sidebar.notInitialized')}
                  </Badge>
                  {openSpecState ? (
                    <Badge variant="outline" className="h-5">
                      {t(`workspace.chat.dialogs.openspec.profile.${openSpecState.profile}`)}
                    </Badge>
                  ) : null}
                  {typeof openSpecState?.activeChanges.length === 'number' ? (
                    <Badge variant="outline" className="h-5">
                      {t('workspace.openspec.sidebar.activeChangesCompact', {
                        count: openSpecState.activeChanges.length,
                      })}
                    </Badge>
                  ) : null}
                </div>
                {canOpenComposerActions ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 shrink-0 px-2 text-xs"
                    onClick={handleOpenComposerActions}
                  >
                    {sidebarRecommendedAction
                      ? t('workspace.openspec.sidebar.continueWithAction', {
                          action: sidebarRecommendedAction.title,
                        })
                      : t('workspace.openspec.sidebar.openComposerActions')}
                  </Button>
                ) : null}
              </div>

              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <CircleDot className="h-3 w-3 shrink-0" />
                <span className="uppercase tracking-wide">
                  {t('workspace.openspec.sidebar.currentFocusTitle')}
                </span>
                <span className="truncate text-foreground">
                  {focusChangeName
                    ? t('workspace.openspec.sidebar.currentFocusCompact', { change: focusChangeName })
                    : t('workspace.openspec.sidebar.currentFocusEmpty')}
                </span>
              </div>

              {sidebarRecommendedAction ? (
                <div className="mt-1.5 space-y-1.5 text-[11px] text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span className="uppercase tracking-wide">
                      {t('workspace.openspec.sidebar.recommendedTitle')}
                    </span>
                    <span className="truncate text-foreground">
                      {sidebarRecommendedAction.title}
                    </span>
                    <span
                      className="max-w-[140px] shrink truncate font-mono text-[10px]"
                      title={sidebarRecommendedAction.draftTemplate.trim()}
                    >
                      {recommendedCommandCanvas}
                    </span>
                  </div>
                  {sidebarRecommendedAction.recommendedReason ? (
                    <div className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {t('workspace.openspec.sidebar.recommendedReasonLabel')}:
                      </span>{' '}
                      {sidebarRecommendedAction.recommendedReason}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {!canOpenComposerActions ? (
                <div className="mt-1.5 text-[11px] text-muted-foreground">
                  {t('workspace.openspec.sidebar.archivedReadOnly')}
                </div>
              ) : null}

              {openSpecState?.projectSynced === false ? (
                <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                  {t('workspace.openspec.sidebar.syncRequired')}
                </div>
              ) : null}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {isRefreshing ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.openspec.sidebar.loading')}
              </div>
            ) : !hasOpenSpec ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.openspec.empty.description')}
              </div>
            ) : filteredChanges.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.openspec.sidebar.noResults')}
              </div>
            ) : statusFilteredChanges.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {t('workspace.openspec.sidebar.emptyState')}：{currentStatusLabel}
              </div>
            ) : (
              <div className="space-y-1.5">
                {statusFilteredChanges.map((change) => {
                  const changeId = `${change.archived ? 'archive' : 'active'}:${change.name}`;
                  const isExpanded = expandedChangeIds.includes(changeId);
                  return (
                    <div key={changeId} className="rounded-lg border border-border/70 bg-card/40">
                      <button
                        type="button"
                        onClick={() => toggleChange(changeId)}
                        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
                      >
                        <ChevronDown
                          className={cn(
                            'h-4 w-4 text-muted-foreground transition-transform',
                            isExpanded ? 'rotate-0' : '-rotate-90',
                          )}
                        />
                        <FolderGit2 className="h-4 w-4 text-primary" />
                        <span className="flex-1 truncate text-sm font-medium">{change.name}</span>
                      </button>

                      {isExpanded ? (
                        <div className="space-y-1 border-t border-border/70 px-2 py-2">
                          {renderDocumentButton(
                            <FileText className="h-3.5 w-3.5 text-muted-foreground" />,
                            t('workspace.openspec.documents.proposal'),
                            change.proposalPath,
                          )}
                          {renderDocumentButton(
                            <FileText className="h-3.5 w-3.5 text-muted-foreground" />,
                            t('workspace.openspec.documents.design'),
                            change.designPath,
                          )}
                          {renderDocumentButton(
                            <CheckSquare className="h-3.5 w-3.5 text-muted-foreground" />,
                            t('workspace.openspec.documents.tasks'),
                            change.tasksPath,
                          )}
                          {change.specs.length > 0 ? (
                            <div className="space-y-1 rounded-md bg-muted/30 p-1">
                              <div className="px-1 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                                {t('workspace.openspec.documents.specs')}
                              </div>
                              {change.specs.map((spec) =>
                                renderDocumentButton(
                                  <FileCode2 className="h-3.5 w-3.5 text-muted-foreground" />,
                                  spec.capabilityName,
                                  spec.path,
                                ),
                              )}
                            </div>
                          ) : null}
                          {change.totalTasks > 0 ? (
                            <div className="px-2 py-1 text-[11px] text-muted-foreground">
                              {t('workspace.openspec.tasks.summary', {
                                done: change.completedTasks,
                                total: change.totalTasks,
                              })}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default OpenSpecSidebar;
