import React, { useCallback, useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Switch } from '@/shared/components/ui/switch';
import { Textarea } from '@/shared/components/ui/textarea';
import { Label } from '@/shared/components/ui/label';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Badge } from '@/shared/components/ui/badge';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import type { AutomationJob, JobStatus, JobTrigger, JobUpdateInput } from '../../model/automationTypes';
import type { PromptInvocationItem } from '@/shared/types/promptInvocations';
import { toPromptInvocationTool } from '@/shared/types/promptInvocations';
import { PromptInvocationPickerDialog } from '@/shared/components/prompt-invocation-picker';
import { Bot, CalendarClock, Clock, Copy, FileText, Send, Slash } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import { ScheduleBuilder } from './ScheduleBuilder';
import type { ScheduleBuilderValidation } from './scheduleBuilderModel';
import { STATUS_OPTIONS, TRIGGER_OPTIONS } from './jobFormOptions';
import { AutomationAgentSelector } from './AutomationAgentSelector';
import {
  AutomationFormSectionHeading,
  automationFormSectionClassName,
} from './AutomationFormSection';
import { AutomationWorktreeSetting } from './AutomationWorktreeSetting';
import type { AutomationWorkspaceSummary } from '../../model/automationTypes';
import { automationWorkspaceApi } from '../../api/automationWorkspaceApi';

const logger = createLogger('AutomationJobEditDialog');

interface AutomationJobEditDialogProps {
  isOpen: boolean;
  task: AutomationJob | null;
  loading: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: (payload: JobUpdateInput) => Promise<void>;
  workspaces: AutomationWorkspaceSummary[];
}

const isJobTrigger = (value: string): value is JobTrigger =>
  TRIGGER_OPTIONS.some(option => option.value === value);

const isJobStatus = (value: string): value is 'active' | 'paused' =>
  STATUS_OPTIONS.some(option => option.value === value);

type JobUpdateForm = JobUpdateInput & { workspaceId: string };

const generateWebhookApiKey = (): string => (crypto.randomUUID() as unknown as {
  replaceAll(searchValue: string, replaceValue: string): string;
}).replaceAll('-', '');

const mapTaskToForm = (task: AutomationJob): JobUpdateForm => ({
  id: task.id,
  name: task.name,
  description: task.description,
  workspaceId: task.workspaceId,
  prompt: task.prompt,
  status: task.status === 'completed' ? undefined : task.status,
  trigger: task.trigger,
  schedule: task.schedule,
  exact: task.exact ?? false,
  agenticTool: task.agenticTool,
  model: task.model,
  agentConfig: { mode: task.agentConfig.mode },
  deliveryWebhookUrl: task.deliveryWebhookUrl,
  failureDestination: task.failureDestination,
});

