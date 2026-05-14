import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useState, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SessionViewerDialog');
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  MessageSquare,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { ChatMessageItem } from '@/features/workspace/components/ChatPanel/ChatMessageItem';
import { agentApi } from '@/features/workspace/components/ChatPanel/agentSessionApi';
import type { AgentMessage, AgentSession } from '@/features/workspace/components/ChatPanel/agentSessionTypes';
import { useI18n } from '@/shared/hooks/useI18n';

interface SessionViewerDialogProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string | null;
  workspaceId: string;
  runtimeBaseUrl: string;
  title?: string;
  description?: string;
}

const MESSAGES_PER_PAGE = 15;

export const SessionViewerDialog: React.FC<SessionViewerDialogProps> = ({
  isOpen,
  onClose,
  sessionId,
  workspaceId,
  runtimeBaseUrl,
  title,
  description,
}) => {
  const { t } = useI18n();
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<AgentSession | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [totalMessages, setTotalMessages] = useState(0);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [loadedOffset, setLoadedOffset] = useState(0);

  const fetchSessionAndMessages = useCallback(async () => {
    if (!sessionId || !runtimeBaseUrl) {
      logger.warn('Missing required params', { sessionId, runtimeBaseUrl });
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Step 1: Get session info and message total count
      const [sessionData, countResult] = await Promise.all([
        agentApi.sessions.getSession(runtimeBaseUrl, sessionId),
        agentApi.messages.listMessages(runtimeBaseUrl, sessionId, { limit: 1, offset: 0 })
      ]);

      setSessionInfo(sessionData);
      const total = countResult.total;
      setTotalMessages(total);

      // Step 2: Calculate offset to load the most recent messages
      const offset = Math.max(0, total - MESSAGES_PER_PAGE);
      const messagesData = await agentApi.messages.listMessages(runtimeBaseUrl, sessionId, {
        limit: MESSAGES_PER_PAGE,
        offset,
      });

      setMessages(messagesData.items);
      setLoadedOffset(offset);
      setHasMoreMessages(offset > 0);

    } catch (err) {
      logger.error('Error fetching session data', { error: err });
      setError(err instanceof Error ? err.message : t('common.messages.unknownError'));
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, runtimeBaseUrl, t]);

  const loadMoreMessages = useCallback(async () => {
    if (!sessionId || !runtimeBaseUrl || isLoadingMore || !hasMoreMessages) {
      return;
    }

    setIsLoadingMore(true);

    try {
      // Load older messages by going to a lower offset
      const olderOffset = Math.max(0, loadedOffset - MESSAGES_PER_PAGE);
      const actualLimit = loadedOffset - olderOffset;

      if (actualLimit <= 0) {
        setHasMoreMessages(false);
        return;
      }

      const data = await agentApi.messages.listMessages(runtimeBaseUrl, sessionId, {
        limit: actualLimit,
        offset: olderOffset,
      });

      if (data.items.length > 0) {
        // Prepend older messages before existing ones
        setMessages(prev => [...data.items, ...prev]);
        setLoadedOffset(olderOffset);
        setHasMoreMessages(olderOffset > 0);
      } else {
        setHasMoreMessages(false);
      }
    } catch (err) {
      logger.error('Error loading more messages', { error: err });
      setError(err instanceof Error ? err.message : t('common.messages.unknownError'));
    } finally {
      setIsLoadingMore(false);
    }
  }, [sessionId, runtimeBaseUrl, isLoadingMore, hasMoreMessages, loadedOffset, t]);

  const handleRefresh = useCallback(() => {
    void fetchSessionAndMessages();
  }, [fetchSessionAndMessages]);

  const scrollAreaRef = React.useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isOpen && sessionId) {
      void fetchSessionAndMessages();
    }
  }, [isOpen, sessionId, fetchSessionAndMessages]);

  if (!sessionId) return null;

  const dialogTitle = title || t('common.sessionViewer.title');
  const dialogDescription = description || t('common.sessionViewer.description');

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0 pb-4 border-b">
          <DialogHeading icon={MessageSquare} className="text-lg font-semibold">
            {dialogTitle}
          </DialogHeading>
          <DialogDescription className="text-sm text-muted-foreground mt-1">
            {sessionInfo?.title || dialogDescription}
          </DialogDescription>

          {sessionInfo && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-xs">
                {sessionInfo.agentic_tool}
              </Badge>
              <Badge variant="outline" className="text-xs">
                {sessionInfo.status}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {new Date(sessionInfo.created_at).toLocaleString()}
              </span>
            </div>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between py-2 px-1">
            <h3 className="text-sm font-semibold text-muted-foreground">
              {t('common.sessionViewer.messagesTitle')}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
              className="h-8 px-3 text-xs"
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
              {t('common.sessionViewer.refresh')}
            </Button>
          </div>

          <ScrollArea ref={scrollAreaRef} className="flex-1 rounded-lg border bg-muted/20">
            {isLoading ? (
              <div className="flex items-center justify-center h-full p-8">
                <div className="text-center">
                  <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">{t('common.sessionViewer.loading')}</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-full p-8">
                <div className="text-center">
                  <AlertCircle className="h-8 w-8 mx-auto mb-2 text-destructive" />
                  <p className="text-sm text-destructive">{error}</p>
                  <Button variant="outline" size="sm" onClick={handleRefresh} className="mt-4">
                    {t('common.sessionViewer.retry')}
                  </Button>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex items-center justify-center h-full p-8">
                <p className="text-sm text-muted-foreground">{t('common.sessionViewer.noMessages')}</p>
              </div>
            ) : (
              <div className="p-4">
                {hasMoreMessages && !isLoadingMore && (
                  <div className="flex justify-center py-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadMoreMessages}
                      className="text-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary"
                    >
                      {totalMessages > 0
                        ? t('workspace.chat.messages.loadMoreWithCount', { count: totalMessages })
                        : t('workspace.chat.messages.loadMore')
                      }
                    </Button>
                  </div>
                )}

                {isLoadingMore && (
                  <div className="flex justify-center py-3">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled
                      className="text-sm border-primary/20 bg-primary/5 text-primary"
                    >
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary mr-2"></div>
                      {t('workspace.chat.messages.loadingMore')}
                    </Button>
                  </div>
                )}

                <div className="flex flex-col w-full min-w-0 gap-1">
                  {messages.map((message) => (
                    <ChatMessageItem
                      key={message.message_id}
                      message={message}
                      allMessages={messages}
                      showTimestamp={true}
                      variant="detailed"
                    />
                  ))}
                </div>
              </div>
            )}
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SessionViewerDialog;
