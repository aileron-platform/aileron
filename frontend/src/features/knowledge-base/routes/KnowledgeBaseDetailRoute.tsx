import React from 'react';
import { BookOpen, CalendarClock, Database, FolderTree, GitBranch, Link2, Loader2, Network, Settings, Share2, Trash2 } from 'lucide-react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Tabs } from '@/shared/components/ui/tabs';
import { Textarea } from '@/shared/components/ui/textarea';
import { useToast } from '@/shared/components/ui/use-toast';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatFileSize } from '@/shared/utils/fileUtils';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import type { KnowledgeBaseDetail } from '@/shared/types/knowledgeBase';
import { KnowledgeBaseAttachmentsTab } from '../components/KnowledgeBaseAttachmentsTab';
import { KnowledgeBaseFilesTab } from '../components/KnowledgeBaseFilesTab';
import { KnowledgeBaseSchedulesTab } from '../components/KnowledgeBaseSchedulesTab';
import { KnowledgeBaseSharingTab } from '../components/KnowledgeBaseSharingTab';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';

const KnowledgeBaseWikiTab = React.lazy(() => import('../components/KnowledgeBaseWikiTab'));
const KnowledgeBaseGraphTab = React.lazy(() => import('../components/KnowledgeBaseGraphTab'));
const KnowledgeBaseVersionControlTab = React.lazy(() => import('../components/KnowledgeBaseVersionControlTab'));

