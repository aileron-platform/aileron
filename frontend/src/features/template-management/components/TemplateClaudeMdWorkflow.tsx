import React from 'react';
import { Copy, Download } from 'lucide-react';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeMd } from '../features/template-editor/hooks/useClaudeMd';

interface TemplateClaudeMdWorkflowProps {
  templateId?: string;
  initialContent?: string | null;
  onContentChange?: (content: string) => void;
  onSaveSuccess?: () => void;
  headerExtras?: React.ReactNode;
}

export const TemplateClaudeMdWorkflow: React.FC<TemplateClaudeMdWorkflowProps> = ({
  templateId,
  initialContent,
  onContentChange,
  onSaveSuccess,
  headerExtras,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const {
    content,
    hasUnsavedChanges,
    isLoading,
    isSaving,
    error,
    loadContent,
    saveContent,
    setContent,
  } = useClaudeMd({
    templateId,
    initialContent: initialContent ?? '',
    onSuccess: onSaveSuccess,
  });

  const handleChange = (nextContent: string) => {
    setContent(nextContent);
    onContentChange?.(nextContent);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: t('template.detail.claudeMd.actions.copySuccess.title'),
        description: t('template.detail.claudeMd.actions.copySuccess.description'),
      });
    } catch {
      toast({
        title: t('template.detail.claudeMd.actions.copyFailed.title'),
        description: t('template.detail.claudeMd.actions.copyFailed.description'),
        variant: 'destructive',
      });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = t('template.detail.claudeMd.downloadFileName');
    window.document.body.appendChild(anchor);
    anchor.click();
    window.document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    toast({
      title: t('template.detail.claudeMd.actions.downloadSuccess.title'),
      description: t('template.detail.claudeMd.actions.downloadSuccess.description'),
    });
  };

  return (
    <MarkdownDocumentShell
      title={t('template.detail.claudeMd.header.title')}
      refreshLabel={t('common.refresh')}
      saveLabel={isSaving ? t('common.saving') : t('common.save')}
      runtimeLoadingLabel={t('template.editor.claudeMd.status.loading')}
      loadingLabel={t('template.editor.claudeMd.status.loading')}
      isRuntimeReady
      isLoading={isLoading}
      isSaving={isSaving}
      value={content}
      onChange={handleChange}
      onRefresh={loadContent}
      onSave={() => saveContent(content)}
      refreshDisabled={!templateId || isSaving}
      saveDisabled={!templateId || isSaving || !hasUnsavedChanges}
      statusMessage={error ? <span className="text-destructive">{error}</span> : null}
      placeholder={t('template.editor.claudeMd.editor.placeholder')}
      headerExtras={
        <>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleCopy}
            disabled={isLoading}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('template.detail.claudeMd.actions.copy')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleDownload}
            disabled={isLoading}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('template.detail.claudeMd.actions.download')}
          </Button>
          {headerExtras}
        </>
      }
    />
  );
};

export default TemplateClaudeMdWorkflow;
