/**
 * AutomationJobCreateDialog - Create automation task dialog
 */

import React, { useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { ApiError } from '@/shared/api/apiClient';

const logger = createLogger('AutomationJobCreateDialog');
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
import { useAutomation } from '../../providers/AutomationProvider';
import type { JobCreateInput } from '../../model/automationTypes';
import { SlashCommandPickerDialog } from '@/shared/components/slash-command-picker';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { AlertCircle, Bot, CalendarClock, Clock, FileText, Send, Slash } from 'lucide-react';
import { TRIGGER_OPTIONS } from './jobFormOptions';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationWorkspaceApi } from '../../api/automationWorkspaceApi';
import type { AutomationWorkspaceSummary } from '../../model/automationTypes';
import { ScheduleBuilder } from './ScheduleBuilder';
import type { ScheduleBuilderValidation } from './scheduleBuilderModel';
import { AutomationAgentSelector } from './AutomationAgentSelector';
import {
  AutomationFormSectionHeading as FormSectionHeading,
  automationFormSectionClassName,
} from './AutomationFormSection';
import { AutomationWorktreeSetting } from './AutomationWorktreeSetting';

const generateWebhookApiKey = (): string => {
  return (crypto.randomUUID() as unknown as {
    replaceAll(searchValue: string, replaceValue: string): string;
  }).replaceAll('-', '');
};

const EXPECTED_CREATE_ERROR_CODES = new Set([
  'workspace_git_repository_required',
  'workspace_git_initial_commit_required',
  'worktree_conflict',
  'worktree_operation_in_progress',
  'worktree_locked',
  'worktree_storage_limit',
  'automation_worktree_unavailable',
  'automation_runtime_unavailable',
]);

const buildDefaultForm = (): JobCreateInput => ({
  name: '',
  description: '',
  workspaceId: '',
  prompt: '',
  trigger: 'cron',
  schedule: '0 9 * * *',
  exact: false,
  deliveryWebhookUrl: undefined,
  failureDestination: undefined,
});

