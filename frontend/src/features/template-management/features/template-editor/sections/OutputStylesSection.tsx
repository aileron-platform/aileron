import React from 'react';
import { OutputStyleDialog } from '@/shared/components/dialogs';
import type { OutputStyleFormValue } from '../formTypes';
import * as templateApi from '@/shared/services/templateApi';
import { adaptOutputStyleFormValues } from '@/shared/components/template/adapters';
import { OutputStyleViewer, type OutputStyleData } from '@/shared/components/template/OutputStyleViewer';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';
import { useTemplateApi } from '../hooks/useTemplateApi';

interface OutputStylesSectionProps {
  outputStyles: OutputStyleFormValue[];
  onOutputStylesChange: (styles: OutputStyleFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const OutputStylesSection: React.FC<OutputStylesSectionProps> = ({
  outputStyles,
  onOutputStylesChange,
  templateId,
  onReloadTemplate,
}) => {
  const { loadOutputStyles } = useTemplateApi({
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
  } = useTemplateDocumentSection<OutputStyleFormValue, OutputStyleData>({
    templateId,
    initialItems: outputStyles,
    onItemsChange: onOutputStylesChange,
    onReloadTemplate,
    loadItems: templateId ? loadOutputStyles : undefined,
    getIdentifier: item => item.fileName,
    toViewItems: adaptOutputStyleFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
    createRemote: async (item) => {
      await templateApi.createOutputStyleFile(templateId!, {
        file_name: item.fileName,
        content: item.content,
      });
    },
    updateRemote: async (item, original) => {
      await templateApi.updateOutputStyleFile(templateId!, original.fileName, {
        content: item.content,
      });
    },
    deleteRemote: async (item) => {
      await templateApi.deleteOutputStyleFile(templateId!, item.fileName);
    },
    normalizeUpdatedItem: (item, original) => ({ ...item, fileName: original.fileName }),
  });

  return (
    <>
      <OutputStyleViewer
        items={viewItems}
        isEditable={true}
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onRefresh={templateId ? loadOutputStyles : undefined}
      />

      <OutputStyleDialog
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

export default OutputStylesSection;
