import React from 'react';
import { Loader2 } from 'lucide-react';
import { useTypewriterEffect } from './hooks/useTypewriterEffect';

export interface TypingIndicatorProps {
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({ t }) => {
  // 使用打字機效果，會自動循環顯示不同的動詞
  const { displayedText, isTyping } = useTypewriterEffect({
    duration: 1000,
    loop: true,
  });

  return (
    <div className="px-3 pb-4">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-muted/50 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-background text-muted-foreground shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {displayedText}...
            {/* 添加閃爍的游標效果 */}
            {isTyping && (
              <span className="inline-block w-0.5 h-3 bg-muted-foreground ml-0.5 animate-pulse" />
            )}
          </span>
          <span className="text-xs text-muted-foreground/80">
            {t('workspace.chat.typing.subtitle')}
          </span>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;
