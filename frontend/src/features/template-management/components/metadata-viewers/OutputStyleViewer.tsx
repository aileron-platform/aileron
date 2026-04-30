import React, { useMemo } from 'react';
import { Palette } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';
import type { OutputStyleData } from './types';

export type { OutputStyleData } from './types';

export interface OutputStyleViewerProps extends Omit<MarkdownFileViewerProps<OutputStyleData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: OutputStyleData) => void;
  onDelete?: (item: OutputStyleData) => void;
  onRefresh?: () => void | Promise<void>;
}

export const OutputStyleViewer: React.FC<OutputStyleViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  onRefresh,
  ...restProps
}) => {
  const { t } = useI18n();

  const i18nKeys: MarkdownFileViewerProps<OutputStyleData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.outputStyle.sidebar.title' : 'template.detail.outputStyle.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.outputStyle.sidebar.searchPlaceholder' : 'template.detail.outputStyle.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.outputStyle.sidebar.empty' : 'template.detail.outputStyle.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.outputStyle.list.nameFallback' : 'template.detail.outputStyle.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.outputStyle.list.sizeLabel' : 'template.detail.outputStyle.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.outputStyle.detail.descriptionFallback' : 'template.detail.outputStyle.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.outputStyle.actions.copy' : 'template.detail.outputStyle.actions.copy',
      download: isEditable ? 'template.editor.outputStyle.actions.download' : 'template.detail.outputStyle.actions.download',
      add: isEditable ? 'template.editor.outputStyle.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.outputStyle.empty.title' : 'template.detail.outputStyle.empty.title',
      description: isEditable ? 'template.editor.outputStyle.empty.description' : 'template.detail.outputStyle.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.outputStyle.errors.copyFailed' : 'template.detail.outputStyle.errors.copyFailed',
    },
  };

  const getItemIcon = () => Palette;

  const renderContent = (item: OutputStyleData) => {
    return <MarkdownContent content={item.content} />;
  };

  const getDownloadFileName = (item: OutputStyleData) => item.fileName;

  const getDownloadFileType = () => 'text/markdown';

  const actions = useMemo(() => {
    return {
      edit: onEdit && isEditable ? {
        onClick: (item: OutputStyleData) => onEdit(item),
        label: t('template.editor.outputStyle.actions.edit'),
      } : undefined,
      delete: onDelete && isEditable ? {
        onClick: (item: OutputStyleData) => onDelete(item),
        label: t('template.editor.outputStyle.actions.delete'),
      } : undefined,
    };
  }, [isEditable, onEdit, onDelete, t]);

  return (
    <MarkdownFileViewer
      {...restProps}
      i18nKeys={i18nKeys}
      getItemIcon={getItemIcon}
      renderContent={renderContent}
      getDownloadFileName={getDownloadFileName}
      getDownloadFileType={getDownloadFileType}
      actions={actions}
      showAddButton={isEditable}
      onRefresh={onRefresh}
      refreshLabel={t('template.editor.fileManagement.sidebar.refresh')}
    />
  );
};

export default OutputStyleViewer;
