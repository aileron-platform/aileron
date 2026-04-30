import React from 'react';
import { CalendarClock, RefreshCw, Save } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '@/features/automation/services/automationApi';
import type { AutomationJob } from '@/features/automation/types';
import type { KnowledgeBaseAttachmentSummary } from '@/shared/types/knowledgeBase';

interface KnowledgeBaseSchedulesTabProps {
  knowledgeBaseId: string;
  knowledgeBaseName: string;
  accessRole: string;
  attachments: KnowledgeBaseAttachmentSummary[];
}

const DEFAULT_SCHEDULE = '0 9 * * *';

export const KnowledgeBaseSchedulesTab: React.FC<KnowledgeBaseSchedulesTabProps> = ({
  knowledgeBaseId,
  knowledgeBaseName,
  accessRole,
  attachments,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { state: appState } = useApp();
  const [existingJob, setExistingJob] = React.useState<AutomationJob | null>(null);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = React.useState('');
  const [schedule, setSchedule] = React.useState(DEFAULT_SCHEDULE);
  const [isBusy, setIsBusy] = React.useState(false);
  const canWrite = ['owner', 'manager', 'editor'].includes(accessRole);
  const writableAttachments = React.useMemo(
    () => attachments.filter((attachment) => attachment.mode === 'rw'),
    [attachments],
  );
  const selectedAttachment = attachments.find((attachment) => attachment.workspaceId === selectedWorkspaceId);
  const hasEligibleWorkspace = writableAttachments.length > 0;

  const loadJobs = React.useCallback(async () => {
    try {
      const items = await automationApi.listJobs();
      const match = items.find(
        (job) =>
          job.metadata?.jobType === 'knowledge_base.wiki_index'
          && job.metadata?.knowledgeBaseId === knowledgeBaseId,
      );
      setExistingJob(match ?? null);
      if (match) {
        setSelectedWorkspaceId(match.workspaceId);
        setSchedule(match.schedule || DEFAULT_SCHEDULE);
      }
    } catch (error) {
      toast({
        title: t('knowledgeBase.schedules.toasts.loadFailed.title'),
        description: error instanceof Error ? error.message : t('knowledgeBase.schedules.toasts.loadFailed.description'),
        variant: 'destructive',
      });
    }
  }, [knowledgeBaseId, t, toast]);

  React.useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  React.useEffect(() => {
    if (existingJob) {
      return;
    }
    if (!selectedWorkspaceId && writableAttachments[0]) {
      setSelectedWorkspaceId(writableAttachments[0].workspaceId);
    }
  }, [existingJob, selectedWorkspaceId, writableAttachments]);

  const saveSchedule = React.useCallback(async () => {
    if (!selectedAttachment || selectedAttachment.mode !== 'rw') {
      return;
    }
    setIsBusy(true);
    try {
      if (existingJob) {
        await automationApi.updateJob({
          id: existingJob.id,
          name: existingJob.name,
          description: existingJob.description,
          owner: existingJob.owner,
          userId: existingJob.userId,
          workspaceId: selectedAttachment.workspaceId,
          prompt: existingJob.prompt,
          status: existingJob.status,
          trigger: 'cron',
          schedule,
          tags: existingJob.tags,
          notifications: existingJob.notifications,
          metadata: {
            jobType: 'knowledge_base.wiki_index',
            knowledgeBaseId,
          },
          webhookApiKey: existingJob.webhookApiKey,
        });
        toast({ variant: 'success', title: t('knowledgeBase.schedules.toasts.updateSuccess.title') });
      } else {
        await automationApi.createJob({
          name: t('knowledgeBase.schedules.defaultName', { name: knowledgeBaseName }),
          description: t('knowledgeBase.schedules.defaultDescription', { name: knowledgeBaseName }),
          owner: appState.user.name ?? t('knowledgeBase.schedules.defaultOwner'),
          userId: appState.user.id ?? 'local-user',
          workspaceId: selectedAttachment.workspaceId,
          prompt: t('knowledgeBase.schedules.defaultPrompt'),
          status: 'active',
          trigger: 'cron',
          schedule,
          tags: ['knowledge-base', 'wiki-index'],
          notifications: { email: false, slack: false, webhook: false },
          metadata: {
            jobType: 'knowledge_base.wiki_index',
            knowledgeBaseId,
          },
        });
        toast({ variant: 'success', title: t('knowledgeBase.schedules.toasts.createSuccess.title') });
      }
      await loadJobs();
    } catch (error) {
      const failureKey = existingJob
        ? 'knowledgeBase.schedules.toasts.updateFailed'
        : 'knowledgeBase.schedules.toasts.createFailed';
      toast({
        title: t(`${failureKey}.title`),
        description: error instanceof Error ? error.message : t(`${failureKey}.description`),
        variant: 'destructive',
      });
    } finally {
      setIsBusy(false);
    }
  }, [
    appState.user.id,
    appState.user.name,
    existingJob,
    knowledgeBaseId,
    knowledgeBaseName,
    loadJobs,
    schedule,
    selectedAttachment,
    t,
    toast,
  ]);

  const sectionHeading = existingJob
    ? t('knowledgeBase.schedules.editor.updateTitle')
    : t('knowledgeBase.schedules.editor.createTitle');
  const sectionHelper = existingJob
    ? t('knowledgeBase.schedules.editor.updateHelper')
    : t('knowledgeBase.schedules.editor.createHelper');
  const saveLabel = existingJob
    ? t('knowledgeBase.schedules.actions.update')
    : t('knowledgeBase.schedules.actions.create');

  const isDisabled = !canWrite || isBusy || !hasEligibleWorkspace
    || !selectedAttachment || selectedAttachment.mode !== 'rw';

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarClock className="h-4 w-4 text-sky-600" />
                {sectionHeading}
              </CardTitle>
              <CardDescription>{sectionHelper}</CardDescription>
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              title={t('knowledgeBase.common.actions.refresh')}
              aria-label={t('knowledgeBase.common.actions.refresh')}
              onClick={() => { void loadJobs(); }}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-xs font-medium text-muted-foreground">
              {t('knowledgeBase.schedules.editor.workspace')}
              <select
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm"
                value={selectedWorkspaceId}
                disabled={!canWrite || isBusy || !hasEligibleWorkspace}
                onChange={(event) => setSelectedWorkspaceId(event.target.value)}
              >
                {attachments.length === 0 && (
                  <option value="">{t('knowledgeBase.schedules.editor.workspaceEmpty')}</option>
                )}
                {attachments.map((attachment) => (
                  <option key={attachment.id} value={attachment.workspaceId} disabled={attachment.mode !== 'rw'}>
                    {attachment.mountAlias} ({t(`knowledgeBase.common.mode.${attachment.mode}`)})
                  </option>
                ))}
              </select>
            </label>

            {hasEligibleWorkspace ? (
              <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
                {existingJob
                  ? t('knowledgeBase.schedules.editor.moveNotice')
                  : t('knowledgeBase.schedules.editor.mountNotice')}
              </p>
            ) : (
              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {t('knowledgeBase.schedules.editor.noEligibleWorkspace')}
              </p>
            )}

            <label className="block text-xs font-medium text-muted-foreground">
              {t('knowledgeBase.schedules.editor.cron')}
              <input
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 font-mono text-sm"
                value={schedule}
                disabled={!canWrite || isBusy || !hasEligibleWorkspace}
                onChange={(event) => setSchedule(event.target.value)}
              />
            </label>

            <Button
              className="h-8 gap-2"
              disabled={isDisabled}
              onClick={() => { void saveSchedule(); }}
            >
              <Save className="h-4 w-4" />
              {saveLabel}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default KnowledgeBaseSchedulesTab;