export const AutomationJobCreateDialog: React.FC = () => {
  const { t } = useI18n();
  const { state, closeCreateDialog, createTask } = useAutomation();

  const defaultForm = useMemo(() => buildDefaultForm(), []);

  const [form, setForm] = useState<JobCreateInput>(defaultForm);
  const [slashDialogOpen, setSlashDialogOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<AutomationWorkspaceSummary[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);
  const [commandsError, setCommandsError] = useState<string | null>(null);
  const [scheduleValidation, setScheduleValidation] = useState<ScheduleBuilderValidation>({ isValid: true });
  const [createErrorCode, setCreateErrorCode] = useState<string | null>(null);

  useEffect(() => {
    if (state.isCreateDialogOpen) {
      setForm(defaultForm);
      setScheduleValidation({ isValid: true });
      setCreateErrorCode(null);
    }
  }, [defaultForm, state.isCreateDialogOpen]);

  useEffect(() => {
    if (!state.isCreateDialogOpen) {
      setWorkspaces([]);
      setWorkspacesLoading(false);
      setWorkspaceError(null);
      setCommands([]);
      setCommandsLoading(false);
      setCommandsError(null);
      return;
    }

    const controller = new AbortController();
    setWorkspacesLoading(true);
    setWorkspaceError(null);

    void (async () => {
      try {
        const items = await automationWorkspaceApi.list(controller.signal);
        if (controller.signal.aborted) {
          return;
        }

        setWorkspaces(items);
        setForm(prev => {
          const nextWorkspaceId =
            prev.workspaceId && items.some(item => item.id === prev.workspaceId)
              ? prev.workspaceId
              : items[0]?.id ?? '';
          return { ...prev, workspaceId: nextWorkspaceId };
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        logger.error('Failed to load automation workspaces', { error });
        setWorkspaces([]);
        setWorkspaceError(error instanceof Error ? error.message : 'unknown');
        setForm(prev => ({ ...prev, workspaceId: '' }));
      } finally {
        if (!controller.signal.aborted) {
          setWorkspacesLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [state.isCreateDialogOpen]);

  useEffect(() => {
    if (!state.isCreateDialogOpen || !form.workspaceId) {
      setCommands([]);
      setCommandsLoading(false);
      setCommandsError(null);
      return;
    }

    const controller = new AbortController();
    setCommandsLoading(true);
    setCommandsError(null);

    void (async () => {
      try {
        const items = await automationWorkspaceApi.listSlashCommands(form.workspaceId, controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        setCommands(items);
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        logger.error('Failed to load automation slash commands', { error });
        setCommands([]);
        setCommandsError(error instanceof Error ? error.message : 'unknown');
      } finally {
        if (!controller.signal.aborted) {
          setCommandsLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [form.workspaceId, state.isCreateDialogOpen]);

  useEffect(() => {
    if (!state.isCreateDialogOpen || workspaces.length === 0) {
      return;
    }
    setForm(prev => {
      if (prev.workspaceId && workspaces.some(item => item.id === prev.workspaceId)) {
        return prev;
      }
      return { ...prev, workspaceId: workspaces[0].id };
    });
  }, [state.isCreateDialogOpen, workspaces]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.workspaceId || !form.name.trim() || !form.prompt.trim()) return;
    if (!form.agenticTool || !form.model) return;
    if (['cron', 'at', 'every'].includes(form.trigger) && !form.schedule.trim()) return;
    if (form.trigger === 'cron' && !scheduleValidation.isValid) return;
    setCreateErrorCode(null);
    try {
      await createTask(form);
    } catch (error) {
      const errorCode = error instanceof ApiError && error.errorCode
        && EXPECTED_CREATE_ERROR_CODES.has(error.errorCode)
        ? error.errorCode
        : 'generic';
      if (errorCode === 'generic') {
        logger.error('Failed to create task', { error });
      }
      setCreateErrorCode(errorCode);
    }
  };

  const disabled =
    state.creating ||
    !form.workspaceId ||
    !form.name.trim() ||
    !form.prompt.trim() ||
    !form.agenticTool ||
    !form.model ||
    (['cron', 'at', 'every'].includes(form.trigger) && !form.schedule.trim()) ||
    (form.trigger === 'cron' && !scheduleValidation.isValid);

  const slashCommandButtonDisabled = !form.workspaceId || commandsLoading || (!commandsError && commands.length === 0);

  return (
    <Dialog open={state.isCreateDialogOpen} onOpenChange={(open) => (!open ? closeCreateDialog() : undefined)}>
      <DialogContent className="flex h-[min(880px,92vh)] w-[min(960px,calc(100vw-2rem))] max-w-none flex-col overflow-hidden border-border/60 p-0">
        <form className="flex flex-col min-h-0 flex-1" onSubmit={handleSubmit}>
          <DialogHeader className="border-b border-border/60 px-6 py-5">
            <div className="space-y-1">
              <DialogHeading icon={Clock} className="text-base font-semibold">
                {t('automation.create.title')}
              </DialogHeading>
              <DialogDescription className="text-xs">
                {t('automation.create.subtitle')}
              </DialogDescription>
            </div>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-muted/10 px-6 py-6">
            <section className={automationFormSectionClassName}>
              <FormSectionHeading
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
                    onChange={(event) => setForm(prev => ({ ...prev, name: event.target.value }))}
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
                    onValueChange={(value) => setForm(prev => ({ ...prev, workspaceId: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('automation.form.fields.workspace.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {workspacesLoading ? (
                        <div className="px-3 py-2 text-sm text-muted-foreground">
                          {t('automation.form.fields.workspace.loading')}
                        </div>
                      ) : workspaceError ? (
                        <div className="px-3 py-2 text-sm text-destructive">
                          {t('automation.form.fields.workspace.error')}
                        </div>
                      ) : workspaces.length === 0 ? (
                        <div className="px-3 py-2 text-sm text-muted-foreground">
                          {t('automation.form.fields.workspace.empty')}
                        </div>
                      ) : (
                        workspaces.map(option => (
                          <SelectItem key={option.id} value={option.id}>
                            <div className="flex items-center gap-2">
                              <span>{option.name}</span>
                              <Badge variant="secondary" className="text-[10px] uppercase">
                                {option.accessSource === 'shared'
                                  ? t('automation.form.fields.workspace.accessSource.shared')
                                  : t('automation.form.fields.workspace.accessSource.owned')}
                              </Badge>
                            </div>
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  {workspaceError && (
                    <p className="text-xs text-destructive">
                      {t('automation.form.fields.workspace.error')}
                    </p>
                  )}
                  {!workspaceError && !workspacesLoading && workspaces.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      {t('automation.form.fields.workspace.empty')}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm">{t('automation.form.fields.description.label')}</Label>
                <Textarea
                  value={form.description}
                  onChange={(event) => setForm(prev => ({ ...prev, description: event.target.value }))}
                  placeholder={t('automation.form.fields.description.placeholder')}
                  rows={3}
                />
              </div>

              <AutomationWorktreeSetting />

              <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">
                      {t('automation.form.fields.prompt.label')}
                      <span className="ml-1 text-destructive">*</span>
                    </Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => setSlashDialogOpen(true)}
                      disabled={slashCommandButtonDisabled}
                      title={
                        !form.workspaceId
                          ? t('automation.form.fields.workspace.placeholder')
                          : commandsLoading
                          ? t('automation.form.fields.prompt.commandsLoading')
                          : commandsError
                          ? t('automation.form.fields.prompt.commandsError')
                          : commands.length === 0
                          ? t('automation.form.fields.prompt.commandsEmpty')
                          : undefined
                      }
                    >
                      <Slash className="h-4 w-4" /> {t('automation.form.fields.prompt.selectCommand')}
                    </Button>
                  </div>
                  <Textarea
                    value={form.prompt}
                  onChange={(event) => setForm(prev => ({ ...prev, prompt: event.target.value }))}
                  placeholder={t('automation.form.fields.prompt.placeholder')}
                    rows={4}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.prompt.helper')}
                  </p>
                  {commandsLoading && (
                    <p className="text-xs text-muted-foreground">
                      {t('automation.form.fields.prompt.commandsLoading')}
                    </p>
                  )}
                  {!commandsLoading && !commandsError &&
                    state.isCreateDialogOpen &&
                    form.workspaceId &&
                    commands.length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        {t('automation.form.fields.prompt.commandsEmpty')}
                      </p>
                    )}
                  {commandsError && (
                    <p className="text-xs text-destructive">
                      {t('automation.form.fields.prompt.commandsError')}
                    </p>
                  )}
                </div>
            </section>

            <section className={automationFormSectionClassName}>
              <FormSectionHeading
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
                onChange={(selection) => setForm(prev => ({
                  ...prev,
                  agenticTool: selection.agenticTool,
                  model: selection.model,
                  agentConfig: { mode: selection.mode },
                }))}
              />
            </section>

            <section className={automationFormSectionClassName}>
              <FormSectionHeading
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
                      const newTrigger = value as JobCreateInput['trigger'];
                      setForm(prev => {
                        const updated = { ...prev, trigger: newTrigger };
                        // Generate the API key when switching to webhook.
                        if (newTrigger === 'webhook' && !prev.webhookApiKey) {
                          updated.webhookApiKey = generateWebhookApiKey();
                        }
                        // Manual triggers do not need a schedule.
                        if (newTrigger === 'manual' || newTrigger === 'webhook') {
                          updated.schedule = '';
                        }
                        // Restore a default schedule when switching back to cron.
                        if (newTrigger === 'cron' && prev.trigger !== 'cron') {
                          updated.schedule = '0 9 * * *';
                        }
                        if (newTrigger === 'at' && prev.trigger !== 'at') {
                          updated.schedule = '20m';
                        }
                        if (newTrigger === 'every' && prev.trigger !== 'every') {
                          updated.schedule = '30m';
                        }
                        return updated;
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('automation.form.fields.trigger.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {TRIGGER_OPTIONS.map(option => (
                        <SelectItem key={option.value} value={option.value}>
                          {t(option.labelKey)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {form.trigger === 'cron' && (
                <div className="space-y-2">
                  <Label className="text-sm">
                    {t('automation.form.fields.schedule.label')}
                    <span className="ml-1 text-destructive">*</span>
                  </Label>
                  <ScheduleBuilder
                    value={form.schedule}
                    onChange={(schedule) => setForm(prev => ({ ...prev, schedule }))}
                    onValidationChange={setScheduleValidation}
                  />
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {t('automation.form.fields.schedule.timezoneHelper')}
                  </p>
                </div>
              )}

              {form.trigger === 'at' && (
                <div className="space-y-2">
                  <Label className="text-sm">
                    {t('automation.form.fields.atSchedule.label')}
                    <span className="ml-1 text-destructive">*</span>
                  </Label>
                  <Input
                    value={form.schedule}
                    onChange={(event) => setForm(prev => ({ ...prev, schedule: event.target.value }))}
                    placeholder={t('automation.form.fields.atSchedule.placeholder')}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.atSchedule.help')}
                  </p>
                </div>
              )}

              {form.trigger === 'every' && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-sm">
                      {t('automation.form.fields.everyInterval.label')}
                      <span className="ml-1 text-destructive">*</span>
                    </Label>
                    <Input
                      value={form.schedule}
                      onChange={(event) => setForm(prev => ({ ...prev, schedule: event.target.value }))}
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
                      onCheckedChange={(checked) => setForm(prev => ({ ...prev, exact: checked }))}
                      aria-label={t('automation.form.fields.exact.label')}
                    />
                  </div>
                </div>
              )}

              {form.trigger === 'cron' && (
                <div className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2">
                  <div className="space-y-0.5">
                    <Label className="text-sm">{t('automation.form.fields.exact.label')}</Label>
                    <p className="text-xs text-muted-foreground">{t('automation.form.fields.exact.help')}</p>
                  </div>
                  <Switch
                    checked={Boolean(form.exact)}
                    onCheckedChange={(checked) => setForm(prev => ({ ...prev, exact: checked }))}
                    aria-label={t('automation.form.fields.exact.label')}
                  />
                </div>
              )}

              {form.trigger === 'webhook' && (
                <div className="space-y-2">
                  <Label className="text-sm">{t('automation.form.fields.webhookApiKey.label')}</Label>
                  <div className="flex gap-2">
                    <Input
                      value={form.webhookApiKey || ''}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setForm(prev => ({ ...prev, webhookApiKey: generateWebhookApiKey() }))}
                    >
                      {t('automation.form.fields.webhookApiKey.regenerate')}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.webhookApiKey.helper')}
                  </p>
                  <p className="rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                    {t('automation.form.fields.webhookTriggerUrl.pendingCreateHelper')}
                  </p>
                </div>
              )}
            </section>

            <section className={automationFormSectionClassName}>
              <FormSectionHeading
                icon={Send}
                title={t('automation.form.sections.delivery.title')}
                description={t('automation.form.sections.delivery.description')}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-sm">{t('automation.form.fields.deliveryWebhookUrl.label')}</Label>
                  <Input
                    value={form.deliveryWebhookUrl ?? ''}
                    onChange={(event) => setForm(prev => ({
                      ...prev,
                      deliveryWebhookUrl: event.target.value,
                    }))}
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
                    onChange={(event) => setForm(prev => ({
                      ...prev,
                      failureDestination: event.target.value,
                    }))}
                    placeholder={t('automation.form.fields.failureDestination.placeholder')}
                  />
                </div>
              </div>
            </section>

          </div>

          {createErrorCode && (
            <div className="flex flex-shrink-0 items-start gap-2 border-t border-destructive/20 bg-destructive/5 px-6 py-3 text-sm text-destructive" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
              <span>{t(`automation.create.errors.${createErrorCode}`)}</span>
            </div>
          )}

          <DialogFooter className="flex-shrink-0 border-t border-border/60 px-6 py-4">
            <Button type="button" variant="outline" onClick={closeCreateDialog} disabled={state.creating}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={disabled} className="gap-2">
              {state.creating ? t('automation.create.actions.creating') : t('automation.create.actions.submit')}
            </Button>
          </DialogFooter>
        </form>

        <SlashCommandPickerDialog
          open={slashDialogOpen}
          onOpenChange={setSlashDialogOpen}
          commands={commands}
          onSelect={(command: SlashCommandItem) => {
            setForm(prev => ({ ...prev, prompt: `/${command.displayName}` }));
          }}
          labels={{
            title: t('automation.slashDialog.title'),
            description: t('automation.slashDialog.description'),
            searchPlaceholder: t('automation.slashDialog.searchPlaceholder'),
            empty: t('automation.slashDialog.empty'),
            scope: {
              all: t('automation.slashDialog.scope.all'),
              project: t('automation.slashDialog.scope.project'),
              user: t('automation.slashDialog.scope.user'),
            },
          }}
        />
      </DialogContent>
    </Dialog>
  );
};
