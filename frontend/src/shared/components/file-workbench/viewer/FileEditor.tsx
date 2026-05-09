import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { cn } from '@/shared/utils/cn';
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
      readOnly={readOnly}
      isExpanded={isExpanded}
      onExpandedChange={setIsExpanded}
      onTabsChange={handleTabsChange}
      onActiveTabChange={() => undefined}
    />
  );
};

FileEditor.displayName = 'FileEditor';

export default FileEditor;
