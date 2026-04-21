import { useCallback, useMemo, useState } from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import useTemplateFileSection from './useTemplateFileSection';

const logger = createLogger('useTemplateDocumentSection');

export interface TemplateDocumentSectionOptions<TFormValue, TViewItem> {
  templateId?: string;
  initialItems: TFormValue[];
  onItemsChange: (items: TFormValue[]) => void;
  onReloadTemplate?: () => Promise<void>;
  loadItems?: () => Promise<TFormValue[]>;
  getIdentifier: (item: TFormValue) => string;
  toViewItems: (items: TFormValue[]) => TViewItem[];
  getViewItemId: (item: TViewItem) => string;
  getFormItemId: (item: TFormValue) => string;
  createRemote?: (item: TFormValue) => Promise<void>;
  updateRemote?: (item: TFormValue, original: TFormValue) => Promise<void>;
  deleteRemote?: (item: TFormValue) => Promise<void>;
  normalizeUpdatedItem?: (item: TFormValue, original: TFormValue) => TFormValue;
}

export interface TemplateDocumentSectionResult<TFormValue, TViewItem> {
  items: TFormValue[];
  viewItems: TViewItem[];
  dialogOpen: boolean;
  dialogMode: 'create' | 'edit';
  editingItem: TFormValue | null;
  setDialogOpen: (open: boolean) => void;
  handleAdd: () => void;
  handleEdit: (item: TViewItem) => void;
  handleDelete: (item: TViewItem) => Promise<void>;
  handleSubmit: (item: TFormValue) => Promise<void>;
}

export function useTemplateDocumentSection<TFormValue, TViewItem>({
  templateId,
  initialItems,
  onItemsChange,
  onReloadTemplate,
  loadItems,
  getIdentifier,
  toViewItems,
  getViewItemId,
  getFormItemId,
  createRemote,
  updateRemote,
  deleteRemote,
  normalizeUpdatedItem,
}: TemplateDocumentSectionOptions<TFormValue, TViewItem>): TemplateDocumentSectionResult<TFormValue, TViewItem> {
  const { t } = useI18n();
  const { toast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingItem, setEditingItem] = useState<TFormValue | null>(null);

  const { items, addItem, updateItem, removeItem } = useTemplateFileSection<TFormValue>({
    templateId,
    initialItems,
    onItemsChange,
    loadItems: templateId ? loadItems : undefined,
    getIdentifier,
  });

  const viewItems = useMemo(() => toViewItems(items), [items, toViewItems]);

  const handleAdd = useCallback(() => {
    setDialogMode('create');
    setEditingItem(null);
    setDialogOpen(true);
  }, []);

  const handleEdit = useCallback((viewItem: TViewItem) => {
    const target = items.find((item) => getFormItemId(item) === getViewItemId(viewItem));
    if (!target) {
      return;
    }
    setDialogMode('edit');
    setEditingItem(target);
    setDialogOpen(true);
  }, [getFormItemId, getViewItemId, items]);

  const handleDelete = useCallback(async (viewItem: TViewItem) => {
    const target = items.find((item) => getFormItemId(item) === getViewItemId(viewItem));
    if (!target) {
      return;
    }

    if (templateId && deleteRemote) {
      try {
        await deleteRemote(target);
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
  }, [deleteRemote, getFormItemId, getViewItemId, items, onReloadTemplate, removeItem, t, templateId, toast]);

  const handleSubmit = useCallback(async (nextItem: TFormValue) => {
    if (dialogMode === 'create') {
      addItem(nextItem);

      if (templateId && createRemote) {
        try {
          await createRemote(nextItem);
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
      setEditingItem(null);
      return;
    }

    const original = editingItem || items.find((item) => getFormItemId(item) === getFormItemId(nextItem));
    if (!original) {
      setDialogOpen(false);
      setEditingItem(null);
      return;
    }

    if (templateId && updateRemote) {
      try {
        await updateRemote(nextItem, original);
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

    updateItem(normalizeUpdatedItem ? normalizeUpdatedItem(nextItem, original) : nextItem);
    setDialogOpen(false);
    setEditingItem(null);
  }, [
    addItem,
    createRemote,
    dialogMode,
    editingItem,
    getFormItemId,
    items,
    normalizeUpdatedItem,
    onReloadTemplate,
    t,
    templateId,
    toast,
    updateItem,
    updateRemote,
  ]);

  return {
    items,
    viewItems,
    dialogOpen,
    dialogMode,
    editingItem,
    setDialogOpen,
    handleAdd,
    handleEdit,
    handleDelete,
    handleSubmit,
  };
}

export default useTemplateDocumentSection;
