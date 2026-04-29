import React from 'react';
import { CalendarClock, Database, FolderTree, GitBranch, Link2, Network, Settings, Share2, Trash2 } from 'lucide-react';
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Tabs } from '@/shared/components/ui/tabs';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatFileSize } from '@/shared/utils/fileUtils';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import { KnowledgeBaseAttachmentsTab } from '../components/KnowledgeBaseAttachmentsTab';
import { KnowledgeBaseFilesTab } from '../components/KnowledgeBaseFilesTab';
import { KnowledgeBaseSchedulesTab } from '../components/KnowledgeBaseSchedulesTab';
import { KnowledgeBaseSharingTab } from '../components/KnowledgeBaseSharingTab';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

const KnowledgeBaseGraphTab = React.lazy(() => import('../components/KnowledgeBaseGraphTab'));
const KnowledgeBaseVersionControlTab = React.lazy(() => import('../components/KnowledgeBaseVersionControlTab'));

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
    if (location.pathname.endsWith('/files')) {
      return 'files';
    }
    if (location.pathname.endsWith('/sharing')) {
      return 'sharing';
    }
    if (location.pathname.endsWith('/workspaces')) {
      return 'workspaces';
    }
    if (location.pathname.endsWith('/graph')) {
      return 'graph';
    }
    if (location.pathname.endsWith('/version-control')) {
      return 'version-control';
    }
    if (location.pathname.endsWith('/schedules')) {
      return 'schedules';
    }
    return 'files';
  }, [location.pathname]);

  React.useEffect(() => {
    if (!knowledgeBaseId) {
      return;
    }
    void loadKnowledgeBaseDetail(knowledgeBaseId);
    void loadKnowledgeBaseShares(knowledgeBaseId);
    void loadKnowledgeBaseAttachments(knowledgeBaseId);
  }, [knowledgeBaseId, loadKnowledgeBaseDetail, loadKnowledgeBaseShares, loadKnowledgeBaseAttachments]);

  if (!knowledgeBaseId) {
    return <Navigate to={ROUTES.KNOWLEDGE_BASES} replace />;
  }

  const detail = detailById[knowledgeBaseId];
  const shares = sharesById[knowledgeBaseId] ?? [];
  const attachments = attachmentsById[knowledgeBaseId] ?? [];
  const storageInfo = detail
    ? `${formatFileSize(detail.currentSizeBytes)} / ${detail.quotaBytes ? formatFileSize(detail.quotaBytes) : t('knowledgeBase.detail.cards.quotaUnlimited')}`
    : '--';

  const roleVariant = detail?.accessRole === 'owner'
    ? 'default'
    : detail?.accessRole === 'manager'
      ? 'secondary'
      : 'outline';

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <FeatureHeader
        title={detail?.name ?? t('knowledgeBase.detail.fallbackName', { id: knowledgeBaseId })}
        icon={Database}
        info={(
          <div className="flex min-w-0 items-center gap-2 overflow-hidden text-xs text-muted-foreground">
            <Badge variant={roleVariant}>{detail?.accessRole ?? 'viewer'}</Badge>
            <span className="truncate">
              {t('knowledgeBase.detail.cards.storageTitle')}: {storageInfo}
            </span>
          </div>
        )}
        actions={(
          <>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" disabled>
              <Settings className="mr-1.5 h-3.5 w-3.5" />
              {t('knowledgeBase.detail.settingsAction')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={!detail || (detail.accessRole !== 'owner' && detail.accessRole !== 'manager')}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              {t('knowledgeBase.detail.deleteAction')}
            </Button>
          </>
        )}
      />

      <Tabs value={activeTab} className="flex w-full flex-shrink-0 flex-col">
        <TopTabsBar>
          <TopTabsList className="max-w-2xl">
            <TopTabsTrigger value="files" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)} className="gap-2">
                <FolderTree className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.files')}
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="graph" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_GRAPH(knowledgeBaseId)} className="gap-2">
                <Network className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.graph')}
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="version-control" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_VERSION_CONTROL(knowledgeBaseId)} className="gap-2">
                <GitBranch className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.versionControl')}
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="schedules" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_SCHEDULES(knowledgeBaseId)} className="gap-2">
                <CalendarClock className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.schedules')}
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="sharing" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_SHARING(knowledgeBaseId)} className="gap-2">
                <Share2 className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.sharing')}
                <TopTabsCountBadge count={shares.length} />
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="workspaces" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_WORKSPACES(knowledgeBaseId)} className="gap-2">
                <Link2 className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.workspaces')}
                <TopTabsCountBadge count={attachments.length} />
              </Link>
            </TopTabsTrigger>
          </TopTabsList>
        </TopTabsBar>
      </Tabs>

      <div className="min-h-0 flex-1 overflow-hidden">
        <Routes>
          <Route
            index
            element={<Navigate to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)} replace />}
          />
          <Route
            path="files"
            element={(
              <KnowledgeBaseFilesTab
                knowledgeBaseId={knowledgeBaseId}
                readOnly={detail?.accessRole === 'viewer'}
              />
            )}
          />
          <Route
            path="graph"
            element={(
              <React.Suspense fallback={<div className="p-4 text-sm text-muted-foreground">{t('knowledgeBase.graph.loading')}</div>}>
                <KnowledgeBaseGraphTab knowledgeBaseId={knowledgeBaseId} />
              </React.Suspense>
            )}
          />
          <Route
            path="version-control"
            element={(
              <React.Suspense fallback={<div className="p-4 text-sm text-muted-foreground">{t('knowledgeBase.versionControl.loading')}</div>}>
                <KnowledgeBaseVersionControlTab
                  knowledgeBaseId={knowledgeBaseId}
                  accessRole={detail?.accessRole ?? 'viewer'}
                  versionControlEnabled={detail?.versionControlEnabled}
                  gitLfsEnabled={detail?.gitLfsEnabled}
                />
              </React.Suspense>
            )}
          />
          <Route
            path="schedules"
            element={(
              <KnowledgeBaseSchedulesTab
                knowledgeBaseId={knowledgeBaseId}
                knowledgeBaseName={detail?.name ?? knowledgeBaseId}
                accessRole={detail?.accessRole ?? 'viewer'}
                attachments={attachments}
              />
            )}
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
