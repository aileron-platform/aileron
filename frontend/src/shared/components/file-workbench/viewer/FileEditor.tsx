import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Copy, Download } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { getFileIcon } from '@/shared/utils/fileIconUtils';
import { cn } from '@/shared/utils/cn';
import { FileFocusToolbar } from './FileFocusToolbar';
import { FileViewerWorkbench } from './FileViewerWorkbench';
import type { FileViewerWorkbenchAdapter, FileViewerWorkbenchTab } from './types';

const logger = createLogger('FileEditor');

export interface FileEditorProps {
  fileName: string;
  filePath: string;
  fileContent: string;
  fileIcon?: React.ReactNode;
  readOnly?: boolean;
  onSave?: (content: string) => Promise<void>;
  onContentChange?: (content: string) => void;
  isLoading?: boolean;
  isSaving?: boolean;
  className?: string;
}

const buildSingleFileTab = ({
  fileName,
  filePath,
  content,
  originalContent,
  isModified,
  isLoading,
}: {
  fileName: string;
  filePath: string;
  content: string;
  originalContent: string;
  isModified: boolean;
  isLoading: boolean;
}): FileViewerWorkbenchTab => ({
  id: filePath,
  path: filePath,
  name: fileName,
  content,
  originalContent,
  isModified,
  isLoading,
});

export const FileEditor: React.FC<FileEditorProps> = ({
  fileName,
  filePath,
  fileContent,
  fileIcon,
  readOnly = false,
  onSave,
  onContentChange,
  isLoading = false,
  isSaving = false,
  className,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const [content, setContent] = useState(fileContent);
  const [originalContent, setOriginalContent] = useState(fileContent);
  const [isExpanded, setIsExpanded] = useState(false);
  const previousFilePathRef = useRef(filePath);

  useEffect(() => {
    const filePathChanged = previousFilePathRef.current !== filePath;
    if (filePathChanged) {
      previousFilePathRef.current = filePath;
      setContent(fileContent);
      setOriginalContent(fileContent);
      setIsExpanded(false);
      return;
    }

    if (content === originalContent && fileContent !== originalContent) {
      setContent(fileContent);
      setOriginalContent(fileContent);
    }
  }, [content, fileContent, filePath, originalContent]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: t('common.fileEditor.copy.success'),
        description: t('common.fileEditor.copy.successDesc'),
      });
    } catch (error) {
      logger.error('Failed to copy file content', { error });
      toast({
        title: t('common.fileEditor.copy.error'),
        variant: 'destructive',
      });
    }
  }, [content, t, toast]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    toast({
      title: t('common.fileEditor.download.success'),
      description: t('common.fileEditor.download.successDesc', { name: fileName }),
    });
  }, [content, fileName, t, toast]);

  const adapter = useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async () => content,
    saveFile: onSave
      ? async (_path, nextContent) => {
        try {
          await onSave(nextContent);
          setOriginalContent(nextContent);
          toast({
            title: t('common.fileEditor.save.success'),
            description: t('common.fileEditor.save.successDesc', { name: fileName }),
          });
        } catch (error) {
          logger.error('Failed to save file', { error });
          toast({
            title: t('common.fileEditor.save.error'),
            description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
            variant: 'destructive',
          });
          throw error;
        }
      }
      : undefined,
  }), [content, fileName, onSave, t, toast]);

  const tab = useMemo(() => buildSingleFileTab({
    fileName,
    filePath,
    content,
    originalContent,
    isModified: content !== originalContent,
    isLoading,
  }), [content, fileName, filePath, isLoading, originalContent]);

  const handleTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextTab = nextTabs[0];
    if (!nextTab) {
      return;
    }

    setContent(nextTab.content);
    setOriginalContent(nextTab.originalContent);
    onContentChange?.(nextTab.content);
  }, [onContentChange]);

  const headerActions = (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-full w-8 rounded-none text-muted-foreground hover:text-foreground"
        onClick={() => void handleCopy()}
        title={t('common.fileEditor.actions.copy')}
        aria-label={t('common.fileEditor.actions.copy')}
        disabled={isLoading}
      >
        <Copy className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-full w-8 rounded-none text-muted-foreground hover:text-foreground"
        onClick={handleDownload}
        title={t('common.fileEditor.actions.download')}
        aria-label={t('common.fileEditor.actions.download')}
        disabled={isLoading}
      >
        <Download className="h-3.5 w-3.5" />
      </Button>
    </>
  );

  return (
    <FileViewerWorkbench
      tabs={[tab]}
      activeTabId={filePath}
      adapter={adapter}
      capabilities={{
        canEdit: !isSaving,
        canSave: Boolean(onSave) && !isSaving,
        canCopyPath: false,
        canRevealInTree: false,
        canCloseTabs: false,
      }}
      className={cn('h-full', className)}
      headerActions={headerActions}
      readOnly={readOnly}
      isExpanded={isExpanded}
      onExpandedChange={setIsExpanded}
      hideChromeWhenExpanded
      renderFocusToolbar={({ actions, icon, metadata, subtitle, title }) => (
        <FileFocusToolbar
          icon={icon ?? fileIcon ?? getFileIcon(fileName)}
          title={title}
          subtitle={subtitle}
          metadata={metadata}
          actions={actions}
          exitLabel={t('shared.fileViewer.toolbar.collapse')}
          onExit={() => setIsExpanded(false)}
        />
      )}
      onTabsChange={handleTabsChange}
      onActiveTabChange={() => undefined}
    />
  );
};

FileEditor.displayName = 'FileEditor';

export default FileEditor;
