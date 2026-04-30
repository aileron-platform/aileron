import React from 'react';
import { TemplateAgentDialog } from '../components/TemplateAgentDialog';
import type { AgentFormValue } from '../formTypes';
import { AgentViewer, type AgentData } from '@/features/template-management/components/metadata-viewers/AgentViewer';
import { adaptAgentFormValues } from '@/features/template-management/components/metadata-viewers/adapters';
import useTemplateDocumentSection from '../hooks/useTemplateDocumentSection';

interface AgentsSectionProps {
  agents: AgentFormValue[];
  onAgentsChange: (agents: AgentFormValue[]) => void;
  templateId?: string;
  onReloadTemplate?: () => Promise<void>;
}

const AgentsSection: React.FC<AgentsSectionProps> = ({
  agents,
  onAgentsChange,
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
  } = useTemplateDocumentSection<AgentFormValue, AgentData>({
    initialItems: agents,
    onItemsChange: onAgentsChange,
    getIdentifier: item => item.fileName,
    toViewItems: adaptAgentFormValues,
    getViewItemId: item => item.id,
    getFormItemId: item => item.localId,
    normalizeUpdatedItem: (item, original) => ({ ...item, fileName: original.fileName }),
  });

  return (
    <>
      <AgentViewer
        items={viewItems}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onRefresh={onReloadTemplate}
      />

      <TemplateAgentDialog
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingItem}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </>
  );
};

export default AgentsSection;
