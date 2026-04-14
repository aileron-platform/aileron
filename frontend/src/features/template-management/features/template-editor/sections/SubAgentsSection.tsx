import React, { useMemo, useState } from 'react';
import { SubAgentDialog } from '@/shared/components/dialogs';
import type { SubAgentFormValue } from '../formTypes';
import { SubAgentViewer, type SubAgentData } from '@/shared/components/template/SubAgentViewer';
import { adaptSubAgentFormValues } from '@/shared/components/template/adapters';
import useTemplateFileSection from '../hooks/useTemplateFileSection';
import { useTemplateApi } from '../hooks/useTemplateApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import * as templateApi from '@/shared/services/templateApi';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SubAgentsSection');

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
  const { t } = useI18n();
  const { toast } = useToast();
  const { saveSubAgents, loadSubAgents } = useTemplateApi({
    templateId,
    onSuccess: () => {
      void onReloadTemplate?.();
    },
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingAgent, setEditingAgent] = useState<SubAgentFormValue | null>(null);

  const {
    items,
    addItem,
    updateItem,
    removeItem,
  } = useTemplateFileSection<SubAgentFormValue>({
    templateId,
    initialItems: subAgents,
    onItemsChange: onSubAgentsChange,
    loadItems: templateId ? loadSubAgents : undefined,
    getIdentifier: item => item.fileName,
  });

  const adaptedAgents = useMemo(() => adaptSubAgentFormValues(items), [items]);

  const handleAdd = () => {
    setDialogMode('create');
    setEditingAgent(null);
    setDialogOpen(true);
  };

  const handleEdit = (item: SubAgentData) => {
    const target = items.find(agent => agent.localId === item.id);
    if (!target) return;

    setDialogMode('edit');
    setEditingAgent(target);
    setDialogOpen(true);
  };

  const handleDelete = async (item: SubAgentData) => {
    const target = items.find(agent => agent.localId === item.id);
    if (!target) return;

    if (templateId) {
      try {
        await templateApi.deleteSubAgentFile(templateId, target.fileName);
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

  const handleDialogSubmit = async (agent: SubAgentFormValue) => {
    if (dialogMode === 'create') {
      // 更新本地狀態
      addItem(agent);

      // 手動保存到服務器
      if (templateId) {
        try {
          await templateApi.createSubAgentFile(templateId, {
            file_name: agent.fileName,
            content: agent.content,
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
      setEditingAgent(null);
      return;
    }

    const original = editingAgent || items.find(item => item.localId === agent.localId);
    if (!original) {
      setDialogOpen(false);
      setEditingAgent(null);
      return;
    }

    if (templateId) {
      try {
        await templateApi.updateSubAgentFile(templateId, original.fileName, {
          content: agent.content,
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
    updateItem({ ...agent, fileName: original.fileName });
    setDialogOpen(false);
    setEditingAgent(null);
  };

  return (
    <>
      <SubAgentViewer
        items={adaptedAgents}
        isEditable
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <SubAgentDialog
        variant="template"
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingAgent}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleDialogSubmit}
      />
    </>
  );
};

export default SubAgentsSection;
