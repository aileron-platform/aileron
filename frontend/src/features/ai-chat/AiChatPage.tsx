import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Archive, ArrowDownWideNarrow, Check, ListFilter, MessageSquare, Plus, RotateCcw } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  CollapsedSidebarIcon,
  SidebarCollapseToggle,
  collapsedSidebarActionClass,
  collapsedSidebarIconClass,
} from '@/shared/components/layout/CollapsedSidebarControls';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import {
  getLastThreadId,
  getPreferredThreadSettings,
  getThreadListSortMode,
  setLastThreadId,
  setThreadListSortMode as persistThreadListSortMode,
} from './storage/aiChatStorage';
import { subscribeThreadEvents } from './realtime/threadEvents';
import { sortThreadSummaries, type ThreadListSortMode } from './model/threadListModel';
import { resolveThreadSelection } from './model/threadSelectionModel';
import { useCapabilities } from './hooks/useCapabilities';
import { useThread } from './hooks/useThread';
import { useThreads } from './hooks/useThreads';
import { ThreadListSidebar } from './components/ThreadListSidebar';
import { ChatWorkbench } from './components/ChatWorkbench';
import { ChatThreadFeatureHeader } from './components/ChatThreadFeatureHeader';

interface AiChatPageProps {
  workspaceId: string;
  userId: string;
}

const THREAD_COLUMN_DEFAULT_WIDTH = 320;

