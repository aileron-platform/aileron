import React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { PlatformResourceStatisticsSummary } from '../model/platformResourceTypes';

interface PlatformResourceDistributionProps {
  summary: PlatformResourceStatisticsSummary | null;
}

export const PlatformResourceDistribution: React.FC<PlatformResourceDistributionProps> = ({
  summary,
}) => {
  const { t } = useI18n();
  if (!summary || summary.distributions.length === 0) return null;

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">{t('platformResources.statistics.distributions.title')}</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {summary.distributions.map(item => (
          <div key={item.key} className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2">
            <span className="text-sm">
              {t(`platformResources.statistics.distributions.${item.key}`)}
            </span>
            <span className="font-semibold tabular-nums">{item.count}</span>
          </div>
        ))}
      </div>
    </section>
  );
};
