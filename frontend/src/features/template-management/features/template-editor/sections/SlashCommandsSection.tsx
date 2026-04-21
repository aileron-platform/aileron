import React from 'react';
import { SlashCommandDialog } from '@/shared/components/dialogs';
import type { SlashCommandFormValue } from '../formTypes';
import { SlashCommandViewer, type SlashCommandData } from '@/shared/components/template/SlashCommandViewer';
import { adaptSlashCommandFormValues } from '@/shared/components/template/adapters';
import * as templateApi from '@/shared/services/templateApi';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';
import { useTemplateApi } from '../hooks/useTemplateApi';

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
  const { loadSlashCommands } = useTemplateApi({
    templateId,
    onSuccess: () => {
      void onReloadTemplate?.();
    },
  });

  const {
    viewItems,
    dialogOpen,
    dialogMode,
    editingItem,
    setDialogOpen,
    handleAdd,
    handleEdit,
    handleDelete,
    handleSubmit,
  } = useTemplateDocumentSection<SlashCommandFormValue, SlashCommandData>({
    templateId,
    initialItems: slashCommands,
    onItemsChange: onSlashCommandsChange,
    onReloadTemplate,
    loadItems: templateId ? loadSlashCommands : undefined,
    getIdentifier: item => item.fileName,
    toViewItems: adaptSlashCommandFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
    createRemote: async (item) => {
      await templateApi.createSlashCommandFile(templateId!, {
        file_name: item.fileName,
        content: item.content,
      });
    },
    updateRemote: async (item, original) => {
      await templateApi.updateSlashCommandFile(templateId!, original.fileName, {
        content: item.content,
      });
    },
    deleteRemote: async (item) => {
      await templateApi.deleteSlashCommandFile(templateId!, item.fileName);
    },
    normalizeUpdatedItem: (item, original) => ({ ...item, fileName: original.fileName }),
  });

  return (
    <>
      <SlashCommandViewer
        items={viewItems}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <SlashCommandDialog
        variant="template"
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingItem}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </>
  );
};

export default SlashCommandsSection;
