import React, { useMemo } from 'react';
import { Palette } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import MarkdownFileViewer, { type MarkdownFileViewerProps, type BaseItem } from './MarkdownFileViewer';
import { useI18n } from '@/shared/hooks/useI18n';

// OutputStyle 數據類型
export interface OutputStyleData extends BaseItem {}

// 屬性類型
export interface OutputStyleViewerProps extends Omit<MarkdownFileViewerProps<OutputStyleData>, 'i18nKeys' | 'getItemIcon' | 'renderContent' | 'getDownloadFileName' | 'getDownloadFileType'> {
  isEditable?: boolean;
  onEdit?: (item: OutputStyleData) => void;
  onDelete?: (item: OutputStyleData) => void;
}

export const OutputStyleViewer: React.FC<OutputStyleViewerProps> = ({
  isEditable = false,
  onEdit,
  onDelete,
  ...restProps
}) => {
  const { t } = useI18n();

  // 翻譯鍵
  const i18nKeys: MarkdownFileViewerProps<OutputStyleData>['i18nKeys'] = {
    sidebar: {
      title: isEditable ? 'template.editor.outputStyles.sidebar.title' : 'template.detail.outputStyles.sidebar.title',
      searchPlaceholder: isEditable ? 'template.editor.outputStyles.sidebar.searchPlaceholder' : 'template.detail.outputStyles.sidebar.searchPlaceholder',
      empty: isEditable ? 'template.editor.outputStyles.sidebar.empty' : 'template.detail.outputStyles.sidebar.empty',
    },
    list: {
      nameFallback: isEditable ? 'template.editor.outputStyles.list.nameFallback' : 'template.detail.outputStyles.list.nameFallback',
      sizeLabel: isEditable ? 'template.editor.outputStyles.list.sizeLabel' : 'template.detail.outputStyles.list.sizeLabel',
    },
    detail: {
      descriptionFallback: isEditable ? 'template.editor.outputStyles.detail.descriptionFallback' : 'template.detail.outputStyles.detail.descriptionFallback',
    },
    actions: {
      copy: isEditable ? 'template.editor.outputStyles.actions.copy' : 'template.detail.outputStyles.actions.copy',
      download: isEditable ? 'template.editor.outputStyles.actions.download' : 'template.detail.outputStyles.actions.download',
      add: isEditable ? 'template.editor.outputStyles.actions.add' : undefined,
    },
    empty: {
      title: isEditable ? 'template.editor.outputStyles.empty.title' : 'template.detail.outputStyles.empty.title',
      description: isEditable ? 'template.editor.outputStyles.empty.description' : 'template.detail.outputStyles.empty.description',
    },
    errors: {
      copyFailed: isEditable ? 'template.editor.outputStyles.errors.copyFailed' : 'template.detail.outputStyles.errors.copyFailed',
    },
  };

  // 圖標
  const getItemIcon = () => Palette;

  // 渲染內容
  const renderContent = (item: OutputStyleData) => {
    return <MarkdownContent content={item.content} />;
  };

  // 下載檔案名稱
  const getDownloadFileName = (item: OutputStyleData) => item.fileName;

  // 下載檔案類型
  const getDownloadFileType = () => 'text/markdown';

  // 動作配置
  const actions = useMemo(() => {
    return {
      edit: onEdit && isEditable ? {
        onClick: (item: OutputStyleData) => onEdit(item),
        label: t('template.editor.outputStyles.actions.edit'),
      } : undefined,
      delete: onDelete && isEditable ? {
        onClick: (item: OutputStyleData) => onDelete(item),
        label: t('template.editor.outputStyles.actions.delete'),
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
    />
  );
};

export default OutputStyleViewer;

