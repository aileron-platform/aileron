import React from 'react';
import { ArrowUpRight, CalendarClock, Database, GitBranch, HardDrive, Library, Link2, Plus, RefreshCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';
import { KnowledgeBaseCreateDialog } from '../components/KnowledgeBaseCreateDialog';
import type { KnowledgeBaseSummary } from '@/features/knowledge-base/model/knowledgeBaseTypes';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import { formatKnowledgeBaseFileSize } from '../model/formatKnowledgeBaseFileSize';
import { KnowledgeBaseShellAdapter } from '../components/KnowledgeBaseShellAdapter';

const ROLE_BADGE_VARIANT: Record<
  ResourceAccessRole,
  'default' | 'secondary' | 'outline'
> = {
  owner: 'default',
  manager: 'secondary',
  reader: 'outline',
};

interface KnowledgeBaseListRouteProps {
  navigationSlot?: React.ReactNode;
}

export const KnowledgeBaseListRoute: React.FC<KnowledgeBaseListRouteProps> = ({ navigationSlot }) => {
  const { t, state } = useI18n();
  const currentLanguage = state?.currentLanguage ?? 'en';
  const {
    knowledgeBases,
    attachmentCounts,
    isLoadingKnowledgeBases,
    listError,
    reloadKnowledgeBases,
  } = useKnowledgeBase();
  const [createOpen, setCreateOpen] = React.useState(false);
  const refreshInFlightRef = React.useRef<Promise<void> | null>(null);

  React.useEffect(() => {
    const refresh = () => {
      if (refreshInFlightRef.current) {
        return;
      }
      const request = reloadKnowledgeBases().finally(() => {
        refreshInFlightRef.current = null;
      });
      refreshInFlightRef.current = request;
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refresh();
      }
    };

    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [reloadKnowledgeBases]);

  const formatUpdatedAt = React.useCallback((value: string) => {
    return new Intl.DateTimeFormat(currentLanguage, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(value));
  }, [currentLanguage]);

  const header = (
    <FeatureHeader
      title={t('knowledgeBase.list.title')}
      icon={Library}
      info={(
        <span className="text-xs text-muted-foreground">
          {t('knowledgeBase.list.description')}
        </span>
      )}
      actions={(
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => void reloadKnowledgeBases()}>
            <RefreshCcw className="mr-1 h-3.5 w-3.5" />
            {t('knowledgeBase.list.refreshAction')}
          </Button>
          <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('knowledgeBase.list.createAction')}
          </Button>
        </div>
      )}
    />
  );

  if (isLoadingKnowledgeBases || listError) {
    return (
      <KnowledgeBaseShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          header,
          content: (
            <div className="flex h-full items-center justify-center p-6">
              {isLoadingKnowledgeBases ? (
                <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                  {t('knowledgeBase.list.loading')}
                </div>
              ) : (
                <div className="flex h-32 w-full items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 text-sm text-destructive">
                  {listError}
                </div>
              )}
            </div>
          ),
        }}
      />
    );
  }

  return (
    <KnowledgeBaseShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header,
        main: {
          accessibleLabel: t('knowledgeBase.list.title'),
          content: (
            <>
              <div className="h-full overflow-auto p-6">
        {knowledgeBases.length === 0 && (
          <EmptyState
            icon={Database}
            title={t('knowledgeBase.list.empty')}
            action={(
              <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setCreateOpen(true)}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                {t('knowledgeBase.list.createAction')}
              </Button>
            )}
          />
        )}

        {knowledgeBases.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {knowledgeBases.map((kb) => (
              <KnowledgeBaseCard
                key={kb.id}
                knowledgeBase={kb}
                attachmentCount={attachmentCounts[kb.id] ?? null}
                formatUpdatedAt={formatUpdatedAt}
              />
            ))}
          </div>
        )}
              </div>
              <KnowledgeBaseCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
            </>
          ),
        },
      }}
    />
  );
};

interface KnowledgeBaseCardProps {
  knowledgeBase: KnowledgeBaseSummary;
  attachmentCount: number | null;
  formatUpdatedAt: (value: string) => string;
}

const KnowledgeBaseCard: React.FC<KnowledgeBaseCardProps> = ({
  knowledgeBase,
  attachmentCount,
  formatUpdatedAt,
}) => {
  const { t } = useI18n();
  const usagePercent = Math.min(100, Math.round(knowledgeBase.utilizationPercent ?? 0));
  const storageValue = t('knowledgeBase.list.stats.storageUsageWithQuota', {
    used: formatKnowledgeBaseFileSize(knowledgeBase.currentSizeBytes),
    quota: formatKnowledgeBaseFileSize(knowledgeBase.effectiveQuotaBytes),
  });

  return (
    <Link
      to={ROUTES.knowledgeBase.files(knowledgeBase.id)}
      className="group flex min-h-[248px] flex-col rounded-lg border bg-card p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="line-clamp-2 min-h-[3rem] text-base font-semibold leading-6 text-foreground">
              {knowledgeBase.name}
            </div>
          </div>
        </div>
        <Badge variant={ROLE_BADGE_VARIANT[knowledgeBase.accessRole]} className="shrink-0">
          {knowledgeBase.accessSource === 'platform_admin'
            ? t('knowledgeBase.common.role.platformAdmin')
            : t(`knowledgeBase.common.role.${knowledgeBase.accessRole}`)}
        </Badge>
      </div>

      <p className="mt-3 line-clamp-2 text-sm leading-5 text-muted-foreground">
        {knowledgeBase.description || t('knowledgeBase.list.stats.noDescription')}
      </p>

      <div className="mt-3 rounded-md border bg-muted/25 p-3">
        <div className="flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
            <HardDrive className="h-3.5 w-3.5" />
            <span>{t('knowledgeBase.list.stats.storage')}</span>
          </div>
          <span className="shrink-0 font-semibold text-foreground">{usagePercent}%</span>
        </div>
        <Progress
          value={usagePercent}
          aria-label={t('knowledgeBase.list.stats.storageProgressLabel')}
          className="mt-2 h-2"
        />
        <div className="mt-2 truncate text-xs text-muted-foreground">{storageValue}</div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="flex min-h-[64px] flex-col justify-between rounded-md bg-muted/35 p-2">
          <div className="flex items-start gap-1.5 text-muted-foreground">
            <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 leading-4">{t('knowledgeBase.list.stats.attachedWorkspaces')}</span>
          </div>
          <div className="pt-1 text-sm font-semibold leading-none text-foreground">
            {attachmentCount ?? t('knowledgeBase.list.stats.attachmentCountUnavailable')}
          </div>
        </div>
        <div className="flex min-h-[64px] flex-col justify-between rounded-md bg-muted/35 p-2">
          <div className="flex items-start gap-1.5 text-muted-foreground">
            <GitBranch className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 leading-4">{t('knowledgeBase.list.stats.versionControl')}</span>
          </div>
          <div className="truncate pt-1 text-sm font-semibold leading-none text-foreground">
            {knowledgeBase.versionControlEnabled
              ? (knowledgeBase.gitDefaultBranch || t('knowledgeBase.list.stats.versionControlEnabled'))
              : t('knowledgeBase.list.stats.versionControlDisabled')}
          </div>
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 pt-4 text-xs">
        <div className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
          <CalendarClock className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">
            {t('knowledgeBase.list.stats.updatedAt', { date: formatUpdatedAt(knowledgeBase.updatedAt) })}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1 font-medium text-primary">
          {t('knowledgeBase.list.openDetail')}
          <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </div>
      </div>
    </Link>
  );
};