export const AutomationJobEditDialog: React.FC<AutomationJobEditDialogProps> = ({
  isOpen,
  task,
  loading,
  saving,
  onClose,
  onSave,
  workspaces,
}) => {
  const [form, setForm] = useState<JobUpdateForm | null>(null);
  const [promptInvocationDialogOpen, setPromptInvocationDialogOpen] = useState(false);
  const [scheduleValidation, setScheduleValidation] = useState<ScheduleBuilderValidation>({ isValid: true });
  const [promptInvocationProvenance, setPromptInvocationProvenance] = useState<{
    agenticTool: string;
    item: PromptInvocationItem;
  } | null>(null);
  const [promptCompatibilityWarning, setPromptCompatibilityWarning] = useState(false);
  const { t } = useI18n();
  const { toast } = useToast();

  const webhookTriggerUrl = task
    ? new URL(apiClient.buildUrl(`/automation/webhook/${task.id}`), window.location.origin).toString()
    : '';

  const handleCopyWebhookTriggerUrl = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API is unavailable');
      }
      await navigator.clipboard.writeText(webhookTriggerUrl);
      toast({
        title: t('automation.form.fields.webhookTriggerUrl.copySuccessTitle'),
        description: t('automation.form.fields.webhookTriggerUrl.copySuccessDescription'),
      });
    } catch (error) {
      logger.error('Failed to copy webhook trigger URL', { error });
      toast({
        title: t('automation.form.fields.webhookTriggerUrl.copyFailedTitle'),
        description: t('automation.form.fields.webhookTriggerUrl.copyFailedDescription'),
        variant: 'destructive',
      });
    }
  };

  useEffect(() => {
    if (isOpen && task) {
      setForm(mapTaskToForm(task));
      setScheduleValidation({ isValid: true });
      setPromptInvocationProvenance(null);
      setPromptCompatibilityWarning(false);
    }
    if (!isOpen) {
      setForm(null);
      setScheduleValidation({ isValid: true });
      setPromptInvocationProvenance(null);
      setPromptCompatibilityWarning(false);
    }
  }, [isOpen, task]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form) return;
    if (!form.workspaceId || !form.name.trim() || !form.prompt.trim()) return;
    if (!form.agenticTool || !form.model) return;
    if (['cron', 'at', 'every'].includes(form.trigger) && !form.schedule.trim()) return;
    if (form.trigger === 'cron' && !scheduleValidation.isValid) return;
    try {
      const { workspaceId: _workspaceId, ...payload } = form;
      await onSave(payload);
    } catch (error) {
      logger.error('Failed to update automation task', { error });
    }
  };

  const disabled =
    !form ||
    saving ||
    !form.workspaceId ||
    !form.name.trim() ||
    !form.agenticTool ||
    !form.model ||
    (['cron', 'at', 'every'].includes(form.trigger) && !form.schedule.trim()) ||
    (form.trigger === 'cron' && !scheduleValidation.isValid) ||
    !form.prompt.trim();

  const selectedWorkspace = workspaces.find(item => item.id === form?.workspaceId);
  const promptInvocationButtonDisabled = !selectedWorkspace?.runtimeUrl || !form?.agenticTool;
  const loadPromptInvocationCatalog = useCallback(() => {
    if (!selectedWorkspace?.runtimeUrl || !form?.workspaceId || !form.agenticTool) {
      throw new Error('Workspace Runtime and Agentic Tool are required');
    }
    return automationWorkspaceApi.listPromptInvocations(
      selectedWorkspace.runtimeUrl,
      form.workspaceId,
      toPromptInvocationTool(form.agenticTool),
    );
  }, [form?.agenticTool, form?.workspaceId, selectedWorkspace?.runtimeUrl]);

  const renderContent = () => {
    if (loading || !form) {
      return (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      );
    }

    return (
      <form className="flex flex-col min-h-0 flex-1" onSubmit={handleSubmit}>
        <DialogHeader className="border-b border-border/60 px-6 py-5">
          <div className="space-y-1">
            <DialogHeading icon={Clock} className="text-base font-semibold">
              {t('automation.edit.title')}
            </DialogHeading>
            <DialogDescription className="text-xs">{t('automation.edit.subtitle')}</DialogDescription>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-muted/10 px-6 py-6">
          <section className={automationFormSectionClassName}>
            <AutomationFormSectionHeading
              icon={FileText}
              title={t('automation.form.sections.basics.title')}
              description={t('automation.form.sections.basics.description')}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-sm">
                  {t('automation.form.fields.name.label')}
                  <span className="ml-1 text-destructive">*</span>
                </Label>
                <Input
                  value={form.name}
                  onChange={(event) => setForm(prev => prev ? { ...prev, name: event.target.value } : prev)}
                  placeholder={t('automation.form.fields.name.placeholder')}
                  maxLength={80}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">
                  {t('automation.form.fields.workspace.label')}
                  <span className="ml-1 text-destructive">*</span>
                </Label>
                <Select
                  value={form.workspaceId}
                  disabled
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('automation.form.fields.workspace.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {workspaces.map(ws => (
                      <SelectItem key={ws.id} value={ws.id}>
                        <div className="flex items-center gap-2">
                          <span>{ws.name}</span>
                          <Badge variant="secondary" className="text-[10px] uppercase">
                            {ws.accessSource === 'shared'
                              ? t('automation.form.fields.workspace.accessSource.shared')
                              : t('automation.form.fields.workspace.accessSource.owned')}
                          </Badge>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">{t('automation.form.fields.description.label')}</Label>
              <Textarea
                value={form.description}
                onChange={(event) => setForm(prev => prev ? { ...prev, description: event.target.value } : prev)}
                placeholder={t('automation.form.fields.description.placeholder')}
                rows={2}
                maxLength={200}
              />
            </div>

            <AutomationWorktreeSetting />
          </section>

          <section className={automationFormSectionClassName}>
            <AutomationFormSectionHeading
              icon={Bot}
              title={t('automation.form.sections.agent.title')}
              description={t('automation.form.sections.agent.description')}
            />
            <AutomationAgentSelector
              workspaceId={form.workspaceId}
              value={{
                agenticTool: form.agenticTool,
                model: form.model,
                mode: form.agentConfig?.mode,
              }}
              onChange={(selection) => setForm(prev => {
                if (!prev) return prev;
                const toolChanged = Boolean(
                  prev.agenticTool
                  && selection.agenticTool
                  && prev.agenticTool !== selection.agenticTool,
                );
                if (toolChanged) {
                  setPromptCompatibilityWarning(Boolean(
                    promptInvocationProvenance
                    && promptInvocationProvenance.agenticTool !== selection.agenticTool
                    && prev.prompt === promptInvocationProvenance.item.invocation,
                  ));
                  setPromptInvocationProvenance(null);
                }
                return {
                  ...prev,
                  agenticTool: selection.agenticTool,
                  model: selection.model,
                  agentConfig: { mode: selection.mode },
                };
              })}
            />
          </section>

          <section className={automationFormSectionClassName}>
            <AutomationFormSectionHeading
              icon={FileText}
              title={t('automation.form.sections.instructions.title')}
              description={t('automation.form.sections.instructions.description')}
            />
            <div className="space-y-2">
              <Label className="text-sm">
                {t('automation.form.fields.prompt.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <div className="flex gap-2">
                <Textarea
                  value={form.prompt}
                  onChange={(event) => {
                    setForm(prev => prev ? { ...prev, prompt: event.target.value } : prev);
                    setPromptInvocationProvenance(null);
                    setPromptCompatibilityWarning(false);
                  }}
                  placeholder={t('automation.form.fields.prompt.placeholder')}
                  rows={3}
                  required
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => setPromptInvocationDialogOpen(true)}
                  disabled={promptInvocationButtonDisabled}
                  aria-label={t('automation.form.fields.prompt.selectInvocation')}
                  className="flex-shrink-0"
                >
                  <Slash className="h-4 w-4" />
                </Button>
              </div>
              {promptCompatibilityWarning && (
                <p role="alert" className="text-xs text-warning-foreground">
                  {t('automation.form.fields.prompt.toolCompatibilityWarning')}
                </p>
              )}
            </div>
          </section>

          <section className={automationFormSectionClassName}>
            <AutomationFormSectionHeading
              icon={CalendarClock}
              title={t('automation.form.sections.schedule.title')}
              description={t('automation.form.sections.schedule.description')}
            />
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label className="text-sm">{t('automation.form.fields.trigger.label')}</Label>
                <Select
                  value={form.trigger}
                  onValueChange={(value) => {
                    if (isJobTrigger(value)) {
                      setForm(prev => {
                        if (!prev) return prev;
                        const updated = { ...prev, trigger: value };
                        if (value === 'manual' || value === 'webhook') {
                          updated.schedule = '';
                        }
                        if (value === 'cron' && prev.trigger !== 'cron') {
                          updated.schedule = '0 9 * * *';
                        }
                        if (value === 'at' && prev.trigger !== 'at') {
                          updated.schedule = '20m';
                        }
                        if (value === 'every' && prev.trigger !== 'every') {
                          updated.schedule = '30m';
                        }
                        return updated;
                      });
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TRIGGER_OPTIONS.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {t(opt.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {form && form.trigger === 'cron' && (
                <div className="space-y-2 col-span-2">
                  <Label className="text-sm">
                    {t('automation.form.fields.schedule.label')}
                    <span className="ml-1 text-destructive">*</span>
                  </Label>
                  <ScheduleBuilder
                    value={form.schedule}
                    onChange={(schedule) => setForm(prev => prev ? { ...prev, schedule } : prev)}
                    onValidationChange={setScheduleValidation}
                  />
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {t('automation.form.fields.schedule.timezoneHelper')}
                  </p>
                </div>
              )}

              {form && form.trigger === 'at' && (
                <div className="space-y-2 col-span-2">
                  <Label className="text-sm">
                    {t('automation.form.fields.atSchedule.label')}
                    <span className="ml-1 text-destructive">*</span>
                  </Label>
                  <Input
                    value={form.schedule}
                    onChange={(event) => setForm(prev => prev ? { ...prev, schedule: event.target.value } : prev)}
                    placeholder={t('automation.form.fields.atSchedule.placeholder')}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.atSchedule.help')}
                  </p>
                </div>
              )}

              {form && form.trigger === 'every' && (
                <div className="space-y-3 col-span-2">
                  <div className="space-y-2">
                    <Label className="text-sm">
                      {t('automation.form.fields.everyInterval.label')}
                      <span className="ml-1 text-destructive">*</span>
                    </Label>
                    <Input
                      value={form.schedule}
                      onChange={(event) => setForm(prev => prev ? { ...prev, schedule: event.target.value } : prev)}
                      placeholder={t('automation.form.fields.everyInterval.placeholder')}
                      required
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('automation.form.fields.everyInterval.help')}
                    </p>
                  </div>
                  <div className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2">
                    <div className="space-y-0.5">
                      <Label className="text-sm">{t('automation.form.fields.exact.label')}</Label>
                      <p className="text-xs text-muted-foreground">{t('automation.form.fields.exact.help')}</p>
                    </div>
                    <Switch
                      checked={Boolean(form.exact)}
                      onCheckedChange={(checked) => setForm(prev => prev ? { ...prev, exact: checked } : prev)}
                      aria-label={t('automation.form.fields.exact.label')}
                    />
                  </div>
                </div>
              )}

              {form && form.trigger === 'cron' && (
                <div className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2 col-span-2">
                  <div className="space-y-0.5">
                    <Label className="text-sm">{t('automation.form.fields.exact.label')}</Label>
                    <p className="text-xs text-muted-foreground">{t('automation.form.fields.exact.help')}</p>
                  </div>
                  <Switch
                    checked={Boolean(form.exact)}
                    onCheckedChange={(checked) => setForm(prev => prev ? { ...prev, exact: checked } : prev)}
                    aria-label={t('automation.form.fields.exact.label')}
                  />
                </div>
              )}

              {form && form.trigger === 'webhook' && (
                <div className="space-y-2 col-span-2">
                  <Label className="text-sm">{t('automation.form.fields.webhookApiKey.label')}</Label>
                  {form.webhookApiKey ? (
                    <Input
                      value={form.webhookApiKey}
                      readOnly
                      className="font-mono text-sm"
                    />
                  ) : (
                    <p className="rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                      {task?.webhookConfigured
                        ? t('automation.form.fields.webhookApiKey.configured')
                        : t('automation.form.fields.webhookApiKey.notConfigured')}
                    </p>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setForm(prev => prev ? {
                      ...prev,
                      webhookApiKey: generateWebhookApiKey(),
                    } : prev)}
                  >
                    {t('automation.form.fields.webhookApiKey.regenerate')}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.webhookApiKey.helper')}
                  </p>

                  <Label className="text-sm">{t('automation.form.fields.webhookTriggerUrl.label')}</Label>
                  <div className="flex gap-2">
                    <Input
                      value={webhookTriggerUrl}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCopyWebhookTriggerUrl}
                    >
                      <Copy className="mr-2 h-3 w-3" />
                      {t('automation.form.fields.webhookTriggerUrl.copy')}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.webhookTriggerUrl.helper')}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label className="text-sm">{t('automation.form.fields.status.label')}</Label>
              <Select
                value={form.status}
                onValueChange={(value) => {
                  if (isJobStatus(value)) {
                    setForm(prev => prev ? { ...prev, status: value } : prev);
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </section>

          <section className={automationFormSectionClassName}>
            <AutomationFormSectionHeading
              icon={Send}
              title={t('automation.form.sections.delivery.title')}
              description={t('automation.form.sections.delivery.description')}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-sm">{t('automation.form.fields.deliveryWebhookUrl.label')}</Label>
                <Input
                  value={form.deliveryWebhookUrl ?? ''}
                  onChange={(event) => setForm(prev => prev ? {
                    ...prev,
                    deliveryWebhookUrl: event.target.value,
                  } : prev)}
                  placeholder={t('automation.form.fields.deliveryWebhookUrl.placeholder')}
                />
                <p className="text-xs text-muted-foreground">
                  {t('automation.form.fields.deliveryWebhookUrl.help')}
                </p>
              </div>
              <div className="space-y-2">
                <Label className="text-sm">{t('automation.form.fields.failureDestination.label')}</Label>
                <Input
                  value={form.failureDestination ?? ''}
                  onChange={(event) => setForm(prev => prev ? {
                    ...prev,
                    failureDestination: event.target.value,
                  } : prev)}
                  placeholder={t('automation.form.fields.failureDestination.placeholder')}
                />
              </div>
            </div>
          </section>

        </div>

        <DialogFooter className="flex-shrink-0 border-t border-border/60 px-6 py-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={disabled} className="gap-2">
            {saving ? t('automation.edit.actions.saving') : t('automation.edit.actions.submit')}
          </Button>
        </DialogFooter>
      </form>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent className="flex h-[min(880px,92vh)] w-[min(960px,calc(100vw-2rem))] max-w-none flex-col overflow-hidden border-border/60 p-0">
        {renderContent()}

        <PromptInvocationPickerDialog
          open={promptInvocationDialogOpen}
          onOpenChange={setPromptInvocationDialogOpen}
          catalogKey={`${form?.workspaceId ?? ''}:${form?.agenticTool ?? ''}`}
          loadCatalog={loadPromptInvocationCatalog}
          onSelect={(item) => {
            setForm(prev => prev ? { ...prev, prompt: item.invocation } : prev);
            setPromptInvocationProvenance({
              agenticTool: form?.agenticTool ?? '',
              item,
            });
            setPromptCompatibilityWarning(false);
          }}
          labels={{
            title: t('automation.promptInvocationDialog.title'),
            description: t('automation.promptInvocationDialog.description'),
            searchPlaceholder: t('automation.promptInvocationDialog.searchPlaceholder'),
            empty: t('automation.promptInvocationDialog.empty'),
          }}
        />
      </DialogContent>
    </Dialog>
  );
};
