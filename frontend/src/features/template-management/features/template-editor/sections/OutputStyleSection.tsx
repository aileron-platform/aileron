import React from 'react';
import { TemplateOutputStyleDialog } from '../components/TemplateOutputStyleDialog';
import type { OutputStyleFormValue } from '../formTypes';
import { adaptOutputStyleFormValues } from '@/features/template-management/components/metadata-viewers/adapters';
import { OutputStyleViewer, type OutputStyleData } from '@/features/template-management/components/metadata-viewers/OutputStyleViewer';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';

interface OutputStyleSectionProps {
  outputStyle: OutputStyleFormValue[];
  onOutputStyleChange: (styles: OutputStyleFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const OutputStyleSection: React.FC<OutputStyleSectionProps> = ({
  outputStyle,
  onOutputStyleChange,
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
  } = useTemplateDocumentSection<OutputStyleFormValue, OutputStyleData>({
    initialItems: outputStyle,
    onItemsChange: onOutputStyleChange,
    getIdentifier: item => item.fileName,
    toViewItems: adaptOutputStyleFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
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
        onRefresh={onReloadTemplate}
      />

      <TemplateOutputStyleDialog
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingItem}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </>
  );
};

export default OutputStyleSection;
