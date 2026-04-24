import React from 'react';
import { GitBranch } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps, type BaseItem, type ItemActions } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';

// Agent 數據類型
export interface AgentData extends BaseItem {}

// 屬性類型
export interface AgentViewerProps extends Omit<MarkdownFileViewerProps<AgentData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: AgentData) => void;
  onDelete?: (item: AgentData) => void;
  onRefresh?: () => void | Promise<void>;
}

export const AgentViewer: React.FC<AgentViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  onRefresh,
  ...restProps
}) => {
  const { t } = useI18n();

  // 翻譯鍵
  const i18nKeys: MarkdownFileViewerProps<AgentData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.agents.sidebar.title' : 'template.detail.agents.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.agents.sidebar.searchPlaceholder' : 'template.detail.agents.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.agents.sidebar.empty' : 'template.detail.agents.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.agents.list.nameFallback' : 'template.detail.agents.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.agents.list.sizeLabel' : 'template.detail.agents.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.agents.detail.descriptionFallback' : 'template.detail.agents.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.agents.actions.copy' : 'template.detail.agents.actions.copy',
      download: isEditable ? 'template.editor.agents.actions.download' : 'template.detail.agents.actions.download',
      add: isEditable ? 'template.editor.agents.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.agents.empty.title' : 'template.detail.agents.empty.title',
      description: isEditable ? 'template.editor.agents.empty.description' : 'template.detail.agents.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.agents.errors.copyFailed' : 'template.detail.agents.errors.copyFailed',
    },
  };

  // 操作按鈕
  const actions: ItemActions<AgentData> | undefined = React.useMemo(() => {
    if (!isEditable) return undefined;

    return {
      edit: onEdit ? {
        onClick: (item: AgentData) => onEdit(item),
        label: t('template.editor.agents.actions.edit'),
      } : undefined,
      delete: onDelete ? {
        onClick: (item: AgentData) => onDelete(item),
        label: t('template.editor.agents.actions.delete'),
      } : undefined,
    };
  }, [isEditable, onEdit, onDelete, t]);

  return (
    <MarkdownFileViewer<AgentData>
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

export default AgentViewer;
