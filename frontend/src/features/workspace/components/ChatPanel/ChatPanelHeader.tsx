import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsDown,
  Copy,
  Loader2,
  Maximize2,
  MessageSquare,
  Minimize2,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Check,
  Trash2,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ChatPanelHeader');
import { Badge } from '@/shared/components/ui/badge';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/shared/components/ui/command';
import { cn } from '@/shared/utils/cn';
import type { ChatSessionOption } from './types';
import { resolveSessionDisplayLabel } from './sessionDisplayLabel';

export interface ChatPanelHeaderProps {
  isCollapsed: boolean;
  isExpanded: boolean;
  sessionId: string | null;
  isConnected: boolean;
  sessions: ChatSessionOption[];
  selectedSessionId: string | null;
  isLoadingSessions: boolean;
  hasActiveConversation: boolean;
  hasPendingNewConversation: boolean;
  isSelectedSessionDeleteBlocked?: boolean;
  onToggleCollapse: () => void;
  onToggleFullscreen: () => void;
  onNewSession: () => void;
  onRefresh: () => void;
  onClear: () => void;
  onExport: () => void;
  onSessionSelect: (sessionId: string) => void;
  onSessionDelete?: (sessionId: string) => void | Promise<void>;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const ConnectionBadge: React.FC<{ isConnected: boolean; t: ChatPanelHeaderProps['t'] }> = ({
  isConnected,
  t,
}) => (
  <div
    className={cn(
      'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
      isConnected
        ? 'bg-primary/10 dark:bg-primary/15 text-primary dark:text-primary-foreground'
        : 'bg-amber-100 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300'
    )}
  >
    <span className={cn('h-1.5 w-1.5 rounded-full', isConnected ? 'bg-primary' : 'bg-amber-600 dark:bg-amber-400')} />
    {isConnected
      ? t('workspace.chat.header.connection.connected')
      : t('workspace.chat.header.connection.disconnected')}
  </div>
);

const RECENT_SESSION_LIMIT = 5;
const OLDER_SESSION_PAGE_SIZE = 10;

interface SessionSwitcherProps {
  sessions: ChatSessionOption[];
  selectedSessionId: string | null;
  hasPendingNewConversation: boolean;
  isLoadingSessions: boolean;
  isSelectedSessionDeleteBlocked: boolean;
  onSessionSelect: (sessionId: string) => void;
  onSessionDelete?: (sessionId: string) => void | Promise<void>;
  t: ChatPanelHeaderProps['t'];
}

const SessionSwitcher: React.FC<SessionSwitcherProps> = ({
  sessions,
  selectedSessionId,
  hasPendingNewConversation,
  isLoadingSessions,
  isSelectedSessionDeleteBlocked,
  onSessionSelect,
  onSessionDelete,
  t,
}) => {
  const [open, setOpen] = useState(false);
  const [olderSessionLimit, setOlderSessionLimit] = useState(OLDER_SESSION_PAGE_SIZE);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.session_id === (selectedSessionId ?? undefined)),
    [selectedSessionId, sessions]
  );

  const sessionsKey = useMemo(() => sessions.map((session) => session.session_id).join('|'), [sessions]);

  useEffect(() => {
    setOlderSessionLimit(OLDER_SESSION_PAGE_SIZE);
  }, [sessionsKey]);

  const recentSessions = useMemo(
    () => sessions.slice(0, RECENT_SESSION_LIMIT),
    [sessions]
  );
  const olderSessions = useMemo(
    () => sessions.slice(RECENT_SESSION_LIMIT),
    [sessions]
  );
  const visibleOlderSessions = useMemo(
    () => olderSessions.slice(0, olderSessionLimit),
    [olderSessions, olderSessionLimit]
  );
  const hasMoreOlderSessions = visibleOlderSessions.length < olderSessions.length;

  const placeholder = t('workspace.chat.header.sessions.placeholder');
  const defaultSessionLabel = t('workspace.chat.header.sessionDefault');
  const getSessionLabel = (session: ChatSessionOption) =>
    resolveSessionDisplayLabel(session, defaultSessionLabel);
  const triggerLabel = hasPendingNewConversation
    ? t('workspace.chat.header.sessions.newConversation')
    : selectedSession
      ? getSessionLabel(selectedSession)
      : placeholder;

  const messageCountLabel = (count: number) =>
    t('workspace.chat.header.sessions.messageCount', { count });

  const handleSelect = (sessionId: string) => {
    onSessionSelect(sessionId);
    setOpen(false);
  };

  const handleLoadMoreOlderSessions = () => {
    setOlderSessionLimit((limit) => Math.min(limit + OLDER_SESSION_PAGE_SIZE, olderSessions.length));
  };

  const isDeleteBlocked = (sessionId: string) =>
    !onSessionDelete ||
    (selectedSessionId === sessionId && isSelectedSessionDeleteBlocked);

  const handleDelete = async (sessionId: string) => {
    if (!onSessionDelete || isDeleteBlocked(sessionId) || deletingSessionId === sessionId) return;

    setDeletingSessionId(sessionId);
    try {
      await onSessionDelete(sessionId);
    } finally {
      setDeletingSessionId((current) => (current === sessionId ? null : current));
    }
  };

  const renderSessionItem = (session: ChatSessionOption) => {
    const label = getSessionLabel(session);
    const isSelected = selectedSessionId === session.session_id;
    const isDeleting = deletingSessionId === session.session_id;
    const showDeleteAction = !isDeleteBlocked(session.session_id);

    return (
      <CommandItem
        key={session.session_id}
        value={`${session.session_id} ${label}`}
        onSelect={() => handleSelect(session.session_id)}
      >
        <MessageSquare className="h-3 w-3 text-muted-foreground" />
        <span className="flex-1 truncate text-xs" title={label}>
          {label}
        </span>
        {typeof session.messageCount === 'number' && (
          <Badge variant="outline" className="ml-2 text-[10px] px-1 py-0">
            {messageCountLabel(session.messageCount)}
          </Badge>
        )}
        {showDeleteAction && (
          <Button
            variant="ghost"
            size="icon"
            className="ml-1 h-6 w-6 text-muted-foreground hover:text-destructive"
            title={t('workspace.chat.header.sessions.deleteAction')}
            aria-label={t('workspace.chat.header.sessions.deleteAction')}
            disabled={isDeleting}
            onMouseDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              void handleDelete(session.session_id);
            }}
          >
            {isDeleting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
          </Button>
        )}
        {isSelected && (
          <Check className="h-3 w-3 text-primary" />
        )}
      </CommandItem>
    );
  };

  return (
    <div className="flex-1 min-w-0">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="h-8 w-full justify-between px-2"
            disabled={isLoadingSessions && sessions.length === 0}
          >
            <span className="flex min-w-0 items-center gap-1.5 truncate text-xs">
              <MessageSquare className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
              <span className="truncate">{triggerLabel}</span>
            </span>
            <span className="flex items-center gap-1.5 flex-shrink-0">
              {typeof selectedSession?.messageCount === 'number' && (
                <Badge variant="outline" className="text-[10px] hidden sm:inline-flex px-1 py-0">
                  {messageCountLabel(selectedSession.messageCount)}
                </Badge>
              )}
              {hasPendingNewConversation ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              ) : (
                <ChevronDown
                  className={cn(
                    'h-3.5 w-3.5 text-muted-foreground transition-transform duration-150',
                    open && 'rotate-180'
                  )}
                />
              )}
            </span>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-0" align="start">
          <Command>
            <div className="border-b border-border/60 px-2 py-1.5">
              <CommandInput
                placeholder={t('workspace.chat.header.sessions.searchPlaceholder', {
                  defaultValue: '搜尋對話...',
                })}
                className="h-8 text-xs"
              />
            </div>
            <CommandList>
              <CommandEmpty>
                {t('workspace.chat.header.sessions.emptySearch', {
                  defaultValue: '沒有符合條件的對話。',
                })}
              </CommandEmpty>

              {hasPendingNewConversation && (
                <CommandGroup
                  heading={t('workspace.chat.header.sessions.pendingSection', {
                    defaultValue: '正在建立',
                  })}
                >
                  <CommandItem value="__pending__" disabled>
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    <span className="truncate text-xs">
                      {t('workspace.chat.header.sessions.newConversation')}
                    </span>
                  </CommandItem>
                </CommandGroup>
              )}

              {recentSessions.length > 0 && (
                <CommandGroup
                  heading={t('workspace.chat.header.sessions.recentSection', {
                    defaultValue: '最近對話',
                  })}
                >
                  {recentSessions.map(renderSessionItem)}
                </CommandGroup>
              )}

              {recentSessions.length > 0 && olderSessions.length > 0 && <CommandSeparator />}

              {olderSessions.length > 0 && (
                <CommandGroup
                  heading={t('workspace.chat.header.sessions.allSection', {
                    defaultValue: '更多對話',
                  })}
                >
                  {visibleOlderSessions.map(renderSessionItem)}
                  {hasMoreOlderSessions && (
                    <CommandItem
                      value="__load_more_sessions__"
                      onSelect={handleLoadMoreOlderSessions}
                    >
                      <ChevronsDown className="h-3 w-3 text-muted-foreground" />
                      <span className="flex-1 truncate text-xs">
                        {t('workspace.chat.header.sessions.loadMore', {
                          defaultValue: '載入更多對話',
                        })}
                      </span>
                      <Badge variant="outline" className="ml-2 text-[10px] px-1 py-0">
                        {t('workspace.chat.header.sessions.loadedCount', {
                          count: visibleOlderSessions.length,
                          defaultValue: '已載入 {{count}} 則',
                        })}
                      </Badge>
                    </CommandItem>
                  )}
                </CommandGroup>
              )}

              {sessions.length === 0 && !isLoadingSessions && !hasPendingNewConversation && (
                <div className="px-3 py-3 text-xs text-muted-foreground">
                  {t('workspace.chat.header.sessions.empty')}
                </div>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
};

const CopySessionIdMenu: React.FC<{ sessionId: string | null; t: ChatPanelHeaderProps['t'] }> = ({
  sessionId,
  t,
}) => {
  const { toast } = useToast();

  const handleCopy = async () => {
    if (!sessionId) return;
    try {
      await navigator.clipboard.writeText(sessionId);
      toast({
        title: t('workspace.chat.header.sessionId.copied', { defaultValue: '已複製' }),
        description: sessionId,
      });
    } catch (error) {
      logger.error('Failed to copy session ID', { error });
      toast({
        variant: 'destructive',
        title: t('workspace.chat.header.sessionId.copyFailed', { defaultValue: '複製失敗' }),
      });
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          title={t('workspace.chat.header.actions.menu')}
          className="h-8 w-8"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-48"
        collisionPadding={{ right: 16, left: 16 }}
      >
        <DropdownMenuItem
          disabled={!sessionId}
          onSelect={(event) => {
            event.preventDefault();
            handleCopy();
          }}
        >
          <Copy className="mr-2 h-3.5 w-3.5" />
          <span className="text-xs">
            {t('workspace.chat.header.actions.copySessionId', { defaultValue: '複製 Session ID' })}
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const ChatPanelHeader: React.FC<ChatPanelHeaderProps> = ({
  isCollapsed,
  isExpanded,
  sessionId,
  isConnected,
  sessions,
  selectedSessionId,
  isLoadingSessions,
  hasActiveConversation,
  hasPendingNewConversation,
  isSelectedSessionDeleteBlocked = false,
  onToggleCollapse,
  onToggleFullscreen,
  onNewSession,
  onRefresh,
  onSessionSelect,
  onSessionDelete,
  t,
}) => {
  if (isCollapsed) {
    return (
      <header className="flex h-10 items-center justify-center border-b border-border bg-card">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onToggleCollapse}
          title={t('workspace.chat.header.actions.expand')}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>
      </header>
    );
  }

  return (
    <header className="flex flex-col border-b border-border bg-card">
      <div className="flex h-10 items-center justify-between px-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              <span className="truncate whitespace-nowrap text-sm font-medium text-foreground">
                {t('workspace.chat.header.title')}
              </span>
              <ConnectionBadge isConnected={isConnected} t={t} />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={onToggleFullscreen}
            title={
              isExpanded
                ? t('workspace.chat.header.actions.exitFullscreen')
                : t('workspace.chat.header.actions.fullscreen')
            }
          >
            {isExpanded ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </Button>

          {!isExpanded && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onToggleCollapse}
              title={t('workspace.chat.header.actions.collapse')}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="border-t border-border/70 bg-card px-3 py-1.5">
        <div className="flex items-center gap-2">
          <SessionSwitcher
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            hasPendingNewConversation={hasPendingNewConversation}
            isLoadingSessions={isLoadingSessions}
            isSelectedSessionDeleteBlocked={isSelectedSessionDeleteBlocked}
            onSessionSelect={onSessionSelect}
            onSessionDelete={onSessionDelete}
            t={t}
          />

          <div className="flex flex-shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={onRefresh}
              title={t('workspace.chat.header.actions.refresh')}
              className="h-8 w-8"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={onNewSession}
              title={t('workspace.chat.header.actions.new')}
              disabled={hasPendingNewConversation || isLoadingSessions}
              className="h-8 w-8"
            >
              {hasPendingNewConversation ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
            </Button>

            <CopySessionIdMenu sessionId={sessionId} t={t} />
          </div>
        </div>
      </div>
    </header>
  );
};

export default ChatPanelHeader;
