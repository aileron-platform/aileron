import React from 'react';
import { Database, ExternalLink, Library, Plus, RefreshCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
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
    <div className="h-full overflow-auto p-6 md:p-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
              <Library className="h-3.5 w-3.5" />
              {t('knowledgeBase.list.pill')}
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t('knowledgeBase.list.title')}</h1>
              <p className="text-sm text-muted-foreground">{t('knowledgeBase.list.description')}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start md:self-auto">
            <Button variant="outline" size="sm" className="gap-2" onClick={() => void reloadKnowledgeBases()}>
              <RefreshCcw className="h-4 w-4" />
              {t('knowledgeBase.list.refreshAction')}
            </Button>
            <Button className="gap-2" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              {t('knowledgeBase.list.createAction')}
            </Button>
          </div>
        </div>

        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Database className="h-5 w-5 text-sky-600" />
              {t('knowledgeBase.list.cardTitle')}
            </CardTitle>
            <CardDescription>{t('knowledgeBase.list.cardDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {isLoadingKnowledgeBases && (
              <div className="rounded-xl border border-dashed bg-background/80 p-6 text-sm text-muted-foreground">
                {t('knowledgeBase.list.loading')}
              </div>
            )}

            {!isLoadingKnowledgeBases && listError && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
                {listError}
              </div>
            )}

            {!isLoadingKnowledgeBases && !listError && knowledgeBases.length === 0 && (
              <div className="rounded-xl border border-dashed bg-background/80 p-6 text-sm text-muted-foreground">
                {t('knowledgeBase.list.empty')}
              </div>
            )}

            {!isLoadingKnowledgeBases && !listError && knowledgeBases.map((kb) => (
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
          </CardContent>
        </Card>

        <KnowledgeBaseCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      </div>
    </div>
  );
};

export default KnowledgeBaseListRoute;
