import React from 'react';
import { HardDrive } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import type { WorkspaceCapacityItem, WorkspaceCapacityResponse } from '../api/workspaceCapacityApi';

interface WorkspaceCapacityCardProps {
  capacity: WorkspaceCapacityResponse | null;
  isLoading: boolean;
  hasError: boolean;
}

const formatCapacity = (bytes: number | null): string => (
  bytes == null ? '—' : `${(bytes / 1024 ** 3).toFixed(1)} GiB`
);

const sparklinePoints = (item: WorkspaceCapacityItem): string => {
  if (item.history.length === 0) return '';
  const values = item.history.map(point => point.usedBytes);
  const maximum = Math.max(...values, 1);
  return values.map((value, index) => {
    const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
    const y = 28 - (value / maximum) * 24;
    return `${x},${y}`;
  }).join(' ');
};

export const WorkspaceCapacityCard: React.FC<WorkspaceCapacityCardProps> = ({
  capacity,
  isLoading,
  hasError,
}) => {
  const { t } = useI18n();
  return (
    <section className="space-y-3 rounded-lg border border-border/60 bg-card/70 p-4">
      <div className="flex items-start gap-2">
        <HardDrive aria-hidden="true" className="mt-0.5 h-4 w-4 text-primary" />
        <div>
          <h3 className="text-sm font-semibold">{t('workspace.workspaceSettings.basic.capacity.title')}</h3>
          <p className="text-xs text-muted-foreground">{t('workspace.workspaceSettings.basic.capacity.description')}</p>
        </div>
      </div>
      {hasError ? (
        <p className="text-sm text-muted-foreground">{t('workspace.workspaceSettings.basic.capacity.loadFailed')}</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">{t('workspace.workspaceSettings.basic.capacity.loading')}</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {(capacity?.items ?? []).map(item => (
            <div key={item.storageKind} className="rounded-md border bg-background p-3">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-medium">{t(`workspace.workspaceSettings.basic.capacity.storageKinds.${item.storageKind}`)}</h4>
                <Badge variant="outline">{t(`workspace.workspaceSettings.basic.capacity.risks.${item.risk}`)}</Badge>
              </div>
              <p className="mt-2 text-xl font-semibold">{formatCapacity(item.usedBytes)}</p>
              <p className="text-xs text-muted-foreground">
                {item.allocatedBytes != null
                  ? t('workspace.workspaceSettings.basic.capacity.allocated', { value: formatCapacity(item.allocatedBytes) })
                  : t('workspace.workspaceSettings.basic.capacity.hostAvailable', { value: formatCapacity(item.hostAvailableBytes) })}
              </p>
              {item.utilizationPercent != null ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t('workspace.workspaceSettings.basic.capacity.utilization', { value: item.utilizationPercent })}
                </p>
              ) : null}
              <svg
                className="mt-3 h-8 w-full text-primary"
                viewBox="0 0 100 32"
                role="img"
                aria-label={t('workspace.workspaceSettings.basic.capacity.sparklineLabel')}
              >
                <polyline points={sparklinePoints(item)} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              </svg>
              <p className="mt-1 text-xs text-muted-foreground">
                {item.measuredAt
                  ? t('workspace.workspaceSettings.basic.capacity.measuredAt', { value: item.measuredAt })
                  : t('workspace.workspaceSettings.basic.capacity.neverMeasured')}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
