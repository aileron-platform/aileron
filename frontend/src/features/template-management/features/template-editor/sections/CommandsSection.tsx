import React from 'react';
import { TemplateCommandDialog } from '../components/TemplateCommandDialog';
import type { CommandFormValue } from '../formTypes';
import { CommandViewer, type CommandData } from '@/features/template-management/components/metadata-viewers/CommandViewer';
import { adaptCommandFormValues } from '@/features/template-management/components/metadata-viewers/adapters';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';

interface CommandsSectionProps {
  commands: CommandFormValue[];
  onCommandsChange: (commands: CommandFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const CommandsSection: React.FC<CommandsSectionProps> = ({
  commands,
  onCommandsChange,
  templateId,
  onReloadTemplate,
}) => {
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
  } = useTemplateDocumentSection<CommandFormValue, CommandData>({
    initialItems: commands,
    onItemsChange: onCommandsChange,
    getIdentifier: item => item.fileName,
    toViewItems: adaptCommandFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
    normalizeUpdatedItem: (item, original) => ({ ...item, fileName: original.fileName }),
  });

  return (
    <>
      <CommandViewer
        items={viewItems}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onRefresh={onReloadTemplate}
      />

      <TemplateCommandDialog
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingItem}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </>
  );
};

export default CommandsSection;
