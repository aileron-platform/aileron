import React, { useMemo, useState } from 'react';
import { OutputStyleDialog } from '@/shared/components/dialogs';
import type { OutputStyleFormValue } from '../formTypes';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import * as templateApi from '@/shared/services/templateApi';
import useTemplateFileSection from '../hooks/useTemplateFileSection';
import { useTemplateApi } from '../hooks/useTemplateApi';
import { adaptOutputStyleFormValues } from '@/shared/components/template/adapters';
import { OutputStyleViewer, type OutputStyleData } from '@/shared/components/template/OutputStyleViewer';

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
  const { t } = useI18n();
  const { toast } = useToast();
  const { saveOutputStyles, loadOutputStyles } = useTemplateApi({
    templateId,
    onSuccess: () => {
      void onReloadTemplate?.();
    },
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingStyle, setEditingStyle] = useState<OutputStyleFormValue | null>(null);

  const {
    items,
    addItem,
    updateItem,
    removeItem,
  } = useTemplateFileSection<OutputStyleFormValue>({
    templateId,
    initialItems: outputStyles,
    onItemsChange: onOutputStylesChange,
    loadItems: templateId ? loadOutputStyles : undefined,
    getIdentifier: item => item.fileName,
  });

  const adaptedStyles = useMemo(() => adaptOutputStyleFormValues(items), [items]);

  const handleAdd = () => {
    setDialogMode('create');
    setEditingStyle(null);
    setDialogOpen(true);
  };

  const handleEdit = (item: OutputStyleData) => {
    const target = items.find(style => style.localId === item.id);
    if (!target) return;

    setDialogMode('edit');
    setEditingStyle(target);
    setDialogOpen(true);
  };

  const handleDelete = async (item: OutputStyleData) => {
    const target = items.find(style => style.localId === item.id);
    if (!target) return;

    if (templateId) {
      try {
        await templateApi.deleteOutputStyleFile(templateId, target.fileName);
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

  const handleDialogSubmit = async (style: OutputStyleFormValue) => {
    if (dialogMode === 'create') {
      // 更新本地狀態
      addItem(style);

      // 手動保存到服務器
      if (templateId) {
        await saveOutputStyles([...items, style], items);
      }
    } else {
      // 更新本地狀態
      updateItem(style);

      // 手動保存到服務器
      if (templateId) {
        const updatedItems = items.map(s => s.localId === style.localId ? style : s);
        await saveOutputStyles(updatedItems, items);
      }
    }

    setDialogOpen(false);
    setEditingStyle(null);
  };

  return (
    <>
      <OutputStyleViewer
        items={adaptedStyles}
        isEditable={true}
        onAdd={handleAdd}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <OutputStyleDialog
        variant="template"
        open={dialogOpen}
        mode={dialogMode}
        initialValue={editingStyle}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleDialogSubmit}
      />
    </>
  );
};

export default OutputStylesSection;

