import React from 'react';
import { SubAgentDialog } from '@/shared/components/dialogs';
import type { SubAgentFormValue } from '../formTypes';
import { SubAgentViewer, type SubAgentData } from '@/shared/components/template/SubAgentViewer';
import { adaptSubAgentFormValues } from '@/shared/components/template/adapters';
import * as templateApi from '@/shared/services/templateApi';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';
import { useTemplateApi } from '../hooks/useTemplateApi';

interface SubAgentsSectionProps {
  subAgents: SubAgentFormValue[];
  onSubAgentsChange: (agents: SubAgentFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const SubAgentsSection: React.FC<SubAgentsSectionProps> = ({
  subAgents,
  onSubAgentsChange,
  templateId,
  onReloadTemplate,
}) => {
  const { loadSubAgents } = useTemplateApi({
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
  } = useTemplateDocumentSection<SubAgentFormValue, SubAgentData>({
    templateId,
    initialItems: subAgents,
    onItemsChange: onSubAgentsChange,
    onReloadTemplate,
    loadItems: templateId ? loadSubAgents : undefined,
    getIdentifier: item => item.fileName,
    toViewItems: adaptSubAgentFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
    createRemote: async (item) => {
      await templateApi.createSubAgentFile(templateId!, {
        file_name: item.fileName,
        content: item.content,
      });
    },
    updateRemote: async (item, original) => {
      await templateApi.updateSubAgentFile(templateId!, original.fileName, {
        content: item.content,
      });
    },
    deleteRemote: async (item) => {
      await templateApi.deleteSubAgentFile(templateId!, item.fileName);
    },
    normalizeUpdatedItem: (item, original) => ({ ...item, fileName: original.fileName }),
  });

  return (
    <>
      <SubAgentViewer
        items={viewItems}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <SubAgentDialog
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

export default SubAgentsSection;
