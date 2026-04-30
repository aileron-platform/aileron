/**
 * ThinkingWidget - AI thinking process with Markdown rendering.
 */
import React from 'react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useI18n } from '@/shared/hooks/useI18n';
import { WidgetProps } from './types';

export const ThinkingWidget: React.FC<WidgetProps> = ({ input }) => {
  const { t } = useI18n();
  const thinking = input?.thinking || '';
  const trimmedThinking = thinking.trim();

  if (!trimmedThinking) {
    return (
      <div className="p-3 text-xs text-gray-500 dark:text-zinc-400 italic">
        {t('workspace.chat.widgets.agentTools.emptyThinking')}
      </div>
    );
  }

  return (
    <div className="bg-muted/30 dark:bg-zinc-800/30 p-4">
      <div className="text-xs text-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
        <MarkdownContent content={trimmedThinking} variant="compact" />
      </div>
    </div>
  );
};

export default ThinkingWidget;
