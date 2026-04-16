/**
 * AutomationJobEditDialog - 共用的排程任務編輯對話框
 * 可在排程中心和工作區排程列表中重複使用
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
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
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { AutomationJob, AutomationJobUpdateInput } from '@/features/automation/types';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { SlashCommandPickerDialog } from '@/shared/components/slash-commands';
import { Clock, Plus, Slash, Tag as TagIcon, X } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SchedulerTaskEditDialog');

export interface SchedulerWorkspaceSummary {
  id: string;
  name: string;
  accessSource?: 'owned' | 'shared';
}

interface AutomationJobEditDialogProps {
  isOpen: boolean;
  task: AutomationJob | null;
  loading: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: (payload: AutomationJobUpdateInput) => Promise<void>;
  workspaces: SchedulerWorkspaceSummary[];
  workspacesLoading: boolean;
  commands: SlashCommandItem[];
  commandsLoading: boolean;
  existingTags?: string[];
}

const TRIGGER_OPTIONS = [
  { value: 'cron', labelKey: 'automation.form.trigger.cron' },
  { value: 'interval', labelKey: 'automation.form.trigger.interval' },
  { value: 'manual', labelKey: 'automation.form.trigger.manual' },
  { value: 'webhook', labelKey: 'automation.form.trigger.webhook' },
];

const STATUS_OPTIONS = [
  { value: 'active', labelKey: 'automation.form.status.active' },
  { value: 'paused', labelKey: 'automation.form.status.paused' },
  { value: 'draft', labelKey: 'automation.form.status.draft' },
];

const mapTaskToForm = (task: AutomationJob): AutomationJobUpdateInput => ({
  id: task.id,
  name: task.name,
  description: task.description,
  owner: task.owner,
  userId: task.userId,
  workspaceId: task.workspaceId,
  prompt: task.prompt,
  status: task.status,
  trigger: task.trigger,
  schedule: task.schedule,
  tags: [...task.tags],
  notifications: { ...task.notifications },
  metadata: { ...task.metadata },
});

export const AutomationJobEditDialog: React.FC<AutomationJobEditDialogProps> = ({
  isOpen,
  task,
  loading,
  saving,
  onClose,
  onSave,
  workspaces,
  workspacesLoading,
  commands,
  commandsLoading,
  existingTags = [],
}) => {
  const [form, setForm] = useState<AutomationJobUpdateInput | null>(null);
  const [tagInput, setTagInput] = useState('');
  const [slashDialogOpen, setSlashDialogOpen] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    if (isOpen && task) {
      setForm(mapTaskToForm(task));
      setTagInput('');
    }
    if (!isOpen) {
      setForm(null);
      setTagInput('');
    }
  }, [isOpen, task]);

  const handleAddTag = () => {
    if (!form) return;
    const value = tagInput.trim();
    if (!value) return;
    if (form.tags.includes(value)) {
      setTagInput('');
      return;
    }
    setForm(prev => prev ? { ...prev, tags: [...prev.tags, value] } : prev);
    setTagInput('');
  };

  const handleRemoveTag = (tag: string) => {
    setForm(prev => prev ? { ...prev, tags: prev.tags.filter(item => item !== tag) } : prev);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form) return;
    if (!form.workspaceId || !form.name.trim() || !form.schedule.trim() || !form.prompt.trim()) return;
    try {
      await onSave(form);
    } catch (error) {
      logger.error(t('automation.logs.updateFailed'), { error });
    }
  };

  const disabled =
    !form ||
    saving ||
    !form.workspaceId ||
    !form.name.trim() ||
    !form.schedule.trim() ||
    !form.prompt.trim();

  const tagSuggestions = useMemo(() => {
    return existingTags.slice(0, 6);
  }, [existingTags]);

  const slashCommandButtonDisabled = !form || commandsLoading || commands.length === 0;

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
        <DialogHeader className="border-b border-border/60 px-6 py-5 flex flex-row items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Clock className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <DialogTitle className="text-base font-semibold">{t('automation.edit.title')}</DialogTitle>
            <p className="text-xs text-muted-foreground">{t('automation.edit.subtitle')}</p>
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
                  onValueChange={(value) => setForm(prev => prev ? { ...prev, workspaceId: value } : prev)}
                  disabled={workspacesLoading}
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
                            {ws.accessSource === 'shared' ? 'Shared' : 'Owned'}
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
          </section>

          <section className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm">
                {t('automation.form.fields.prompt.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <div className="flex gap-2">
                <Textarea
                  value={form.prompt}
                  onChange={(event) => setForm(prev => prev ? { ...prev, prompt: event.target.value } : prev)}
                  placeholder={t('automation.form.fields.prompt.placeholder')}
                  rows={3}
                  required
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => setSlashDialogOpen(true)}
                  disabled={slashCommandButtonDisabled}
                  className="flex-shrink-0"
                >
                  <Slash className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label className="text-sm">{t('automation.form.fields.trigger.label')}</Label>
                <Select
                  value={form.trigger}
                  onValueChange={(value) => setForm(prev => prev ? { ...prev, trigger: value as any } : prev)}
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
                  <Input
                    value={form.schedule}
                    onChange={(event) => setForm(prev => prev ? { ...prev, schedule: event.target.value } : prev)}
                    placeholder={t('automation.form.fields.schedule.placeholder')}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.schedule.timezoneHelper')}
                  </p>
                </div>
              )}

              {form && form.trigger === 'webhook' && (
                <div className="space-y-2 col-span-2">
                  <Label className="text-sm">{t('automation.form.fields.webhookApiKey.label')}</Label>
                  <Input
                    value={(form as any).webhookApiKey || ''}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('automation.form.fields.webhookApiKey.helper')}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label className="text-sm">{t('automation.form.fields.status.label')}</Label>
              <Select
                value={form.status}
                onValueChange={(value) => setForm(prev => prev ? { ...prev, status: value as any } : prev)}
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

          <section className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm">{t('automation.form.fields.tags.label')}</Label>
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
                  maxLength={20}
                />
                <Button type="button" variant="outline" size="icon" onClick={handleAddTag}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {form.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {form.tags.map(tag => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      <TagIcon className="h-3 w-3" />
                      {tag}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
              {tagSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  <span className="text-xs text-muted-foreground">{t('automation.form.fields.tags.suggestions')}:</span>
                  {tagSuggestions.map(tag => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className="cursor-pointer hover:bg-accent"
                      onClick={() => {
                        if (!form.tags.includes(tag)) {
                          setForm(prev => prev ? { ...prev, tags: [...prev.tags, tag] } : prev);
                        }
                      }}
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
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
      <DialogContent className="max-w-3xl max-h-[90vh] border-border/60 p-0 flex flex-col">
        {renderContent()}

        <SlashCommandPickerDialog
          open={slashDialogOpen}
          onOpenChange={setSlashDialogOpen}
          commands={commands}
          onSelect={(command: SlashCommandItem) => {
            setForm(prev => prev ? { ...prev, prompt: `/${command.displayName}` } : prev);
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

export default AutomationJobEditDialog;