export const AiChatPage = ({ workspaceId, userId }: AiChatPageProps) => {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [archived, setArchived] = useState(false);
  const threads = useThreads(workspaceId, { archived });
  const capabilities = useCapabilities(workspaceId);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [threadColumnWidth, setThreadColumnWidth] = useState(THREAD_COLUMN_DEFAULT_WIDTH);
  const [threadColumnCollapsed, setThreadColumnCollapsed] = useState(false);
  const [threadListSortMode, setThreadListSortModeState] = useState<ThreadListSortMode>(() =>
    getThreadListSortMode(userId, workspaceId),
  );
  const dragStateRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const visibleThreads = useMemo(
    () => sortThreadSummaries(threads.query.data ?? [], threadListSortMode, t),
    [threads.query.data, threadListSortMode, t],
  );
  const queryThreadId = searchParams.get('thread');
  const selectedThreadActions = useThread(selectedThreadId, workspaceId);
  const selectedThreadSummary = selectedThreadActions.query.data
    ?? visibleThreads.find((thread) => thread.id === selectedThreadId)
    ?? null;

  useEffect(() => {
    setThreadListSortModeState(getThreadListSortMode(userId, workspaceId));
  }, [userId, workspaceId]);

  const selectFallbackAfterRemoval = useCallback((removedThreadId: string) => {
    const fallbackThreadId = visibleThreads.find((thread) => thread.id !== removedThreadId)?.id ?? null;
    if (fallbackThreadId) {
      setLastThreadId(userId, workspaceId, fallbackThreadId);
    }
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      if (fallbackThreadId) {
        nextParams.set('thread', fallbackThreadId);
      } else {
        nextParams.delete('thread');
      }
      return nextParams;
    }, { replace: true });
    setSelectedThreadId(fallbackThreadId);
  }, [setSearchParams, userId, visibleThreads, workspaceId]);

  useEffect(() => {
    const visibleThreadIds = new Set(visibleThreads.map((thread) => thread.id));
    const resolvedThreadId = resolveThreadSelection({
      threads: visibleThreads,
      getSavedThreadId: () => getLastThreadId(userId, workspaceId),
      queryThreadId,
    });
    setSelectedThreadId((currentThreadId) => {
      if (
        currentThreadId
        && !visibleThreadIds.has(currentThreadId)
        && (!queryThreadId || queryThreadId === currentThreadId)
      ) {
        return currentThreadId;
      }
      if (resolvedThreadId) {
        setLastThreadId(userId, workspaceId, resolvedThreadId);
      }
      return resolvedThreadId;
    });
  }, [queryThreadId, userId, visibleThreads, workspaceId]);

  useEffect(() => subscribeThreadEvents(workspaceId, (event) => {
    if (event.type !== 'deleted') return;
    if (event.threadId === selectedThreadId || event.threadId === queryThreadId) {
      selectFallbackAfterRemoval(event.threadId);
    }
  }), [queryThreadId, selectFallbackAfterRemoval, selectedThreadId, workspaceId]);

  const handleSelect = (threadId: string) => {
    setLastThreadId(userId, workspaceId, threadId);
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      nextParams.set('thread', threadId);
      return nextParams;
    }, { replace: true });
    setSelectedThreadId(threadId);
  };

  const handleNewThread = async () => {
    const workspaceCapabilities = capabilities.data;
    if (!workspaceCapabilities) return;
    setArchived(false);
    const preferred = getPreferredThreadSettings(workspaceCapabilities);
    if (preferred) {
      const thread = await threads.createDraft.mutateAsync(preferred);
      handleSelect(thread.id);
      return;
    }

    const tool = workspaceCapabilities.tools.find((item) => item.id === workspaceCapabilities.defaultTool)
      ?? workspaceCapabilities.tools[0];
    if (!tool) return;

    const thread = await threads.createDraft.mutateAsync({
      agenticTool: tool.id,
      model: tool.defaultModel,
      claudeMode: tool.defaultMode,
    });
    handleSelect(thread.id);
  };

  const handleArchiveThread = (threadId: string) => {
    selectedThreadActions.archive.mutate(threadId, {
      onSuccess: () => {
        if (threadId === selectedThreadId) {
          selectFallbackAfterRemoval(threadId);
        }
      },
    });
  };

  const handleDeleteThread = (threadId: string) => {
    selectedThreadActions.deleteThread.mutate(threadId, {
      onSuccess: () => {
        if (threadId === selectedThreadId || threadId === queryThreadId) {
          selectFallbackAfterRemoval(threadId);
        }
      },
    });
  };

  const handleThreadListSortModeChange = (mode: ThreadListSortMode) => {
    setThreadListSortModeState(mode);
    persistThreadListSortMode(userId, workspaceId, mode);
  };

  const handleResizeStart = (event: React.MouseEvent) => {
    event.preventDefault();
    dragStateRef.current = {
      startX: event.clientX,
      startWidth: threadColumnWidth,
    };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const dragState = dragStateRef.current;
      if (!dragState) return;
      const nextWidth = dragState.startWidth + moveEvent.clientX - dragState.startX;
      setThreadColumnWidth(Math.max(320, Math.min(560, nextWidth)));
    };

    const handleMouseUp = () => {
      dragStateRef.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  return (
    <div className="flex h-full min-h-0 min-w-0 bg-background">
      <aside
        data-testid="ai-chat-home-thread-column"
        className="relative flex h-full min-h-0 shrink-0 flex-col border-r border-border bg-background"
        style={{ width: threadColumnCollapsed ? '64px' : `${threadColumnWidth}px` }}
      >
        <header
          className={cn(
            'flex h-10 shrink-0 items-center gap-2 border-b border-border bg-card px-3',
            threadColumnCollapsed ? 'justify-center' : 'justify-between',
          )}
        >
          {!threadColumnCollapsed && (
            <>
              <div className="flex min-w-0 items-center gap-2">
                <MessageSquare className="h-4 w-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
                <h2 className="truncate text-sm font-medium text-foreground">{t('aiChat.threadList.title')}</h2>
              </div>
              <div className="ml-auto flex items-center gap-1">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={t('aiChat.threadList.filter.label')}
                      className={collapsedSidebarActionClass}
                    >
                      <ListFilter className={collapsedSidebarIconClass} aria-hidden="true" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuItem onClick={() => setArchived(false)}>
                      <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                      <span className="flex-1">{t('aiChat.threadList.filter.active')}</span>
                      {!archived && <Check className="h-4 w-4" aria-hidden="true" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setArchived(true)}>
                      <Archive className="mr-2 h-4 w-4" aria-hidden="true" />
                      <span className="flex-1">{t('aiChat.threadList.filter.archived')}</span>
                      {archived && <Check className="h-4 w-4" aria-hidden="true" />}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={t('aiChat.threadList.sort.label')}
                      className={collapsedSidebarActionClass}
                    >
                      <ArrowDownWideNarrow className={collapsedSidebarIconClass} aria-hidden="true" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuItem onClick={() => handleThreadListSortModeChange('activity')}>
                      <span className="flex-1">{t('aiChat.threadList.sort.activity')}</span>
                      {threadListSortMode === 'activity' && <Check className="h-4 w-4" aria-hidden="true" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleThreadListSortModeChange('created')}>
                      <span className="flex-1">{t('aiChat.threadList.sort.created')}</span>
                      {threadListSortMode === 'created' && <Check className="h-4 w-4" aria-hidden="true" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleThreadListSortModeChange('title')}>
                      <span className="flex-1">{t('aiChat.threadList.sort.title')}</span>
                      {threadListSortMode === 'title' && <Check className="h-4 w-4" aria-hidden="true" />}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <button
                  type="button"
                  aria-label={t('aiChat.threadList.newThread')}
                  className={collapsedSidebarActionClass}
                  onClick={handleNewThread}
                >
                  <Plus className={collapsedSidebarIconClass} aria-hidden="true" />
                </button>
              </div>
            </>
          )}
          <SidebarCollapseToggle
            collapsed={threadColumnCollapsed}
            label={t(threadColumnCollapsed ? 'shared.shell.expandSidebar' : 'shared.shell.collapseSidebar')}
            onClick={() => setThreadColumnCollapsed((collapsed) => !collapsed)}
          />
        </header>
        <div className="min-h-0 flex-1 overflow-hidden">
          {threadColumnCollapsed ? (
            <div className="flex h-full items-start justify-center px-3 py-3">
              <CollapsedSidebarIcon icon={MessageSquare} testId="ai-chat-home-thread-column-collapsed-icon" />
            </div>
          ) : (
            <ThreadListSidebar
              workspaceId={workspaceId}
              userId={userId}
              selectedThreadId={selectedThreadId}
              threads={visibleThreads}
              isLoading={threads.query.isLoading}
              onSelect={handleSelect}
              onArchive={handleArchiveThread}
              onDelete={handleDeleteThread}
            />
          )}
        </div>
        {!threadColumnCollapsed && (
          <div
            data-testid="ai-chat-home-resize-handle"
            className="absolute right-0 top-0 h-full w-1 cursor-col-resize bg-transparent transition-colors hover:bg-primary/20"
            onMouseDown={handleResizeStart}
          />
        )}
      </aside>
      <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
        <ChatThreadFeatureHeader
          thread={selectedThreadSummary}
          onRetry={() => {
            if (selectedThreadId) selectedThreadActions.retry.mutate(selectedThreadId);
          }}
          onArchive={selectedThreadId && selectedThreadSummary && !selectedThreadSummary.archived
            ? () => handleArchiveThread(selectedThreadId)
            : undefined}
        />
        <div className="min-h-0 flex-1 overflow-hidden">
          <ChatWorkbench
            workspaceId={workspaceId}
            userId={userId}
            selectedThreadId={selectedThreadId}
            onThreadSelected={handleSelect}
          />
        </div>
      </section>
    </div>
  );
};
