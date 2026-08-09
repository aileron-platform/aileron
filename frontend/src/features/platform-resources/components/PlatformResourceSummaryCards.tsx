import React from 'react';
import { Activity, Database, HardDrive, TriangleAlert } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { PlatformResourceStatisticsSummary } from '../model/platformResourceTypes';
import { formatPlatformResourceCapacity } from '../model/formatPlatformResourceCapacity';

interface PlatformResourceSummaryCardsProps {
  summary: PlatformResourceStatisticsSummary | null;
  isLoading: boolean;
  hasError: boolean;
  onRetry: () => void;
  onNearLimit?: () => void;
}

export const PlatformResourceSummaryCards: React.FC<PlatformResourceSummaryCardsProps> = ({
  summary,
  isLoading,
  hasError,
  onRetry,
  onNearLimit,
}) => {
  const { t } = useI18n();

  if (hasError) {
    return (
      <section className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
        <p className="text-sm text-destructive">{t('platformResources.statistics.errors.summary')}</p>
        <button type="button" className="mt-2 text-sm text-primary underline" onClick={onRetry}>
          {t('platformResources.statistics.actions.retry')}
        </button>
      </section>
    );
  }

  const cards = [
    { key: 'total', icon: Database, value: summary?.metrics.total.value },
    { key: 'active', icon: Activity, value: summary?.metrics.active.value },
    {
      key: 'usedBytes',
      icon: HardDrive,
      value: summary ? formatPlatformResourceCapacity(summary.metrics.usedBytes.value) : undefined,
    },
    { key: 'nearLimit', icon: TriangleAlert, value: summary?.metrics.nearLimit.value },
  ] as const;

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-busy={isLoading}>
      {cards.map(({ key, icon: Icon, value }) => {
        const metric = summary?.metrics[key];
        const content = (
          <>
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                {t(`platformResources.statistics.cards.${key}`)}
              </p>
              <Icon aria-hidden="true" className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-2 text-2xl font-semibold">{isLoading ? '…' : value ?? '—'}</p>
            {metric?.changePercent != null ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {t('platformResources.statistics.comparison', {
                  value: metric.changePercent,
                })}
              </p>
            ) : null}
          </>
        );
        if (key === 'nearLimit' && onNearLimit) {
          return (
            <button
              key={key}
              type="button"
              className="rounded-lg border border-amber-500/35 bg-amber-500/5 p-4 text-left shadow-sm transition-colors hover:bg-amber-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={onNearLimit}
            >
              {content}
            </button>
          );
        }
        return (
          <div key={key} className="rounded-lg border bg-card p-4 shadow-sm">
            {content}
          </div>
        );
      })}
    </section>
  );
};
