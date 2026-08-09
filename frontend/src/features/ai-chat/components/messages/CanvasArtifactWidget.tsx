import { useCallback } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { ToolPartProps } from './toolPartTypes';
import { useAiChatIntegration } from '../../contexts/AiChatIntegrationContext';

const stringValue = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() !== '' ? value : null;

export const CanvasArtifactWidget = ({ parameters, status }: ToolPartProps) => {
  const { t } = useI18n();
  const { openCanvas } = useAiChatIntegration();
  const title = stringValue(parameters.title);
  const pending = status === 'pending';
  const openable = status === 'completed' && openCanvas !== null;

  const handleOpen = useCallback(() => {
    openCanvas?.();
  }, [openCanvas]);

  return (
    <button
      type="button"
      data-status={status}
      onClick={handleOpen}
      disabled={!openable}
      className={cn(
        'my-2 inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground transition-colors hover:border-primary/40 hover:bg-muted disabled:cursor-default disabled:hover:border-border disabled:hover:bg-card',
        pending && 'opacity-70',
      )}
    >
      {pending ? (
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
      ) : (
        <ExternalLink className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
      )}
      <span className="truncate">{title ?? t('aiChat.canvasArtifact.defaultTitle')}</span>
      {openable && (
        <span className="text-xs text-muted-foreground">
          · {t('aiChat.canvasArtifact.open')}
        </span>
      )}
    </button>
  );
};
