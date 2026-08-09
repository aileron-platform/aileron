import React from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  PlatformResourceCapacityTrend,
  PlatformResourceTrend,
} from '../model/platformResourceTypes';
import { formatPlatformResourceCapacity } from '../model/formatPlatformResourceCapacity';

interface TrendPanelProps {
  trend: PlatformResourceTrend | null;
  isLoading: boolean;
  hasError: boolean;
  onRetry: () => void;
}

export const PlatformResourceTrendPanel: React.FC<TrendPanelProps> = ({
  trend,
  isLoading,
  hasError,
  onRetry,
}) => {
  const { t } = useI18n();
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">{t('platformResources.statistics.resourceTrend.title')}</h2>
      {hasError ? (
        <ErrorState message={t('platformResources.statistics.errors.resourceTrend')} onRetry={onRetry} />
      ) : (
        <>
          <div className="mt-3 h-64" aria-hidden="true">
            {isLoading ? null : (
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <LineChart data={trend?.points ?? []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line name={t('platformResources.statistics.series.total')} type="monotone" dataKey="total" stroke="hsl(var(--primary))" />
                  <Line name={t('platformResources.statistics.series.created')} type="monotone" dataKey="created" stroke="#0ea5e9" />
                  <Line name={t('platformResources.statistics.series.active')} type="monotone" dataKey="active" stroke="#10b981" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
          <table
            className="sr-only"
            aria-label={t('platformResources.statistics.resourceTrend.accessibleTableLabel')}
          >
            <thead><tr><th>{t('platformResources.statistics.date')}</th><th>{t('platformResources.statistics.series.total')}</th><th>{t('platformResources.statistics.series.created')}</th><th>{t('platformResources.statistics.series.active')}</th><th>{t('platformResources.statistics.series.deleted')}</th></tr></thead>
            <tbody>
              {(trend?.points ?? []).map(point => (
                <tr key={point.date}><td>{point.date}</td><td>{point.total}</td><td>{point.created}</td><td>{point.active}</td><td>{point.deleted}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
};

interface CapacityTrendPanelProps {
  trend: PlatformResourceCapacityTrend | null;
  isLoading: boolean;
  hasError: boolean;
  onRetry: () => void;
}

export const PlatformResourceCapacityTrendPanel: React.FC<CapacityTrendPanelProps> = ({
  trend,
  isLoading,
  hasError,
  onRetry,
}) => {
  const { t } = useI18n();
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">{t('platformResources.statistics.capacityTrend.title')}</h2>
      {hasError ? (
        <ErrorState message={t('platformResources.statistics.errors.capacityTrend')} onRetry={onRetry} />
      ) : (
        <>
          <div className="mt-3 h-64" aria-hidden="true">
            {isLoading ? null : (
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <LineChart data={trend?.points ?? []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis tickFormatter={value => formatPlatformResourceCapacity(Number(value))} />
                  <Tooltip formatter={value => formatPlatformResourceCapacity(Number(value))} />
                  <Legend />
                  <Line name={t('platformResources.statistics.series.used')} type="monotone" dataKey="usedBytes" stroke="hsl(var(--primary))" />
                  <Line name={t('platformResources.statistics.series.allocated')} type="monotone" dataKey="allocatedBytes" stroke="#f59e0b" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
          <table
            className="sr-only"
            aria-label={t('platformResources.statistics.capacityTrend.accessibleTableLabel')}
          >
            <thead><tr><th>{t('platformResources.statistics.date')}</th><th>{t('platformResources.statistics.series.used')}</th><th>{t('platformResources.statistics.series.allocated')}</th><th>{t('platformResources.statistics.series.unknown')}</th><th>{t('platformResources.statistics.series.stale')}</th></tr></thead>
            <tbody>
              {(trend?.points ?? []).map(point => (
                <tr key={point.date}><td>{point.date}</td><td>{point.usedBytes}</td><td>{point.allocatedBytes ?? ''}</td><td>{point.unknownCount}</td><td>{point.staleCount}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
};

const ErrorState: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => {
  const { t } = useI18n();
  return (
    <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/5 p-3">
      <p className="text-sm text-destructive">{message}</p>
      <button type="button" className="mt-2 text-sm text-primary underline" onClick={onRetry}>
        {t('platformResources.statistics.actions.retry')}
      </button>
    </div>
  );
};
