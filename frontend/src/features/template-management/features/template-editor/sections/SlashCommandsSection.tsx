import React, { useMemo, useState } from 'react';
import { SlashCommandDialog } from '@/shared/components/dialogs';
import type { SlashCommandFormValue } from '../formTypes';
import { SlashCommandViewer, type SlashCommandData } from '@/shared/components/template/SlashCommandViewer';
import { adaptSlashCommandFormValues } from '@/shared/components/template/adapters';
import useTemplateFileSection from '../hooks/useTemplateFileSection';
import { useTemplateApi } from '../hooks/useTemplateApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import * as templateApi from '@/shared/services/templateApi';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SlashCommandsSection');

interface SlashCommandsSectionProps {
  slashCommands: SlashCommandFormValue[];
  onSlashCommandsChange: (commands: SlashCommandFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const SlashCommandsSection: React.FC<SlashCommandsSectionProps> = ({
  slashCommands,
  onSlashCommandsChange,
  templateId,
  onReloadTemplate,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { saveSlashCommands, loadSlashCommands } = useTemplateApi({
    templateId,
    onSuccess: () => {
      void onReloadTemplate?.();
    },
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingCommand, setEditingCommand] = useState<SlashCommandFormValue | null>(null);

  const {
    items,
    addItem,
    updateItem,
    removeItem,
  } = useTemplateFileSection<SlashCommandFormValue>({
    templateId,
    initialItems: slashCommands,
    onItemsChange: onSlashCommandsChange,
    loadItems: templateId ? loadSlashCommands : undefined,
    getIdentifier: item => item.fileName,
  });

  const adaptedCommands = useMemo(() => adaptSlashCommandFormValues(items), [items]);

  const handleAdd = () => {
    setDialogMode('create');
    setEditingCommand(null);
    setDialogOpen(true);
  };

  const handleEdit = (item: SlashCommandData) => {
    const target = items.find(command => command.localId === item.id);
    if (!target) return;

    setDialogMode('edit');
    setEditingCommand(target);
    setDialogOpen(true);
  };

  const handleDelete = async (item: SlashCommandData) => {
    const target = items.find(command => command.localId === item.id);
    if (!target) return;

    if (templateId) {
      try {
        await templateApi.deleteSlashCommandFile(templateId, target.fileName);
        toast({
          title: t('template.editor.toasts.deleteSuccess.title'),
          description: t('template.editor.toasts.deleteSuccess.description'),
          variant: 'success',
        });
        await onReloadTemplate?.();
      } catch (error) {
        logger.error('delete failed', { error });
        toast({
          title: t('template.editor.toasts.deleteFailed.title'),
          description: t('template.editor.toasts.deleteFailed.description'),
          variant: 'destructive',
        });
        return;
      }
    }

    removeItem(target);
  };

  const handleDialogSubmit = async (command: SlashCommandFormValue) => {
    if (dialogMode === 'create') {
      // 更新本地狀態
      addItem(command);

      // 手動保存到服務器
      if (templateId) {
        try {
          await templateApi.createSlashCommandFile(templateId, {
            file_name: command.fileName,
            content: command.content,
          });
          toast({
            title: t('template.editor.toasts.saveSuccess.title'),
            description: t('template.editor.toasts.saveSuccess.description'),
            variant: 'success',
          });
          await onReloadTemplate?.();
        } catch (error) {
          logger.error('create failed', { error });
          toast({
            title: t('template.editor.toasts.saveFailed.title'),
            description: t('template.editor.toasts.saveFailed.description'),
            variant: 'destructive',
          });
          return;
        }
      }

      setDialogOpen(false);
      setEditingCommand(null);
      return;
    }

    const original = editingCommand || items.find(item => item.localId === command.localId);
    if (!original) {
      setDialogOpen(false);
      setEditingCommand(null);
      return;
    }

    if (templateId) {
      try {
        await templateApi.updateSlashCommandFile(templateId, original.fileName, {
          content: command.content,
        });
        toast({
          title: t('template.editor.toasts.saveSuccess.title'),
          description: t('template.editor.toasts.saveSuccess.description'),
          variant: 'success',
        });
        await onReloadTemplate?.();
      } catch (error) {
        logger.error('update failed', { error });
        toast({
          title: t('template.editor.toasts.saveFailed.title'),
          description: t('template.editor.toasts.saveFailed.description'),
          variant: 'destructive',
        });
        return;
      }
    }

    // 維持原始檔名，避免未支援的重新命名情境
    updateItem({ ...command, fileName: original.fileName });
    setDialogOpen(false);
    setEditingCommand(null);
  };

  return (
    <>
      <SlashCommandViewer
        items={adaptedCommands}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <SlashCommandDialog
        variant="template"
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingCommand}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleDialogSubmit}
      />
    </>
  );
};

export default SlashCommandsSection;
