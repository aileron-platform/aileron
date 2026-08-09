import { Bot, RotateCcw } from 'lucide-react';
import {
  collapsedSidebarActionClass,
  collapsedSidebarIconClass,
} from '@/shared/components/layout/CollapsedSidebarControls';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { resolveThreadTitle } from '../model/threadTitleModel';
import type { ThreadSummary } from '../model/threadModel';
import { canRetry } from '../model/threadStatusModel';
import { ContextUsageRing } from './ContextUsageRing';
import { ThreadActionMenu } from './ThreadActionMenu';

interface ChatThreadFeatureHeaderProps {
  thread: ThreadSummary | null;
  onRetry: () => void;
  onArchive?: () => void;
}

export const ChatThreadFeatureHeader = ({ thread, onRetry, onArchive }: ChatThreadFeatureHeaderProps) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const title = thread ? resolveThreadTitle(thread.title, t) : null;

  const handleCopyThreadId = (threadId: string) => {
    void navigator.clipboard?.writeText(threadId).then(() => {
      toast({
        title: t('aiChat.threadActions.copyThreadIdSuccess.title'),
        description: t('aiChat.threadActions.copyThreadIdSuccess.description'),
        variant: 'success',
      });
    });
  };

  if (!thread) {
    return (
      <header
        data-testid="ai-chat-thread-feature-header"
        className="flex h-10 shrink-0 items-center gap-2 border-b border-border bg-card px-3"
      >
        <Bot data-testid="ai-chat-thread-feature-header-icon" className="h-4 w-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
        <h2 className="truncate text-sm font-medium text-foreground">{t('aiChat.workbench.header')}</h2>
      </header>
    );
  }

  return (
    <header
      data-testid="ai-chat-thread-feature-header"
      className="flex h-10 min-w-0 shrink-0 items-center justify-between gap-3 border-b border-border bg-card px-3"
    >
      <div className="flex min-w-0 items-center gap-2">
        <Bot data-testid="ai-chat-thread-feature-header-icon" className="h-4 w-4 shrink-0 text-sidebar-primary" aria-hidden="true" />
        <h2 className="min-w-0 truncate text-sm font-medium text-foreground">{title}</h2>
        <span className="shrink-0 text-xs text-muted-foreground">{thread.agenticTool}</span>
        <span className="min-w-0 truncate text-xs text-muted-foreground">{thread.model}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ContextUsageRing contextTokens={thread.contextTokens} contextWindow={thread.contextWindow} />
        {canRetry(thread.status) && (
          <button
            type="button"
            aria-label={t('aiChat.workbench.retry')}
            className={collapsedSidebarActionClass}
            onClick={onRetry}
          >
            <RotateCcw className={collapsedSidebarIconClass} aria-hidden="true" />
          </button>
        )}
        <ThreadActionMenu
          thread={thread}
          onArchive={onArchive ? () => onArchive() : undefined}
          onCopyThreadId={handleCopyThreadId}
          includeCopyThreadId
          includeDisplaySettings
          triggerClassName={collapsedSidebarActionClass}
        />
      </div>
    </header>
  );
};
