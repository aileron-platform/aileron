/**
 * QueuedMessagesPanel - displays prompts waiting for execution.
 */

import React, { useState } from 'react';
import { Copy, Trash2, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import type { QueuedMessage } from './agentSessionTypes';

interface QueuedMessagesPanelProps {
  messages: QueuedMessage[];
  maxQueueSize?: number;
  onDelete: (messageId: string) => void;
  onCopy: (content: string) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const QueuedMessagesPanel: React.FC<QueuedMessagesPanelProps> = ({
  messages,
  maxQueueSize = 5,
  onDelete,
  onCopy,
  t,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-border bg-muted/30 px-3 py-2">
      {/* Header */}
      <div
        className="flex items-center justify-between cursor-pointer mb-1"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Clock className="h-4 w-4" />
          <span>
            {t('workspace.chat.queue.title', { count: messages.length, max: maxQueueSize })}
          </span>
        </div>
        <div className="p-1 hover:bg-muted rounded">
          {isCollapsed ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Messages list */}
      {!isCollapsed && (
        <div className="space-y-1.5">
          {messages.map((msg, index) => (
            <div
              key={msg.message_id}
              className="flex items-center justify-between bg-background rounded-md px-3 py-2 border border-border/50"
            >
              {/* Position and content preview */}
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="text-xs font-mono text-muted-foreground shrink-0">
                  #{index + 1}
                </span>
                <span className="text-sm text-foreground truncate">
                  {msg.content_preview || t('workspace.chat.queue.emptyMessage')}
                </span>
                {msg.status === 'dispatching' && (
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground shrink-0">
                    {t('workspace.chat.queue.dispatching')}
                  </span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0 ml-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCopy(msg.content_preview || '');
                  }}
                  className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition-colors"
                  title={t('workspace.chat.queue.copy')}
                >
                  <Copy className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(msg.message_id);
                  }}
                  disabled={msg.status === 'dispatching'}
                  className="p-1.5 hover:bg-destructive/10 rounded text-muted-foreground hover:text-destructive transition-colors"
                  title={msg.status === 'dispatching'
                    ? t('workspace.chat.queue.processingTitle')
                    : t('workspace.chat.queue.delete')}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default QueuedMessagesPanel;
