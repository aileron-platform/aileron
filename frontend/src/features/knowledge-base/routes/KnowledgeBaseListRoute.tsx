import React from 'react';
import { Database, ExternalLink, Library, Plus, RefreshCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatFileSize } from '@/shared/utils/fileUtils';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';
import { KnowledgeBaseCreateDialog } from '../components/KnowledgeBaseCreateDialog';

export const KnowledgeBaseListRoute: React.FC = () => {
  const { t } = useI18n();
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
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {knowledgeBases.map((kb) => (
              <Link
                key={kb.id}
                to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(kb.id)}
                className="rounded-xl border bg-background/80 p-4 transition-colors hover:border-primary/40 hover:bg-background"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-base font-semibold text-foreground">{kb.name}</div>
                    <div className="truncate text-xs text-muted-foreground">{kb.slug}</div>
                  </div>
                  <Badge variant={roleVariant(kb.accessRole)}>
                    {kb.accessRole}
                  </Badge>
                </div>

                <p className="mb-4 min-h-[40px] text-sm text-muted-foreground">
                  {kb.description || t('knowledgeBase.list.stats.noDescription')}
                </p>

                <div className="grid gap-2 text-sm text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>{t('knowledgeBase.list.stats.storage')}</span>
                    <span className="font-medium text-foreground">
                      {formatFileSize(kb.currentSizeBytes)}
                      {kb.quotaBytes ? ` / ${formatFileSize(kb.quotaBytes)}` : ` / ${t('knowledgeBase.list.stats.unlimited')}`}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>{t('knowledgeBase.list.stats.attachedWorkspaces')}</span>
                    <span className="font-medium text-foreground">{attachmentCounts[kb.id] ?? 0}</span>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-2 text-xs font-medium text-primary">
                  {t('knowledgeBase.list.openDetail')}
                  <ExternalLink className="h-3.5 w-3.5" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <KnowledgeBaseCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
};

export default KnowledgeBaseListRoute;
