import React, { useMemo, useState } from 'react';
import { Download, Plus, Zap } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { SettingsWorkflowActionButton, SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import HookCard from '@/features/template-management/components/HookCard';
import { useTemplateApi } from '@/features/template-management/features/template-editor/hooks/useTemplateApi';
import type { HookFormValue } from '@/features/template-management/features/template-editor/formTypes';
import { TemplateHookDialog } from './TemplateHookDialog';

interface TemplateHooksSettingsWorkflowProps {
  templateId?: string;
  hooks: HookFormValue[];
  onHooksChange?: (hooks: HookFormValue[]) => void;
  editable?: boolean;
  onSaveSuccess?: () => void;
}

export const TemplateHooksSettingsWorkflow: React.FC<TemplateHooksSettingsWorkflowProps> = ({
  templateId,
  hooks,
  onHooksChange,
  editable = false,
  onSaveSuccess,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { saveHooksConfig } = useTemplateApi({ templateId });
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingHook, setEditingHook] = useState<HookFormValue | undefined>();
  const handlePersist = async (nextHooks: HookFormValue[]) => {
    if (templateId) {
      const saved = await saveHooksConfig(nextHooks);
      if (!saved) return;
    }
    onHooksChange?.(nextHooks);
    onSaveSuccess?.();
  };

  const handleAdd = () => {
    if (!editable) return;
    setEditingHook(undefined);
    setIsDialogOpen(true);
  };

  const handleEdit = (hook: HookFormValue) => {
    if (!editable) return;
    setEditingHook(hook);
    setIsDialogOpen(true);
  };

  const handleDelete = async (hookId: string) => {
    if (!editable) return;
    const nextHooks = hooks.filter((hook) => hook.localId !== hookId);
    await handlePersist(nextHooks);
  };

  const handleSave = async (hookData: HookFormValue) => {
    const nextHooks = editingHook
      ? hooks.map((hook) => (hook.localId === editingHook.localId ? hookData : hook))
      : [...hooks, hookData];
    await handlePersist(nextHooks);
  };

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(hooks, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = t('template.detail.hooks.downloadFileName');
    window.document.body.appendChild(anchor);
    anchor.click();
    window.document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
    toast({
      title: t('template.detail.hooks.toasts.downloadSuccess.title'),
      description: t('template.detail.hooks.toasts.downloadSuccess.description'),
    });
  };

  const headerActions = useMemo(() => (
    <div className="flex items-center gap-2">
      {!editable ? (
        <SettingsWorkflowActionButton variant="outline" onClick={handleDownload}>
          <Download className="mr-1 h-3.5 w-3.5" />
          {t('template.detail.hooks.actions.download')}
        </SettingsWorkflowActionButton>
      ) : null}
      {editable ? (
        <SettingsWorkflowActionButton onClick={handleAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          {t('template.editor.hooks.actions.add')}
        </SettingsWorkflowActionButton>
      ) : null}
    </div>
  ), [editable, t]);

  return (
    <>
      <SettingsWorkflowShell
        title={editable ? t('template.editor.tabs.hooks') : t('template.detail.hooks.header.title')}
        icon={Zap}
        headerActions={headerActions}
        summary={<SettingsWorkflowCountBadge label={t('template.detail.hooks.badge', { count: hooks.length })} />}
        singleHeader
        hasItems={hooks.length > 0}
        emptyIcon={<Zap className="h-6 w-6 text-muted-foreground" />}
        emptyTitle={editable ? t('template.editor.hooks.empty.title') : t('template.detail.hooks.empty.title')}
        emptyDescription={editable ? t('template.editor.hooks.empty.description') : t('template.detail.hooks.empty.description')}
        emptyActions={editable ? (
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('template.editor.hooks.actions.add')}
          </Button>
        ) : undefined}
        contentClassName="space-y-4 p-4"
      >
        {hooks.map((hook) => (
          <HookCard
            key={hook.localId}
            hook={hook}
            showActions={editable}
            onEdit={editable ? handleEdit : undefined}
            onDelete={editable ? handleDelete : undefined}
          />
        ))}
      </SettingsWorkflowShell>

      {editable ? (
        <TemplateHookDialog
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          onSave={handleSave}
          initialData={editingHook}
          existingHooks={hooks}
        />
      ) : null}
    </>
  );
};

export default TemplateHooksSettingsWorkflow;
