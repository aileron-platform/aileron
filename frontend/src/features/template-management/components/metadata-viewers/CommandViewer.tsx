import React from 'react';
import { Terminal } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps, type ItemActions } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';
import type { CommandData } from './types';

export type { CommandData } from './types';

export interface CommandViewerProps extends Omit<MarkdownFileViewerProps<CommandData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: CommandData) => void;
  onDelete?: (item: CommandData) => void;
  onRefresh?: () => void | Promise<void>;
}

export const CommandViewer: React.FC<CommandViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  onRefresh,
  ...restProps
}) => {
  const { t } = useI18n();

  const i18nKeys: MarkdownFileViewerProps<CommandData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.commands.sidebar.title' : 'template.detail.commands.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.commands.sidebar.searchPlaceholder' : 'template.detail.commands.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.commands.sidebar.empty' : 'template.detail.commands.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.commands.list.nameFallback' : 'template.detail.commands.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.commands.list.sizeLabel' : 'template.detail.commands.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.commands.detail.descriptionFallback' : 'template.detail.commands.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.commands.actions.copy' : 'template.detail.commands.actions.copy',
      download: isEditable ? 'template.editor.commands.actions.download' : 'template.detail.commands.actions.download',
      add: isEditable ? 'template.editor.commands.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.commands.empty.title' : 'template.detail.commands.empty.title',
      description: isEditable ? 'template.editor.commands.empty.description' : 'template.detail.commands.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.commands.errors.copyFailed' : 'template.detail.commands.errors.copyFailed',
    },
  };

  const actions: ItemActions<CommandData> | undefined = React.useMemo(() => {
    if (!isEditable) return undefined;

    return {
      edit: onEdit ? {
        onClick: (item: CommandData) => onEdit(item),
        label: t('template.editor.commands.actions.edit'),
      } : undefined,
      delete: onDelete ? {
        onClick: (item: CommandData) => onDelete(item),
        label: t('template.editor.commands.actions.delete'),
      } : undefined,
    };
  }, [isEditable, onEdit, onDelete, t]);

  return (
    <MarkdownFileViewer<CommandData>
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
      onRefresh={onRefresh}
      refreshLabel={t('template.editor.fileManagement.sidebar.refresh')}
    />
  );
};
