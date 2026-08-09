import React from 'react';
import { Clock3, RefreshCw } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  MarketplaceActivityAction,
  MarketplaceActivityRecord,
  MarketplaceActivityStatus,
  MarketplaceProvider,
} from '@/features/marketplace/model/marketplaceTypes';
import { listMarketplaceActivity } from '../../../api/marketplaceApi';
import { getMarketplaceInstallErrorKey } from '../../../components/marketplaceInstallModel';

const PAGE_SIZE = 50;
const PROVIDER_OPTIONS: MarketplaceProvider[] = ['claude-code', 'codex'];
const ACTION_OPTIONS: MarketplaceActivityAction[] = [
  'install',
  'copy',
  'import',
  'delete',
];
const STATUS_OPTIONS: MarketplaceActivityStatus[] = [
  'succeeded',
  'failed',
];

const isProvider = (value: string | null): value is MarketplaceProvider => (
  value !== null && PROVIDER_OPTIONS.includes(value as MarketplaceProvider)
);

const isAction = (
  value: string | null,
): value is MarketplaceActivityAction => (
  value !== null && ACTION_OPTIONS.includes(value as MarketplaceActivityAction)
);

const isStatus = (
  value: string | null,
): value is MarketplaceActivityStatus => (
  value !== null && STATUS_OPTIONS.includes(value as MarketplaceActivityStatus)
);

const positivePage = (value: string | null): number => {
  const page = Number(value);
  return Number.isInteger(page) && page > 0 ? page : 1;
};

const statusBadgeVariant = (
  status: MarketplaceActivityStatus,
): 'secondary' | 'destructive' => {
  if (status === 'succeeded') return 'secondary';
  return 'destructive';
};

