import { useState } from 'react';
import { Plus, Terminal } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { HookDialog } from '@/shared/components/dialogs';
import HookCard from '@/features/template-management/components/HookCard';
import type { HookFormValue } from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTemplateApi } from '../hooks/useTemplateApi';
import { useParams } from 'react-router-dom';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface HooksSectionProps {
  hooks: HookFormValue[];
  onHooksChange: (hooks: HookFormValue[]) => void;
}


const HooksSection: React.FC<HooksSectionProps> = ({
  hooks,
  onHooksChange
}) => {
  const { t } = useI18n();
  const { templateId } = useParams<{ templateId: string }>();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingHook, setEditingHook] = useState<HookFormValue | undefined>();
  const { reloadFromSource } = useTemplateManagementContext();
  const { isSaving, saveHooksConfig } = useTemplateApi({
    templateId,
    onSuccess: reloadFromSource // 保存成功後重新載入模板列表
  });

  const handleAdd = () => {
    setEditingHook(undefined);
    setIsDialogOpen(true);
  };

  const handleEdit = (hook: HookFormValue) => {
    setEditingHook(hook);
    setIsDialogOpen(true);
  };

  const handleDelete = async (hookId: string) => {
    const updatedHooks = hooks.filter(hook => hook.localId !== hookId);

    // 更新本地狀態
    onHooksChange(updatedHooks);

    // 立即儲存到後端
    await saveHooksConfig(updatedHooks);
  };

  const handleSave = async (hookData: HookFormValue) => {
    let updatedHooks: HookFormValue[];

    if (editingHook) {
      // 編輯現有Hook
      updatedHooks = hooks.map(hook =>
        hook.localId === editingHook.localId ? hookData : hook
      );
    } else {
      // 新增 Hook
      updatedHooks = [...hooks, hookData];
    }

    // 更新本地狀態
    onHooksChange(updatedHooks);

    // 立即儲存到後端
    await saveHooksConfig(updatedHooks);
  };

  // 處理編輯特定事件的Hook
  const handleEditEvent = (eventType: string) => {
    const eventHook = hooks.find(hook => hook.event === eventType);
    if (eventHook) {
      handleEdit(eventHook);
    }
  };

  // 處理刪除特定事件的所有Hook
  const handleDeleteEvent = async (eventType: string) => {
    const updatedHooks = hooks.filter(hook => hook.event !== eventType);

    // 更新本地狀態
    onHooksChange(updatedHooks);

    // 立即儲存到後端
    await saveHooksConfig(updatedHooks);
  };

  return (
    <>
      {hooks.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
          <Terminal className="h-10 w-10 text-muted-foreground" />
          <div className="space-y-1">
            <p className="text-base font-medium text-muted-foreground">
              {t('template.editor.hooks.empty.title')}
            </p>
            <p className="text-sm text-muted-foreground">
              {t('template.editor.hooks.empty.description')}
            </p>
          </div>
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
            <Plus className="mr-1 h-3.5 w-3.5" /> {t('template.editor.hooks.actions.add')}
          </Button>
        </div>
      ) : (
        <div className="space-y-4 p-6">
          {/* 右上角新增按鈕 */}
          <div className="flex justify-end mb-4">
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
              <Plus className="mr-1 h-3.5 w-3.5" /> {t('template.editor.hooks.actions.add')}
            </Button>
          </div>
          {hooks.map((hook) => (
            <HookCard
              key={hook.localId}
              hook={hook}
              mode="edit"
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <HookDialog
        variant="template"
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSave={handleSave}
        initialData={editingHook}
        existingHooks={hooks}
      />
    </>
  );
};

export default HooksSection;

