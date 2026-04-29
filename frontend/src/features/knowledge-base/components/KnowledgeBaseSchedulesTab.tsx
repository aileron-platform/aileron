import React from 'react';
import { CalendarClock, Plus, RefreshCw } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
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

export const KnowledgeBaseSchedulesTab: React.FC<KnowledgeBaseSchedulesTabProps> = ({
  knowledgeBaseId,
  knowledgeBaseName,
  accessRole,
  attachments,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { state: appState } = useApp();
  const [jobs, setJobs] = React.useState<AutomationJob[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = React.useState('');
  const [schedule, setSchedule] = React.useState('0 9 * * *');
  const [isBusy, setIsBusy] = React.useState(false);
  const canWrite = ['owner', 'manager', 'editor'].includes(accessRole);
  const selectedAttachment = attachments.find((attachment) => attachment.workspaceId === selectedWorkspaceId);
  const writableAttachments = attachments.filter((attachment) => attachment.mode === 'rw');

  const loadJobs = React.useCallback(async () => {
    try {
      const items = await automationApi.listJobs();
      setJobs(items.filter((job) => job.metadata?.jobType === 'knowledge_base.wiki_index' && job.metadata?.knowledgeBaseId === knowledgeBaseId));
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
    if (!selectedWorkspaceId && writableAttachments[0]) {
      setSelectedWorkspaceId(writableAttachments[0].workspaceId);
    }
  }, [selectedWorkspaceId, writableAttachments]);

  const createSchedule = React.useCallback(async () => {
    if (!selectedAttachment || selectedAttachment.mode !== 'rw') {
      return;
    }
    setIsBusy(true);
    try {
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
      await loadJobs();
    } catch (error) {
      toast({
        title: t('knowledgeBase.schedules.toasts.createFailed.title'),
        description: error instanceof Error ? error.message : t('knowledgeBase.schedules.toasts.createFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsBusy(false);
    }
  }, [appState.user.id, appState.user.name, knowledgeBaseId, knowledgeBaseName, loadJobs, schedule, selectedAttachment, t, toast]);

  return (
    <div className="h-full overflow-auto bg-background">
      <div className="border-b bg-muted/20 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <CalendarClock className="h-4 w-4 text-sky-600" />
          {t('knowledgeBase.schedules.title')}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">{t('knowledgeBase.schedules.description')}</p>
      </div>

      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(280px,360px),1fr]">
        <section className="rounded-md border bg-background p-4">
          <h3 className="text-sm font-semibold">{t('knowledgeBase.schedules.create.title')}</h3>
          <div className="mt-3 space-y-3">
            <label className="block text-xs font-medium text-muted-foreground">
              {t('knowledgeBase.schedules.create.workspace')}
              <select
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm"
                value={selectedWorkspaceId}
                disabled={!canWrite || isBusy}
                onChange={(event) => setSelectedWorkspaceId(event.target.value)}
              >
                {attachments.map((attachment) => (
                  <option key={attachment.id} value={attachment.workspaceId} disabled={attachment.mode !== 'rw'}>
                    {attachment.mountAlias} ({t(`knowledgeBase.common.mode.${attachment.mode}`)})
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-medium text-muted-foreground">
              {t('knowledgeBase.schedules.create.cron')}
              <input
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 font-mono text-sm"
                value={schedule}
                disabled={!canWrite || isBusy}
                onChange={(event) => setSchedule(event.target.value)}
              />
            </label>
            <Button
              className="h-8 gap-2"
              disabled={!canWrite || isBusy || !selectedAttachment || selectedAttachment.mode !== 'rw'}
              onClick={() => { void createSchedule(); }}
            >
              <Plus className="h-4 w-4" />
              {t('knowledgeBase.schedules.actions.create')}
            </Button>
          </div>
        </section>

        <section className="rounded-md border bg-background p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{t('knowledgeBase.schedules.list.title')}</h3>
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
          </div>
          <div className="space-y-2">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-md border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{job.name}</span>
                  <Badge variant="outline">{t(`knowledgeBase.schedules.status.${job.status}`)}</Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{job.schedule}</div>
              </div>
            ))}
            {jobs.length === 0 && (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                {t('knowledgeBase.schedules.list.empty')}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default KnowledgeBaseSchedulesTab;
