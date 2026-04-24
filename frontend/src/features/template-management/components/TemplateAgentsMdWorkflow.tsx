import React from 'react';
import { Copy, Download } from 'lucide-react';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useAgentsMd } from '../features/template-editor/hooks/useAgentsMd';

interface TemplateAgentsMdWorkflowProps {
  templateId?: string;
  initialContent?: string | null;
  onContentChange?: (content: string) => void;
  onSaveSuccess?: () => void;
  headerExtras?: React.ReactNode;
}

export const TemplateAgentsMdWorkflow: React.FC<TemplateAgentsMdWorkflowProps> = ({
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
  } = useAgentsMd({
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
        title: t('template.detail.agentsMd.actions.copySuccess.title'),
        description: t('template.detail.agentsMd.actions.copySuccess.description'),
      });
    } catch {
      toast({
        title: t('template.detail.agentsMd.actions.copyFailed.title'),
        description: t('template.detail.agentsMd.actions.copyFailed.description'),
        variant: 'destructive',
      });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = t('template.common.features.agentsMd');
    window.document.body.appendChild(anchor);
    anchor.click();
    window.document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    toast({
      title: t('template.detail.agentsMd.actions.downloadSuccess.title'),
      description: t('template.detail.agentsMd.actions.downloadSuccess.description'),
    });
  };

  return (
    <MarkdownDocumentShell
      title={t('template.common.features.agentsMd')}
      refreshLabel={t('common.refresh')}
      saveLabel={isSaving ? t('common.saving') : t('common.save')}
      runtimeLoadingLabel={t('template.editor.agentsMd.status.loading')}
      loadingLabel={t('template.editor.agentsMd.status.loading')}
      isRuntimeReady
      isLoading={isLoading}
      isSaving={isSaving}
      value={content}
      onChange={handleChange}
      onRefresh={loadContent}
      onSave={() => saveContent(content)}
      refreshDisabled={!templateId || isSaving}
      saveDisabled={isSaving || !hasUnsavedChanges}
      statusMessage={error ? <span className="text-destructive">{error}</span> : null}
      placeholder={t('template.editor.agentsMd.editor.placeholder')}
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
            {t('template.detail.agentsMd.actions.copy')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleDownload}
            disabled={isLoading}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('template.detail.agentsMd.actions.download')}
          </Button>
          {headerExtras}
        </>
      }
    />
  );
};

export default TemplateAgentsMdWorkflow;
