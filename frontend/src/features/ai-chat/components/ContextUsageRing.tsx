import { useI18n } from '@/shared/hooks/useI18n';

interface ContextUsageRingProps {
  contextTokens: number | null;
  contextWindow: number | null;
}

export const ContextUsageRing = ({ contextTokens, contextWindow }: ContextUsageRingProps) => {
  const { t } = useI18n();

  if (contextTokens == null || contextWindow == null || contextWindow <= 0) {
    return null;
  }

  const ratio = Math.min(contextTokens / contextWindow, 1);
  const percent = Math.round(ratio * 100);
  const warning = percent >= 80;
  const circumference = 44;
  const dashOffset = circumference * (1 - ratio);

  return (
    <span
      data-testid="context-usage-ring"
      data-warning={warning ? 'true' : 'false'}
      title={t('aiChat.contextUsage.tooltip', {
        used: contextTokens,
        limit: contextWindow,
        percent,
      })}
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
    >
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeOpacity="0.18" strokeWidth="3" />
        <circle
          cx="10"
          cy="10"
          r="7"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          className={warning ? 'text-amber-500' : 'text-primary'}
          transform="rotate(-90 10 10)"
        />
      </svg>
      <span className={warning ? 'font-medium text-amber-600' : 'font-medium text-foreground'}>{percent}%</span>
    </span>
  );
};