export const MarketplaceActivityTab: React.FC = () => {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = React.useState<MarketplaceActivityRecord[]>([]);
  const [totalPages, setTotalPages] = React.useState(0);
  const [isLoading, setIsLoading] = React.useState(true);
  const [hasError, setHasError] = React.useState(false);
  const requestSequence = React.useRef(0);

  const page = positivePage(searchParams.get('page'));
  const workspaceId = searchParams.get('workspaceId')?.trim() ?? '';
  const provider = isProvider(searchParams.get('provider'))
    ? searchParams.get('provider') as MarketplaceProvider
    : null;
  const packageId = searchParams.get('packageId')?.trim() ?? '';
  const action = isAction(searchParams.get('action'))
    ? searchParams.get('action') as MarketplaceActivityAction
    : null;
  const status = isStatus(searchParams.get('status'))
    ? searchParams.get('status') as MarketplaceActivityStatus
    : null;

  const updateFilters = React.useCallback((
    updates: Record<string, string | null>,
    resetPage = true,
  ) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    if (resetPage) next.delete('page');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const loadActivity = React.useCallback(async () => {
    const sequence = ++requestSequence.current;
    setIsLoading(true);
    setHasError(false);
    try {
      const result = await listMarketplaceActivity({
        page,
        pageSize: PAGE_SIZE,
        workspaceId: workspaceId || undefined,
        provider: provider ?? undefined,
        packageId: packageId || undefined,
        action: action ?? undefined,
        status: status ?? undefined,
      });
      if (requestSequence.current !== sequence) return;
      setItems(result.items);
      setTotalPages(result.totalPages);
    } catch {
      if (requestSequence.current !== sequence) return;
      setHasError(true);
    } finally {
      if (requestSequence.current === sequence) {
        setIsLoading(false);
      }
    }
  }, [action, packageId, page, provider, status, workspaceId]);

  React.useEffect(() => {
    void loadActivity();
  }, [loadActivity]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock3 className="h-5 w-5" />
              {t('marketplace.settings.activity.title')}
            </CardTitle>
            <CardDescription>
              {t('marketplace.settings.activity.description')}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadActivity()}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-1.5 h-4 w-4 ${
                isLoading ? 'animate-spin' : ''
              }`}
            />
            {t('marketplace.common.actions.refresh')}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Input
            value={workspaceId}
            onChange={event => updateFilters({
              workspaceId: event.target.value || null,
            })}
            aria-label={t('marketplace.settings.activity.filters.workspace')}
            placeholder={t('marketplace.settings.activity.filters.workspace')}
          />
          <Select
            value={provider ?? 'all'}
            onValueChange={value => updateFilters({
              provider: value === 'all' ? null : value,
            })}
          >
            <SelectTrigger
              aria-label={t('marketplace.settings.activity.filters.provider')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('marketplace.settings.activity.filters.allProviders')}
              </SelectItem>
              {PROVIDER_OPTIONS.map(option => (
                <SelectItem key={option} value={option}>
                  {t(`marketplace.providers.${option}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={packageId}
            onChange={event => updateFilters({
              packageId: event.target.value || null,
            })}
            aria-label={t('marketplace.settings.activity.filters.package')}
            placeholder={t('marketplace.settings.activity.filters.package')}
          />
          <Select
            value={action ?? 'all'}
            onValueChange={value => updateFilters({
              action: value === 'all' ? null : value,
            })}
          >
            <SelectTrigger
              aria-label={t('marketplace.settings.activity.filters.action')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('marketplace.settings.activity.filters.allActions')}
              </SelectItem>
              {ACTION_OPTIONS.map(option => (
                <SelectItem key={option} value={option}>
                  {t(`marketplace.activity.actions.${option}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={status ?? 'all'}
            onValueChange={value => updateFilters({
              status: value === 'all' ? null : value,
            })}
          >
            <SelectTrigger
              aria-label={t('marketplace.settings.activity.filters.status')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('marketplace.settings.activity.filters.allStatuses')}
              </SelectItem>
              {STATUS_OPTIONS.map(option => (
                <SelectItem key={option} value={option}>
                  {t(`marketplace.activity.status.${option}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {hasError ? (
          <div className="rounded-lg border border-destructive/40 px-4 py-6 text-center text-sm text-destructive">
            {t('marketplace.settings.activity.loadError')}
          </div>
        ) : null}

        {!hasError && !isLoading && items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            {t('marketplace.settings.activity.empty')}
          </div>
        ) : null}

        {items.map(item => (
          <article
            key={item.id}
            className="space-y-3 rounded-lg border border-border p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">
                  {t(`marketplace.activity.actions.${item.action}`)}
                </span>
                <Badge variant={statusBadgeVariant(item.status)}>
                  {t(`marketplace.activity.status.${item.status}`)}
                </Badge>
              </div>
              <time className="text-xs text-muted-foreground">
                {item.createdAt}
              </time>
            </div>

            <dl className="grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
              {item.operationId ? (
                <div>
                  <dt className="text-muted-foreground">
                    {t('marketplace.settings.activity.fields.operationId')}
                  </dt>
                  <dd className="break-all font-mono">{item.operationId}</dd>
                </div>
              ) : null}
              {item.workspaceId ? (
                <div>
                  <dt className="text-muted-foreground">
                    {t('marketplace.settings.activity.fields.workspace')}
                  </dt>
                  <dd className="font-mono">{item.workspaceId}</dd>
                </div>
              ) : null}
              {item.provider ? (
                <div>
                  <dt className="text-muted-foreground">
                    {t('marketplace.settings.activity.fields.provider')}
                  </dt>
                  <dd>{t(`marketplace.providers.${item.provider}`)}</dd>
                </div>
              ) : null}
              {item.packageId ? (
                <div>
                  <dt className="text-muted-foreground">
                    {t('marketplace.settings.activity.fields.package')}
                  </dt>
                  <dd className="font-mono">{item.packageId}</dd>
                </div>
              ) : null}
              {item.marketplaceId ? (
                <div>
                  <dt className="text-muted-foreground">
                    {t('marketplace.settings.activity.fields.marketplace')}
                  </dt>
                  <dd className="font-mono">{item.marketplaceId}</dd>
                </div>
              ) : null}
            </dl>

            {item.errorCode ? (
              <div className="space-y-1 text-xs text-destructive">
                <p>{t(getMarketplaceInstallErrorKey(item.errorCode))}</p>
                <details>
                  <summary className="cursor-pointer">
                    {t('marketplace.settings.activity.errorDetails')}
                  </summary>
                  <code className="mt-1 block break-all">
                    {item.errorCode}
                  </code>
                </details>
              </div>
            ) : null}
          </article>
        ))}

        {isLoading && items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            {t('marketplace.settings.activity.loading')}
          </div>
        ) : null}

        {totalPages > 1 ? (
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => updateFilters({
                page: String(Math.max(1, page - 1)),
              }, false)}
              disabled={page <= 1 || isLoading}
            >
              {t('marketplace.settings.activity.pagination.previous')}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t('marketplace.settings.activity.pagination.summary', {
                page,
                totalPages,
              })}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => updateFilters({
                page: String(page + 1),
              }, false)}
              disabled={page >= totalPages || isLoading}
            >
              {t('marketplace.settings.activity.pagination.next')}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};
