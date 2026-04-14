import React from 'react';
import { Terminal } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps, type BaseItem, type ItemActions } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';

// SlashCommand 數據類型
export interface SlashCommandData extends BaseItem {}

// 屬性類型
export interface SlashCommandViewerProps extends Omit<MarkdownFileViewerProps<SlashCommandData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: SlashCommandData) => void;
  onDelete?: (item: SlashCommandData) => void;
}

export const SlashCommandViewer: React.FC<SlashCommandViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  ...restProps
}) => {
  const { t } = useI18n();

  // 翻譯鍵
  const i18nKeys: MarkdownFileViewerProps<SlashCommandData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.slashCommands.sidebar.title' : 'template.detail.slashCommands.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.slashCommands.sidebar.searchPlaceholder' : 'template.detail.slashCommands.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.slashCommands.sidebar.empty' : 'template.detail.slashCommands.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.slashCommands.list.nameFallback' : 'template.detail.slashCommands.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.slashCommands.list.sizeLabel' : 'template.detail.slashCommands.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.slashCommands.detail.descriptionFallback' : 'template.detail.slashCommands.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.slashCommands.actions.copy' : 'template.detail.slashCommands.actions.copy',
      download: isEditable ? 'template.editor.slashCommands.actions.download' : 'template.detail.slashCommands.actions.download',
      add: isEditable ? 'template.editor.slashCommands.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.slashCommands.empty.title' : 'template.detail.slashCommands.empty.title',
      description: isEditable ? 'template.editor.slashCommands.empty.description' : 'template.detail.slashCommands.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.slashCommands.errors.copyFailed' : 'template.detail.slashCommands.errors.copyFailed',
    },
  };

  // 操作按鈕
  const actions: ItemActions<SlashCommandData> | undefined = React.useMemo(() => {
    if (!isEditable) return undefined;

    return {
      edit: onEdit ? {
        onClick: (item: SlashCommandData) => onEdit(item),
        label: t('template.editor.slashCommands.actions.edit'),
      } : undefined,
      delete: onDelete ? {
        onClick: (item: SlashCommandData) => onDelete(item),
        label: t('template.editor.slashCommands.actions.delete'),
      } : undefined,
    };
  }, [isEditable, onEdit, onDelete, t]);

  return (
    <MarkdownFileViewer<SlashCommandData>
      {...restProps}
      getItemIcon={() => Terminal}
      renderContent={(item) => (
        <MarkdownContent content={item.content} />
      )}
      getDownloadFileName={(item) => item.fileName}
      getDownloadFileType={() => 'md'}
      actions={actions}
      i18nKeys={i18nKeys}
      showAddButton={isEditable}
    />
  );
};