export const KnowledgeBaseDetailRoute: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { knowledgeBaseId } = useParams<{ knowledgeBaseId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const {
    detailById,
    sharesById,
    attachmentsById,
    isMutating,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseAttachments,
    updateKnowledgeBase,
    deleteKnowledgeBase,
  } = useKnowledgeBase();
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);

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
    if (location.pathname.endsWith('/wiki')) {
      return 'wiki';
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
    return 'wiki';
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
  const canManageKnowledgeBase = detail?.accessRole === 'owner' || detail?.accessRole === 'manager';

  const handleSettingsSave = React.useCallback(
    async (payload: { name: string; description: string; quotaBytes: number | null }) => {
      if (!knowledgeBaseId || !detail) {
        return;
      }

      try {
        const updated = await updateKnowledgeBase(knowledgeBaseId, payload);
        toast({
          variant: 'success',
          title: t('knowledgeBase.detail.settings.toasts.saveSuccess.title'),
          description: updated.name,
        });
        setSettingsOpen(false);
      } catch (error) {
        toast({
          variant: 'destructive',
          title: t('knowledgeBase.detail.settings.toasts.saveFailed.title'),
          description: error instanceof Error ? error.message : t('knowledgeBase.detail.settings.toasts.saveFailed.description'),
        });
      }
    },
    [detail, knowledgeBaseId, t, toast, updateKnowledgeBase],
  );

  const handleDelete = React.useCallback(async () => {
    if (!knowledgeBaseId || !detail) {
      return;
    }

    try {
      await deleteKnowledgeBase(knowledgeBaseId);
      toast({
        variant: 'success',
        title: t('knowledgeBase.detail.delete.toasts.success.title'),
        description: detail.name,
      });
      setDeleteOpen(false);
      navigate(ROUTES.KNOWLEDGE_BASES);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('knowledgeBase.detail.delete.toasts.failed.title'),
        description: error instanceof Error ? error.message : t('knowledgeBase.detail.delete.toasts.failed.description'),
      });
    }
  }, [deleteKnowledgeBase, detail, knowledgeBaseId, navigate, t, toast]);

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
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={!canManageKnowledgeBase}
              onClick={() => setSettingsOpen(true)}
            >
              <Settings className="mr-1.5 h-3.5 w-3.5" />
              {t('knowledgeBase.detail.settingsAction')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={!canManageKnowledgeBase}
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              {t('knowledgeBase.detail.deleteAction')}
            </Button>
          </>
        )}
      />

      <Tabs value={activeTab} className="flex w-full flex-shrink-0 flex-col">
        <TopTabsBar>
          <TopTabsList>
            <TopTabsTrigger value="files" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)} className="gap-2">
                <FolderTree className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.files')}
              </Link>
            </TopTabsTrigger>
            <TopTabsTrigger value="wiki" asChild>
              <Link to={ROUTES.KNOWLEDGE_BASE_DETAIL_WIKI(knowledgeBaseId)} className="gap-2">
                <BookOpen className="h-4 w-4" />
                {t('knowledgeBase.detail.tabs.wiki')}
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
            element={<Navigate to={ROUTES.KNOWLEDGE_BASE_DETAIL_WIKI(knowledgeBaseId)} replace />}
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
            path="wiki"
            element={(
              <React.Suspense fallback={<div className="p-4 text-sm text-muted-foreground">{t('knowledgeBase.wiki.loading')}</div>}>
                <KnowledgeBaseWikiTab knowledgeBaseId={knowledgeBaseId} />
              </React.Suspense>
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
          <Route
            path="*"
            element={<Navigate to={ROUTES.KNOWLEDGE_BASE_DETAIL_WIKI(knowledgeBaseId)} replace />}
          />
        </Routes>
      </div>

      {detail ? (
        <KnowledgeBaseSettingsDialog
          open={settingsOpen}
          knowledgeBase={detail}
          isSaving={isMutating}
          onOpenChange={setSettingsOpen}
          onSave={handleSettingsSave}
        />
      ) : null}

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5 text-destructive" />
              {t('knowledgeBase.detail.delete.title')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('knowledgeBase.detail.delete.description', { name: detail?.name ?? knowledgeBaseId })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMutating}>
              {t('knowledgeBase.detail.delete.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isMutating || !canManageKnowledgeBase}
              onClick={(event) => {
                event.preventDefault();
                void handleDelete();
              }}
            >
              {isMutating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {t('knowledgeBase.detail.delete.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const KnowledgeBaseSettingsDialog: React.FC<{
  open: boolean;
  knowledgeBase: KnowledgeBaseDetail;
  isSaving: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: { name: string; description: string; quotaBytes: number | null }) => Promise<void>;
}> = ({
  open,
  knowledgeBase,
  isSaving,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [name, setName] = React.useState(knowledgeBase.name);
  const [description, setDescription] = React.useState(knowledgeBase.description ?? '');
  const [quotaBytes, setQuotaBytes] = React.useState(
    knowledgeBase.quotaBytes == null ? '' : String(knowledgeBase.quotaBytes),
  );
  const [validationKey, setValidationKey] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    setName(knowledgeBase.name);
    setDescription(knowledgeBase.description ?? '');
    setQuotaBytes(knowledgeBase.quotaBytes == null ? '' : String(knowledgeBase.quotaBytes));
    setValidationKey(null);
  }, [knowledgeBase, open]);

  const parseQuota = React.useCallback((): number | null | undefined => {
    const trimmed = quotaBytes.trim();
    if (!trimmed) {
      return null;
    }
    if (!/^\d+$/.test(trimmed)) {
      setValidationKey('knowledgeBase.detail.settings.validation.quotaNumeric');
      return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isSafeInteger(parsed) || parsed < 0) {
      setValidationKey('knowledgeBase.detail.settings.validation.quotaNumeric');
      return undefined;
    }
    if (parsed < knowledgeBase.currentSizeBytes) {
      setValidationKey('knowledgeBase.detail.settings.validation.quotaBelowUsage');
      return undefined;
    }
    return parsed;
  }, [knowledgeBase.currentSizeBytes, quotaBytes]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setValidationKey(null);

    const nextName = name.trim();
    if (!nextName) {
      setValidationKey('knowledgeBase.detail.settings.validation.nameRequired');
      return;
    }

    const nextQuota = parseQuota();
    if (nextQuota === undefined) {
      return;
    }

    await onSave({
      name: nextName,
      description: description.trim(),
      quotaBytes: nextQuota,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <form className="space-y-5" onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-primary" />
              {t('knowledgeBase.detail.settings.title')}
            </DialogTitle>
            <DialogDescription>
              {t('knowledgeBase.detail.settings.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-name">{t('knowledgeBase.detail.settings.nameLabel')}</Label>
            <Input
              id="kb-settings-name"
              value={name}
              disabled={isSaving}
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-slug">{t('knowledgeBase.detail.settings.slugLabel')}</Label>
            <Input id="kb-settings-slug" value={knowledgeBase.slug} disabled readOnly />
            <p className="text-xs text-muted-foreground">
              {t('knowledgeBase.detail.settings.slugHint')}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-description">{t('knowledgeBase.detail.settings.descriptionLabel')}</Label>
            <Textarea
              id="kb-settings-description"
              value={description}
              disabled={isSaving}
              rows={4}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-settings-quota">{t('knowledgeBase.detail.settings.quotaLabel')}</Label>
            <Input
              id="kb-settings-quota"
              value={quotaBytes}
              inputMode="numeric"
              disabled={isSaving}
              placeholder={t('knowledgeBase.detail.settings.quotaPlaceholder')}
              onChange={(event) => setQuotaBytes(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t('knowledgeBase.detail.settings.quotaHint', {
                usage: formatFileSize(knowledgeBase.currentSizeBytes),
              })}
            </p>
          </div>

          {validationKey ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {t(validationKey, { usage: formatFileSize(knowledgeBase.currentSizeBytes) })}
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="ghost" disabled={isSaving} onClick={() => onOpenChange(false)}>
              {t('knowledgeBase.common.actions.cancel')}
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {t('knowledgeBase.common.actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default KnowledgeBaseDetailRoute;
