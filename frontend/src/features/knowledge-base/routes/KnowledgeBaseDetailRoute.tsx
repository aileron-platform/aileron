import React from 'react';
import { Database, Files, Link2, Settings, Share2, Trash2 } from 'lucide-react';
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatFileSize } from '@/shared/utils/fileUtils';
import { KnowledgeBaseAttachmentsTab } from '../components/KnowledgeBaseAttachmentsTab';
import { KnowledgeBaseFilesTab } from '../components/KnowledgeBaseFilesTab';
import { KnowledgeBaseSharingTab } from '../components/KnowledgeBaseSharingTab';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

const DetailPanel: React.FC<{
  title: string;
  description: string;
  hint: string;
  extra?: React.ReactNode;
}> = ({ title, description, hint }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-dashed bg-muted/40 p-4 text-sm text-muted-foreground">
          {hint}
        </div>
      </CardContent>
    </Card>
  );
};

export const KnowledgeBaseDetailRoute: React.FC = () => {
  const { t } = useI18n();
  const { knowledgeBaseId } = useParams<{ knowledgeBaseId: string }>();
  const location = useLocation();
  const {
    detailById,
    sharesById,
    attachmentsById,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseAttachments,
  } = useKnowledgeBase();

  const activeTab = React.useMemo(() => {
    if (location.pathname.endsWith('/sharing')) {
      return 'sharing';
    }
    if (location.pathname.endsWith('/workspaces')) {
      return 'workspaces';
    }
    return 'files';
  }, [location.pathname]);

  if (!knowledgeBaseId) {
    return <Navigate to={ROUTES.KNOWLEDGE_BASES} replace />;
  }

  React.useEffect(() => {
    void loadKnowledgeBaseDetail(knowledgeBaseId);
    void loadKnowledgeBaseShares(knowledgeBaseId);
    void loadKnowledgeBaseAttachments(knowledgeBaseId);
  }, [knowledgeBaseId, loadKnowledgeBaseDetail, loadKnowledgeBaseShares, loadKnowledgeBaseAttachments]);

  const detail = detailById[knowledgeBaseId];
  const shares = sharesById[knowledgeBaseId] ?? [];
  const attachments = attachmentsById[knowledgeBaseId] ?? [];

  const roleVariant = detail?.accessRole === 'owner'
    ? 'default'
    : detail?.accessRole === 'manager'
      ? 'secondary'
      : 'outline';

  return (
    <div className="h-full overflow-auto p-6 md:p-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Link className="hover:text-foreground" to={ROUTES.KNOWLEDGE_BASES}>
              {t('knowledgeBase.detail.breadcrumbRoot')}
            </Link>
            <span>/</span>
            <span className="text-foreground">{detail?.name ?? knowledgeBaseId}</span>
          </div>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={roleVariant}>{detail?.accessRole ?? 'viewer'}</Badge>
                <Badge variant="outline">{detail?.slug ?? knowledgeBaseId}</Badge>
              </div>
              <div>
                <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
                  <Database className="h-7 w-7 text-sky-600" />
                  {detail?.name ?? t('knowledgeBase.detail.fallbackName', { id: knowledgeBaseId })}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {detail?.description || t('knowledgeBase.detail.noDescription')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled>
                <Settings className="mr-2 h-4 w-4" />
                {t('knowledgeBase.detail.settingsAction')}
              </Button>
              <Button variant="outline" size="sm" disabled={!detail || (detail.accessRole !== 'owner' && detail.accessRole !== 'manager')}>
                <Trash2 className="mr-2 h-4 w-4" />
                {t('knowledgeBase.detail.deleteAction')}
              </Button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('knowledgeBase.detail.cards.storageTitle')}</CardTitle>
              <CardDescription>{t('knowledgeBase.detail.cards.storageDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm">
              <div className="font-semibold text-foreground">
                {detail ? formatFileSize(detail.currentSizeBytes) : '--'}
              </div>
              <div className="text-muted-foreground">
                {detail?.quotaBytes
                  ? t('knowledgeBase.detail.cards.quota', { value: formatFileSize(detail.quotaBytes) })
                  : t('knowledgeBase.detail.cards.quotaUnlimited')}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('knowledgeBase.detail.cards.sharingTitle')}</CardTitle>
              <CardDescription>{t('knowledgeBase.detail.cards.sharingDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm">
              <div className="font-semibold text-foreground">{shares.length}</div>
              <div className="text-muted-foreground">{t('knowledgeBase.detail.cards.sharingHint')}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('knowledgeBase.detail.cards.workspacesTitle')}</CardTitle>
              <CardDescription>{t('knowledgeBase.detail.cards.workspacesDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm">
              <div className="font-semibold text-foreground">{attachments.length}</div>
              <div className="text-muted-foreground">{t('knowledgeBase.detail.cards.workspacesHint')}</div>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} className="w-full">
          <TabsList className="grid w-full max-w-xl grid-cols-3">
            <TabsTrigger value="files" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)} className="gap-2">
                <Files className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.files')}
              </Link>
            </TabsTrigger>
            <TabsTrigger value="sharing" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_SHARING(knowledgeBaseId)} className="gap-2">
                <Share2 className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.sharing')}
              </Link>
            </TabsTrigger>
            <TabsTrigger value="workspaces" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_WORKSPACES(knowledgeBaseId)} className="gap-2">
                <Link2 className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.workspaces')}
              </Link>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <Routes>
          <Route
            index
            element={<Navigate to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)} replace />}
          />
          <Route
            path="files"
            element={<KnowledgeBaseFilesTab knowledgeBaseId={knowledgeBaseId} readOnly={detail?.accessRole === 'viewer'} />}
          />
          <Route
            path="sharing"
            element={<KnowledgeBaseSharingTab knowledgeBaseId={knowledgeBaseId} accessRole={detail?.accessRole ?? 'viewer'} />}
          />
          <Route
            path="workspaces"
            element={<KnowledgeBaseAttachmentsTab knowledgeBaseId={knowledgeBaseId} accessRole={detail?.accessRole ?? 'viewer'} />}
          />
        </Routes>
      </div>
    </div>
  );
};

export default KnowledgeBaseDetailRoute;
