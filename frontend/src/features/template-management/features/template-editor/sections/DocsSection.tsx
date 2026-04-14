import React, { useCallback } from 'react';
import MarkdownEditor from '@/shared/components/composite/MarkdownEditor';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeMd } from '../hooks/useClaudeMd';
import { Button } from '@/shared/components/ui/button';
import { Save } from 'lucide-react';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface DocsSectionProps {
  templateId?: string;
  documentation: string;
  claudeMd: string;
  onChange: (next: { documentation?: string; claudeMd?: string }) => void;
}

const DocsSection: React.FC<DocsSectionProps> = ({
  templateId,
  documentation,
  claudeMd: initialClaudeMd,
  onChange
}) => {
  const { t } = useI18n();
  const { reloadFromSource } = useTemplateManagementContext();
  const {
    content,
    isLoading,
    isSaving,
    error,
    loadContent,
    saveContent,
    setContent,
  } = useClaudeMd({
    templateId,
    initialContent: initialClaudeMd,
    onSuccess: reloadFromSource // 保存成功後重新載入模板列表
  });

  // 當本地內容變更時，通知父組件
  const handleChange = useCallback((newContent: string | undefined) => {
    if (newContent !== undefined) {
      setContent(newContent);
      onChange({ claudeMd: newContent });
    }
  }, [setContent, onChange]);

  // 處理手動儲存
  const handleSave = useCallback(async () => {
    if (templateId && content.trim()) {
      await saveContent(content);
    }
  }, [templateId, content, saveContent]);

  // 儲存按鈕組件
  const SaveButton = () => (
    <Button
      variant="default"
      size="sm"
      className="h-7 px-2 text-xs"
      onClick={handleSave}
      disabled={isSaving || !templateId || !content.trim()}
    >
      <Save className="mr-1 h-3 w-3" />
      {isSaving ? t('template.editor.docs.actions.saving') : t('template.editor.docs.actions.save')}
    </Button>
  );

  return (
    <div className="h-full flex flex-col">
      {/* 狀態指示器 */}
      {(isLoading || isSaving || error) && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            {isLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                {t('template.editor.claudeMd.status.loading')}
              </div>
            )}
            {isSaving && (
              <div className="flex items-center gap-2 text-sm text-blue-600">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                {t('template.editor.claudeMd.status.saving')}
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <span>{t('template.editor.claudeMd.status.error')}</span>
                <button
                  type="button"
                  onClick={loadContent}
                  className="text-xs underline hover:no-underline"
                >
                  {t('template.editor.claudeMd.actions.retry')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 編輯器 */}
      <div className="flex-1">
        <MarkdownEditor
          value={content}
          onChange={handleChange}
          placeholder={t('template.editor.claudeMd.editor.placeholder')}
          className="h-full border-0 rounded-none"
          toolbarExtras={<SaveButton />}
        />
      </div>
    </div>
  );
};

export default DocsSection;