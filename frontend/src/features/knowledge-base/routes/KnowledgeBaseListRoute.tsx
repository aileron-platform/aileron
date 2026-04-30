import React from 'react';
import { ArrowUpRight, CalendarClock, Database, GitBranch, HardDrive, Library, Link2, Plus, RefreshCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatFileSize } from '@/shared/utils/fileUtils';
import { cn } from '@/shared/utils/cn';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';
import { KnowledgeBaseCreateDialog } from '../components/KnowledgeBaseCreateDialog';
import type { KnowledgeBaseSummary } from '@/shared/types/knowledgeBase';

export const KnowledgeBaseListRoute: React.FC = () => {
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

  const roleVariant = (role: string) => {
    if (role === 'owner') return 'default';
    if (role === 'manager') return 'secondary';
    if (role === 'editor') return 'outline';
    return 'secondary';
  };

  const formatUpdatedAt = React.useCallback((value: string) => {
    return new Intl.DateTimeFormat(currentLanguage, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(value));
  }, [currentLanguage]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
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

      <div className="flex-1 overflow-auto p-6">
        {isLoadingKnowledgeBases && (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            {t('knowledgeBase.list.loading')}
          </div>
        )}

        {!isLoadingKnowledgeBases && listError && (
          <div className="flex h-32 items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 text-sm text-destructive">
            {listError}
          </div>
        )}

        {!isLoadingKnowledgeBases && !listError && knowledgeBases.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
            <Database className="h-10 w-10 opacity-30" />
            <p>{t('knowledgeBase.list.empty')}</p>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              {t('knowledgeBase.list.createAction')}
            </Button>
          </div>
        )}

        {!isLoadingKnowledgeBases && !listError && knowledgeBases.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {knowledgeBases.map((kb) => (
              <KnowledgeBaseCard
                key={kb.id}
                knowledgeBase={kb}
                attachmentCount={attachmentCounts[kb.id] ?? 0}
                roleVariant={roleVariant}
                formatUpdatedAt={formatUpdatedAt}
              />
            ))}
          </div>
        )}
      </div>

      <KnowledgeBaseCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
};

interface KnowledgeBaseCardProps {
  knowledgeBase: KnowledgeBaseSummary;
  attachmentCount: number;
  roleVariant: (role: string) => 'default' | 'secondary' | 'outline';
  formatUpdatedAt: (value: string) => string;
}

const KnowledgeBaseCard: React.FC<KnowledgeBaseCardProps> = ({
  knowledgeBase,
  attachmentCount,
  roleVariant,
  formatUpdatedAt,
}) => {
  const { t } = useI18n();
  const quotaBytes = knowledgeBase.quotaBytes ?? null;
  const hasQuota = typeof quotaBytes === 'number' && quotaBytes > 0;
  const usagePercent = hasQuota
    ? Math.min(100, Math.round((knowledgeBase.currentSizeBytes / quotaBytes) * 100))
    : 0;
  const storageValue = hasQuota
    ? t('knowledgeBase.list.stats.storageUsageWithQuota', {
        used: formatFileSize(knowledgeBase.currentSizeBytes),
        quota: formatFileSize(quotaBytes),
      })
    : t('knowledgeBase.list.stats.storageUsageUnlimited', {
        used: formatFileSize(knowledgeBase.currentSizeBytes),
      });

  return (
    <Link
      to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBase.id)}
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
        <Badge variant={roleVariant(knowledgeBase.accessRole)} className="shrink-0">
          {t(`knowledgeBase.common.role.${knowledgeBase.accessRole}`)}
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
          <span className="shrink-0 font-semibold text-foreground">{hasQuota ? `${usagePercent}%` : t('knowledgeBase.list.stats.unlimited')}</span>
        </div>
        <Progress
          value={usagePercent}
          aria-label={t('knowledgeBase.list.stats.storageProgressLabel')}
          className={cn('mt-2 h-2', !hasQuota && 'bg-muted')}
        />
        <div className="mt-2 truncate text-xs text-muted-foreground">{storageValue}</div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="flex min-h-[64px] flex-col justify-between rounded-md bg-muted/35 p-2">
          <div className="flex items-start gap-1.5 text-muted-foreground">
            <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 leading-4">{t('knowledgeBase.list.stats.attachedWorkspaces')}</span>
          </div>
          <div className="pt-1 text-sm font-semibold leading-none text-foreground">{attachmentCount}</div>
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

export default KnowledgeBaseListRoute;
