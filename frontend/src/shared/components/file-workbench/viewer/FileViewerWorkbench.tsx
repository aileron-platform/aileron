import type React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { getFileLanguage } from '../model/fileIconUtils';
import { formatFileSize } from '../model/fileTypeUtils';
import { FileViewerContent } from './FileViewerContent';
import { FileViewerTabStrip } from './FileViewerTabStrip';
import { FileViewerWorkbenchProvider } from './FileViewerWorkbenchContext';
import { FileViewerWorkbenchToolbar } from './FileViewerWorkbenchToolbar';
import type { FileViewerWorkbenchProps } from './types';
import { useFileViewerWorkbenchController } from './useFileViewerWorkbenchController';

export const FileViewerWorkbench: React.FC<FileViewerWorkbenchProps> = ({
  tabs,
  activeTabId,
  adapter,
  capabilities = {},
  statusMetadata,
  className,
  headerActions,
  hideChrome: hideChromeProp = false,
  readOnly = false,
  isExpanded,
  onExpandedChange,
  useViewportExpansion = true,
  isPathWritable,
  renderReadOnlyBadge,
  onOpenPath,
  onTextSelectionChange,
  onTabsChange,
  onActiveTabChange,
  onSplitTab,
  canSplitTab,
  onForeignTabDrop,
}) => {
  const { t } = useI18n();
  const hideChrome = hideChromeProp;
  const controller = useFileViewerWorkbenchController({
    tabs,
    activeTabId,
    adapter,
    capabilities,
    readOnly,
    isExpanded,
    onExpandedChange,
    isPathWritable,
    renderReadOnlyBadge,
    onTabsChange,
    onActiveTabChange,
    onSplitTab,
    canSplitTab,
    onForeignTabDrop,
  });
  const showToolbarSave = controller.canSave
    && Boolean(controller.activeTab)
    && !controller.toolbarFormatActions;
  const showEditorToolbar = Boolean(
    headerActions || controller.toolbarFormatActions || showToolbarSave,
  );

  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col bg-background',
        controller.effectiveExpanded && useViewportExpansion && 'fixed inset-0 z-[99990] h-screen w-screen',
        className,
      )}
    >
      <FileViewerTabStrip
        {...controller.tabStripProps}
        showTabBar={tabs.length > 0 && !hideChrome}
      />

      {tabs.length > 0 && !hideChrome && showEditorToolbar && (
        <FileViewerWorkbenchToolbar
          headerActions={headerActions}
          formatActions={controller.toolbarFormatActions}
          canSave={controller.canSave}
          activeTab={controller.activeTab}
          onSave={() => {
            if (controller.activeTab) void controller.saveTab(controller.activeTab);
          }}
        />
      )}

      <FileViewerWorkbenchProvider registerFormatActions={controller.registerFormatActions}>
        <div key={controller.activeTab?.id ?? 'empty'} className="min-h-0 flex-1 overflow-hidden">
          <FileViewerContent
            activeTab={controller.activeTab}
            adapter={adapter}
            capabilities={capabilities}
            canMutate={controller.canMutate}
            activeViewerOwnerKey={controller.activeViewerOwnerKey}
            codeEditorRef={controller.codeEditorRef}
            onOpenPath={onOpenPath}
            onTextSelectionChange={onTextSelectionChange}
            onActiveContentChange={controller.setActiveContent}
            onTabChange={controller.updateTab}
          />
        </div>
      </FileViewerWorkbenchProvider>

      {controller.activeTab && !hideChrome && (
        <div className="flex h-8 shrink-0 items-center gap-3 border-t border-border bg-muted/30 px-3 text-xs text-muted-foreground">
          <span>{getFileLanguage(controller.activeTab.name)}</span>
          <span>{t('shared.fileViewer.status.lineCount', { count: controller.stats.lines })}</span>
          <span>{formatFileSize(controller.stats.characters)}</span>
          <span>{statusMetadata?.encoding ?? 'UTF-8'}</span>
          <span>{statusMetadata?.lineEnding ?? 'LF'}</span>
          {controller.activeTab.isModified && <span className="text-primary">{t('shared.fileViewer.status.modified')}</span>}
          <div className="ml-auto" />
        </div>
      )}
    </div>
  );
};
