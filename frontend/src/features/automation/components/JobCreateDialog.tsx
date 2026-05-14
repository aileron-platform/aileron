/**
 * JobCreateDialog - Create scheduler task dialog
 */

import React, { useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('JobCreateDialog');
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
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
import { useAutomation } from '../providers/AutomationProvider';
import { JobCreateInput } from '../types';
import { SlashCommandPickerDialog } from '@/shared/components/slash-command-picker';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { Clock, Plus, Slash, Tag as TagIcon, X } from 'lucide-react';
import { STATUS_OPTIONS, TRIGGER_OPTIONS } from './jobFormOptions';
import { useI18n } from '@/shared/hooks/useI18n';
import { useApp } from '@/app/providers/AppProvider';
import { workspaceApi, type WorkspaceSummary } from '../services/workspaceApi';
import { ScheduleBuilder } from './ScheduleBuilder';
import type { ScheduleBuilderValidation } from './scheduleBuilderUtils';

const FALLBACK_USER_ID = 'f57c7e4d-4f51-45a2-b6a6-4d2fe79a4d21';

const generateWebhookApiKey = (): string => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  const length = 32;
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
};

const buildDefaultForm = (
  userId: string,
  owner: string,
): JobCreateInput => ({
  name: '',
  description: '',
  owner,
  userId,
  workspaceId: '',
  prompt: '',
  status: 'active',
  trigger: 'cron',
  schedule: '0 9 * * *',
  tags: ['automation'],
  notifications: {
    email: true,
    slack: false,
    webhook: false,
  },
  metadata: {},
});

export const JobCreateDialog: React.FC = () => {
  const { t } = useI18n();
  const { state: appState } = useApp();
  const { state, closeCreateDialog, createTask } = useAutomation();

  const currentUserId = appState.user.id ?? FALLBACK_USER_ID;
  const currentOwner = appState.user.name ?? t('common.messages.fallbackOwnerName');

  const defaultForm = useMemo(
    () => buildDefaultForm(currentUserId, currentOwner),
    [currentOwner, currentUserId],
  );

  const [form, setForm] = useState<JobCreateInput>(defaultForm);
  const [tagInput, setTagInput] = useState('');
  const [slashDialogOpen, setSlashDialogOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);
  const [commandsError, setCommandsError] = useState<string | null>(null);
  const [scheduleValidation, setScheduleValidation] = useState<ScheduleBuilderValidation>({ isValid: true });

  useEffect(() => {
    if (state.isCreateDialogOpen) {
      setForm(defaultForm);
      setTagInput('');
      setScheduleValidation({ isValid: true });
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
        const items = await workspaceApi.list(controller.signal);
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
        logger.error('Failed to load scheduler workspaces', { error });
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
        const items = await workspaceApi.listSlashCommands(form.workspaceId, controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        setCommands(items);
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        logger.error('Failed to load scheduler slash commands', { error });
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

  const handleAddTag = () => {
    const value = tagInput.trim();
    if (!value) return;
    if (form.tags.includes(value)) {
      setTagInput('');
      return;
    }
    setForm(prev => ({ ...prev, tags: [...prev.tags, value] }));
    setTagInput('');
  };

  const handleRemoveTag = (tag: string) => {
    setForm(prev => ({ ...prev, tags: prev.tags.filter(item => item !== tag) }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.workspaceId || !form.name.trim() || !form.prompt.trim()) return;
    if (form.trigger === 'cron' && !form.schedule.trim()) return;
    if (form.trigger === 'cron' && !scheduleValidation.isValid) return;
    try {
      await createTask(form);
    } catch (error) {
      logger.error('Failed to create task', { error });
    }
  };

  const disabled =
    state.creating ||
    !form.workspaceId ||
    !form.name.trim() ||
    !form.prompt.trim() ||
    (form.trigger === 'cron' && (!form.schedule.trim() || !scheduleValidation.isValid));

  const tagSuggestions = useMemo(() => {
    const tags = new Set<string>();
    state.automationJobs.forEach(task => task.tags.forEach(tag => tags.add(tag)));
    return Array.from(tags).slice(0, 6);
  }, [state.automationJobs]);

  const slashCommandButtonDisabled = !form.workspaceId || commandsLoading || (!commandsError && commands.length === 0);

  return (
    <Dialog open={state.isCreateDialogOpen} onOpenChange={(open) => (!open ? closeCreateDialog() : undefined)}>
      <DialogContent className="max-w-3xl max-h-[90vh] border-border/60 p-0 flex flex-col">
        <form className="flex flex-col min-h-0 flex-1" onSubmit={handleSubmit}>
          <DialogHeader className="border-b border-border/60 px-6 py-5">
            <div className="space-y-1">
              <DialogHeading icon={Clock} className="text-base font-semibold">
                {t('automation.create.title')}
              </DialogHeading>
              <p className="text-xs text-muted-foreground">
                {t('automation.create.subtitle')}
              </p>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto min-h-0 px-6 py-6 space-y-6">
            <section className="space-y-4">
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

            <section className="space-y-4">
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
                        if (newTrigger === 'manual') {
                          updated.schedule = '';
                        }
                        // Restore a default schedule when switching back to cron.
                        if (newTrigger === 'cron' && !prev.schedule) {
                          updated.schedule = '0 9 * * *';
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
                <div className="space-y-2">
                  <Label className="text-sm">{t('automation.form.fields.status.label')}</Label>
                  <Select
                    value={form.status}
                    onValueChange={(value) => setForm(prev => ({ ...prev, status: value as JobCreateInput['status'] }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('automation.form.fields.status.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map(option => (
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
                </div>
              )}
            </section>

            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Label className="text-sm">{t('automation.form.fields.tags.label')}</Label>
                <TagIcon className="h-4 w-4 text-muted-foreground" />
              </div>
              <div className="flex flex-wrap gap-2">
                {form.tags.map(tag => (
                  <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                    {tag}
                    <button type="button" onClick={() => handleRemoveTag(tag)} className="rounded-full p-0.5 hover:text-destructive">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(event) => setTagInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      handleAddTag();
                    }
                  }}
                  placeholder={t('automation.form.fields.tags.placeholder')}
                />
                <Button type="button" variant="outline" className="gap-2" onClick={handleAddTag}>
                  <Plus className="h-4 w-4" />
                  {t('automation.form.fields.tags.add')}
                </Button>
              </div>
              {tagSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{t('automation.form.fields.tags.suggestionsLabel')}</span>
                  {tagSuggestions.map(tag => (
                    <button
                      key={tag}
                      type="button"
                      className="rounded-full border border-border/60 bg-background px-3 py-1 transition hover:border-primary"
                      onClick={() => setForm(prev => ({ ...prev, tags: prev.tags.includes(tag) ? prev.tags : [...prev.tags, tag] }))}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              )}
            </section>
          </div>

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

export default JobCreateDialog;
