import React from 'react';
import { GitBranch } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps, type BaseItem, type ItemActions } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';

// SubAgent 數據類型
export interface SubAgentData extends BaseItem {}

// 屬性類型
export interface SubAgentViewerProps extends Omit<MarkdownFileViewerProps<SubAgentData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: SubAgentData) => void;
  onDelete?: (item: SubAgentData) => void;
  onRefresh?: () => void | Promise<void>;
}

export const SubAgentViewer: React.FC<SubAgentViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  onRefresh,
  ...restProps
}) => {
  const { t } = useI18n();

  // 翻譯鍵
  const i18nKeys: MarkdownFileViewerProps<SubAgentData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.subAgents.sidebar.title' : 'template.detail.subAgents.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.subAgents.sidebar.searchPlaceholder' : 'template.detail.subAgents.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.subAgents.sidebar.empty' : 'template.detail.subAgents.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.subAgents.list.nameFallback' : 'template.detail.subAgents.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.subAgents.list.sizeLabel' : 'template.detail.subAgents.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.subAgents.detail.descriptionFallback' : 'template.detail.subAgents.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.subAgents.actions.copy' : 'template.detail.subAgents.actions.copy',
      download: isEditable ? 'template.editor.subAgents.actions.download' : 'template.detail.subAgents.actions.download',
      add: isEditable ? 'template.editor.subAgents.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.subAgents.empty.title' : 'template.detail.subAgents.empty.title',
      description: isEditable ? 'template.editor.subAgents.empty.description' : 'template.detail.subAgents.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.subAgents.errors.copyFailed' : 'template.detail.subAgents.errors.copyFailed',
    },
  };

  // 操作按鈕
  const actions: ItemActions<SubAgentData> | undefined = React.useMemo(() => {
    if (!isEditable) return undefined;

    return {
      edit: onEdit ? {
        onClick: (item: SubAgentData) => onEdit(item),
        label: t('template.editor.subAgents.actions.edit'),
      } : undefined,
      delete: onDelete ? {
        onClick: (item: SubAgentData) => onDelete(item),
        label: t('template.editor.subAgents.actions.delete'),
      } : undefined,
    };
  }, [isEditable, onEdit, onDelete, t]);

  return (
    <MarkdownFileViewer<SubAgentData>
      {...restProps}
      getItemIcon={() => GitBranch}
      renderContent={(item) => (
        item.content ? (
          <MarkdownContent content={item.content} />
        ) : (
          <div className="text-sm text-muted-foreground">
            {t(i18nKeys.detail.descriptionFallback)}
          </div>
        )
      )}
      getDownloadFileName={(item) => item.fileName}
      getDownloadFileType={() => 'txt'}
      actions={actions}
      i18nKeys={i18nKeys}
      showAddButton={isEditable}
      onRefresh={onRefresh}
      refreshLabel={t('template.editor.fileManagement.sidebar.refresh')}
    />
  );
};

export default SubAgentViewer;
