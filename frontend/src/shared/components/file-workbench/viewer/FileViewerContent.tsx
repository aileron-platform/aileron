import type React from 'react';
import { FileArchive, FileText } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { isImageFile } from '../model/fileTypeUtils';
import {
  isMarkdownFile,
  isMermaidFile,
} from '../model/fileIconUtils';
import { CodeTextEditor, type CodeTextEditorRef } from './CodeTextEditor';
import { ImageViewer } from './ImageViewer';
import { MarkdownViewer } from './MarkdownViewer';
import { MermaidViewer } from './MermaidViewer';
import type {
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchTab,
  FileViewerTextSelection,
} from './types';

interface FileViewerContentProps {
  activeTab: FileViewerWorkbenchTab | null;
  adapter: FileViewerWorkbenchAdapter;
  capabilities: FileViewerWorkbenchCapabilities;
  canMutate: boolean;
  activeViewerOwnerKey: string | null;
  codeEditorRef: React.RefObject<CodeTextEditorRef | null>;
  onOpenPath?: (path: string) => void;
  onTextSelectionChange?: (selection: FileViewerTextSelection) => void;
  onActiveContentChange: (content: string) => void;
  onTabChange: (tabId: string, updates: Partial<FileViewerWorkbenchTab>) => void;
}

export const FileViewerContent: React.FC<FileViewerContentProps> = ({
  activeTab,
  adapter,
  capabilities,
  canMutate,
  activeViewerOwnerKey,
  codeEditorRef,
  onOpenPath,
  onTextSelectionChange,
  onActiveContentChange,
  onTabChange,
}) => {
  const { t } = useI18n();

  if (!activeTab) {
    return (
      <EmptyState
        icon={FileText}
        title={t('shared.fileViewer.emptyState.title')}
      />
    );
  }

  if (activeTab.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {t('shared.fileViewer.loading')}
      </div>
    );
  }

  if (activeTab.error) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-destructive">
        {activeTab.error}
      </div>
    );
  }

  if (activeTab.readable === false && activeTab.unreadableReason === 'binary') {
    return (
      <EmptyState
        icon={FileArchive}
        title={t('shared.fileViewer.unavailable.binary.title')}
        description={t('shared.fileViewer.unavailable.binary.description')}
      />
    );
  }

  if (isImageFile(activeTab.name)) {
    return (
      <ImageViewer
        filePath={activeTab.path}
        fileName={activeTab.name}
        adapter={adapter}
        toolbarOwnerKey={activeViewerOwnerKey ?? undefined}
      />
    );
  }

  if (isMermaidFile(activeTab.name)) {
    return (
      <MermaidViewer
        content={activeTab.content}
        fileName={activeTab.name}
        toolbarOwnerKey={activeViewerOwnerKey ?? undefined}
      />
    );
  }

  if (isMarkdownFile(activeTab.name)) {
    return (
      <MarkdownViewer
        content={activeTab.content}
        fileName={activeTab.name}
        filePath={activeTab.path}
        readOnly={!canMutate}
        onReload={() => adapter.readFile(activeTab.path)}
        onContentChange={onActiveContentChange}
        onSave={adapter.saveFile
          ? async (content) => {
            await adapter.saveFile?.(activeTab.path, content);
            onTabChange(activeTab.id, {
              content,
              originalContent: content,
              isModified: false,
            });
          }
          : undefined}
        onOpenPath={onOpenPath}
        toolbarOwnerKey={activeViewerOwnerKey ?? undefined}
      />
    );
  }

  return (
    <CodeTextEditor
      ref={codeEditorRef}
      filePath={activeTab.path}
      fileName={activeTab.name}
      content={activeTab.content}
      readOnly={!canMutate}
      onContentChange={onActiveContentChange}
      onSelectionChange={onTextSelectionChange}
    />
  );
};
