import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, RotateCcw } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { Thread } from '../model/threadModel';
import { buildThreadErrorNoticeModel } from '../model/threadErrorNoticeModel';

interface ThreadErrorNoticeProps {
  thread: Thread;
  onRetry: () => void;
}

export const ThreadErrorNotice = ({ thread, onRetry }: ThreadErrorNoticeProps) => {
  const { t } = useI18n();
  const [showDetails, setShowDetails] = useState(false);
  const notice = buildThreadErrorNoticeModel(thread);

  if (!notice) {
    return null;
  }

  return (
    <section className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-foreground">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
          <div className="min-w-0 space-y-1">
            <div className="text-xs font-medium text-foreground">
              {t(notice.titleKey, notice.titleParams)}
            </div>
            <div className="text-xs text-muted-foreground">
              {t(notice.descriptionKey)}
            </div>
            {notice.summary && (
              <div className="break-words text-xs text-foreground/90">
                {notice.summary}
              </div>
            )}
          </div>
        </div>
        {notice.retryable && (
          <button
            type="button"
            aria-label={t('aiChat.error.retry')}
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:bg-background/60 hover:text-foreground"
            onClick={onRetry}
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
      {notice.detail && (
        <div className="mt-2">
          <button
            type="button"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowDetails((current) => !current)}
          >
            {showDetails ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            <span>{t(showDetails ? 'aiChat.error.details.hide' : 'aiChat.error.details.show')}</span>
          </button>
          {showDetails && (
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-background/70 p-2 text-xs text-muted-foreground">
              {notice.detail}
            </pre>
          )}
        </div>
      )}
    </section>
  );
};
