import type React from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  FolderTree,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  Redo2,
  RotateCcw,
  Save,
  SaveAll,
  Undo2,
  X,
} from 'lucide-react';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from '@/shared/components/ui/context-menu';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { getFileIcon } from '../model/fileIconUtils';
import type { CodeTextEditorRef } from './CodeTextEditor';
import type {
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchTab,
} from './types';

interface FileViewerTabStripProps {
  showTabBar: boolean;
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  activeTab: FileViewerWorkbenchTab | null;
  adapter: FileViewerWorkbenchAdapter;
  capabilities: FileViewerWorkbenchCapabilities;
  readOnly: boolean;
  effectiveExpanded: boolean;
  canMutate: boolean;
  canSave: boolean;
  canCloseTabs: boolean;
  showLeftScroll: boolean;
  showRightScroll: boolean;
  dropIndicator: { tabId: string; position: 'before' | 'after' } | null;
  tabScrollRef: React.RefObject<HTMLDivElement | null>;
  codeEditorRef: React.RefObject<CodeTextEditorRef | null>;
  isTabWritable: (tab: FileViewerWorkbenchTab | null) => boolean;
  renderReadOnlyBadge?: (tab: FileViewerWorkbenchTab) => React.ReactNode;
  onActiveTabChange: (tabId: string | null) => void;
  onSplitTab?: (tabId: string) => void;
  canSplitTab?: (tabId: string) => boolean;
  onCheckScroll: () => void;
  onScrollTabs: (direction: 'left' | 'right') => void;
  onCloseTab: (tabId: string) => void;
  onTabDragStart: (event: React.DragEvent, tabId: string) => void;
  onTabDragOver: (event: React.DragEvent, targetTabId: string) => void;
  onTabDrop: (event: React.DragEvent, targetTabId: string) => void;
  onTabDragEnd: () => void;
  onStripDragOver: (event: React.DragEvent) => void;
  onStripDrop: (event: React.DragEvent) => void;
  onStripDragLeave: (event: React.DragEvent) => void;
  onToggleExpanded: () => void;
  onSaveTab: (tab: FileViewerWorkbenchTab) => Promise<void>;
  onSaveAllTabs: () => Promise<void>;
  onRevertTab: (tab: FileViewerWorkbenchTab) => void;
  onRevertAllTabs: () => void;
  onCloseAllTabs: () => void;
  onCloseOtherTabs: (tabId: string) => void;
  onCloseTabsToRight: (tabId: string) => void;
  onCloseSavedTabs: () => void;
}

type TabMenuProps = Pick<
  FileViewerTabStripProps,
  | 'adapter'
  | 'capabilities'
  | 'readOnly'
  | 'canMutate'
  | 'isTabWritable'
  | 'onSplitTab'
  | 'canSplitTab'
  | 'onCloseTab'
  | 'onSaveTab'
  | 'onRevertTab'
  | 'onCloseAllTabs'
  | 'onCloseOtherTabs'
  | 'onCloseTabsToRight'
  | 'onCloseSavedTabs'
> & { tab: FileViewerWorkbenchTab };

const TabContextMenu = ({
  tab,
  adapter,
  capabilities,
  readOnly,
  canMutate,
  isTabWritable,
  onSplitTab,
  canSplitTab,
  onCloseTab,
  onSaveTab,
  onRevertTab,
  onCloseAllTabs,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseSavedTabs,
}: TabMenuProps) => {
  const { t } = useI18n();
  return (
    <ContextMenuContent className="w-56" collisionPadding={8}>
      <ContextMenuItem
        onSelect={() => { void onSaveTab(tab); }}
        disabled={!isTabWritable(tab) || readOnly || capabilities.canEdit === false
          || capabilities.canSave === false || !adapter.saveFile || !tab.isModified}
      >
        <Save className="h-4 w-4" aria-hidden="true" />
        {t('shared.fileViewer.tabContextMenu.save')}
      </ContextMenuItem>
      <ContextMenuItem
        onSelect={() => onRevertTab(tab)}
        disabled={!canMutate || !tab.isModified}
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        {t('shared.fileViewer.tabContextMenu.revert')}
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem onSelect={() => onCloseTab(tab.id)}>
        {t('shared.fileViewer.tabContextMenu.close')}
      </ContextMenuItem>
      {onSplitTab ? (
        <ContextMenuItem
          onSelect={() => onSplitTab(tab.id)}
          disabled={canSplitTab ? !canSplitTab(tab.id) : false}
        >
          {t('shared.fileViewer.tabContextMenu.splitOpen')}
        </ContextMenuItem>
      ) : null}
      <ContextMenuItem onSelect={() => onCloseOtherTabs(tab.id)}>
        {t('shared.fileViewer.tabContextMenu.closeOthers')}
      </ContextMenuItem>
      <ContextMenuItem onSelect={() => onCloseTabsToRight(tab.id)}>
        {t('shared.fileViewer.tabContextMenu.closeToTheRight')}
      </ContextMenuItem>
      <ContextMenuItem onSelect={onCloseSavedTabs}>
        {t('shared.fileViewer.tabContextMenu.closeSaved')}
      </ContextMenuItem>
      <ContextMenuItem onSelect={onCloseAllTabs}>
        {t('shared.fileViewer.tabContextMenu.closeAll')}
      </ContextMenuItem>
    </ContextMenuContent>
  );
};

type ToolbarMenuProps = Pick<
  FileViewerTabStripProps,
  | 'tabs'
  | 'activeTab'
  | 'adapter'
  | 'capabilities'
  | 'effectiveExpanded'
  | 'canSave'
  | 'codeEditorRef'
  | 'isTabWritable'
  | 'onToggleExpanded'
  | 'onSaveTab'
  | 'onSaveAllTabs'
  | 'onRevertTab'
  | 'onRevertAllTabs'
  | 'onCloseAllTabs'
>;

const ToolbarMenu = ({
  tabs,
  activeTab,
  adapter,
  capabilities,
  effectiveExpanded,
  canSave,
  codeEditorRef,
  isTabWritable,
  onToggleExpanded,
  onSaveTab,
  onSaveAllTabs,
  onRevertTab,
  onRevertAllTabs,
  onCloseAllTabs,
}: ToolbarMenuProps) => {
  const { t } = useI18n();
  return (
    <DropdownMenuContent align="end" collisionPadding={8} className="w-56">
      {canSave && activeTab ? (
        <>
          <DropdownMenuItem
            onSelect={() => { void onSaveTab(activeTab); }}
            disabled={!activeTab.isModified}
          >
            <Save className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
            {t('shared.fileViewer.toolbar.save')}
            <kbd className="ml-auto text-[10px] text-muted-foreground">Ctrl+S</kbd>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => { void onSaveAllTabs(); }}
            disabled={!tabs.some((tab) => tab.isModified && isTabWritable(tab))}
          >
            <Save className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
            {t('shared.fileViewer.toolbar.saveAll')}
            <kbd className="ml-auto text-[10px] text-muted-foreground">Ctrl+Shift+S</kbd>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => onRevertTab(activeTab)}
            disabled={!activeTab.isModified}
          >
            <RotateCcw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
            {t('shared.fileViewer.toolbar.revert')}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={onRevertAllTabs}
            disabled={!tabs.some((tab) => tab.isModified && isTabWritable(tab))}
          >
            <RotateCcw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
            {t('shared.fileViewer.toolbar.revertAll')}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
        </>
      ) : null}
      <DropdownMenuItem onSelect={onToggleExpanded} disabled={!activeTab}>
        {effectiveExpanded
          ? <Minimize2 className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
          : <Maximize2 className="mr-2 h-3.5 w-3.5" aria-hidden="true" />}
        {effectiveExpanded
          ? t('shared.fileViewer.toolbar.collapse')
          : t('shared.fileViewer.toolbar.expand')}
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={() => codeEditorRef.current?.undo()} disabled={!activeTab}>
        <Undo2 className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        {t('shared.fileViewer.toolbar.undo')}
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={() => codeEditorRef.current?.redo()} disabled={!activeTab}>
        <Redo2 className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        {t('shared.fileViewer.toolbar.redo')}
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem
        onSelect={() => { if (activeTab) void adapter.copyPath?.(activeTab.path); }}
        disabled={!activeTab || capabilities.canCopyPath === false || !adapter.copyPath}
      >
        <Copy className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        {t('shared.fileViewer.toolbar.copyPath')}
      </DropdownMenuItem>
      <DropdownMenuItem
        onSelect={() => { if (activeTab) adapter.revealInTree?.(activeTab.path); }}
        disabled={!activeTab || capabilities.canRevealInTree === false || !adapter.revealInTree}
      >
        <FolderTree className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        {t('shared.fileViewer.toolbar.revealInTree')}
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem onSelect={onCloseAllTabs}>
        <X className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        {t('shared.fileViewer.toolbar.closeAll')}
      </DropdownMenuItem>
      {canSave ? (
        <DropdownMenuItem onSelect={() => { void onSaveAllTabs().then(onCloseAllTabs); }}>
          <SaveAll className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
          {t('shared.fileViewer.toolbar.saveAndCloseAll')}
        </DropdownMenuItem>
      ) : null}
    </DropdownMenuContent>
  );
};

export const FileViewerTabStrip: React.FC<FileViewerTabStripProps> = ({
  showTabBar,
  tabs,
  activeTabId,
  activeTab,
  adapter,
  capabilities,
  readOnly,
  effectiveExpanded,
  canMutate,
  canSave,
  canCloseTabs,
  showLeftScroll,
  showRightScroll,
  dropIndicator,
  tabScrollRef,
  codeEditorRef,
  isTabWritable,
  renderReadOnlyBadge,
  onActiveTabChange,
  onSplitTab,
  canSplitTab,
  onCheckScroll,
  onScrollTabs,
  onCloseTab,
  onTabDragStart,
  onTabDragOver,
  onTabDrop,
  onTabDragEnd,
  onStripDragOver,
  onStripDrop,
  onStripDragLeave,
  onToggleExpanded,
  onSaveTab,
  onSaveAllTabs,
  onRevertTab,
  onRevertAllTabs,
  onCloseAllTabs,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseSavedTabs,
}) => {
  const { t } = useI18n();

  return showTabBar ? (
    <div className="relative flex h-10 shrink-0 border-b border-border bg-card">
      <div className="relative flex min-w-0 flex-1">
        {showLeftScroll ? (
          <button
            type="button"
            className="absolute left-0 top-0 z-20 flex h-full w-7 items-center justify-center border-r border-border bg-card/95 text-foreground shadow-sm transition-colors hover:bg-muted"
            onClick={() => onScrollTabs('left')}
            aria-label={t('shared.fileViewer.tabs.scrollLeft')}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}

        <div
          ref={tabScrollRef}
          role="tablist"
          className="flex min-w-0 flex-1 overflow-x-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-muted-foreground/20"
          style={{ scrollbarWidth: 'thin' }}
          onScroll={onCheckScroll}
          onDragOver={onStripDragOver}
          onDrop={onStripDrop}
          onDragLeave={onStripDragLeave}
        >
          {tabs.map((tab) => (
            <ContextMenu key={tab.id}>
              <ContextMenuTrigger asChild>
                <div
                  draggable
                  role="tab"
                  tabIndex={activeTabId === tab.id ? 0 : -1}
                  aria-selected={activeTabId === tab.id}
                  data-drop-position={dropIndicator?.tabId === tab.id ? dropIndicator.position : undefined}
                  onClick={() => onActiveTabChange(tab.id)}
                  onDragStart={(event) => onTabDragStart(event, tab.id)}
                  onDragOver={(event) => onTabDragOver(event, tab.id)}
                  onDrop={(event) => onTabDrop(event, tab.id)}
                  onDragEnd={onTabDragEnd}
                  className={cn(
                    'relative flex h-full min-w-0 flex-shrink-0 cursor-pointer items-center border-r border-border outline-none transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                    activeTabId === tab.id
                      ? 'border-b-2 border-b-primary bg-background text-foreground'
                      : 'text-muted-foreground',
                  )}
                >
                  {dropIndicator?.tabId === tab.id ? (
                    <span
                      aria-hidden="true"
                      className={cn(
                        'pointer-events-none absolute bottom-1 top-1 z-10 w-0.5 rounded-full bg-primary shadow-sm',
                        dropIndicator.position === 'before' ? 'left-0' : 'right-0',
                      )}
                    />
                  ) : null}
                  <div className="flex h-full min-w-0 items-center px-2.5">
                    <span className="mr-1.5 shrink-0">{getFileIcon(tab.name)}</span>
                    <span className="max-w-28 truncate text-sm" title={tab.path}>{tab.name}</span>
                    {!isTabWritable(tab) && renderReadOnlyBadge ? (
                      <span className="ml-1.5 shrink-0">{renderReadOnlyBadge(tab)}</span>
                    ) : null}
                    {tab.isModified ? (
                      <span
                        className="ml-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                        title={t('shared.fileViewer.status.modified')}
                      />
                    ) : null}
                  </div>
                  {canCloseTabs ? (
                    <button
                      type="button"
                      draggable={false}
                      className="h-full px-1.5 text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                      title={t('shared.fileViewer.tabs.close')}
                      aria-label={t('shared.fileViewer.tabs.close')}
                      onDragStart={(event) => event.stopPropagation()}
                      onClick={(event) => {
                        event.stopPropagation();
                        onCloseTab(tab.id);
                      }}
                    >
                      <X className="h-3 w-3" aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              </ContextMenuTrigger>
              <TabContextMenu
                tab={tab}
                adapter={adapter}
                capabilities={capabilities}
                readOnly={readOnly}
                canMutate={canMutate && isTabWritable(tab)}
                isTabWritable={isTabWritable}
                onSplitTab={onSplitTab}
                canSplitTab={canSplitTab}
                onCloseTab={onCloseTab}
                onSaveTab={onSaveTab}
                onRevertTab={onRevertTab}
                onCloseAllTabs={onCloseAllTabs}
                onCloseOtherTabs={onCloseOtherTabs}
                onCloseTabsToRight={onCloseTabsToRight}
                onCloseSavedTabs={onCloseSavedTabs}
              />
            </ContextMenu>
          ))}
        </div>

        {showRightScroll ? (
          <button
            type="button"
            className="absolute right-0 top-0 z-20 flex h-full w-7 items-center justify-center border-l border-border bg-card/95 text-foreground shadow-sm transition-colors hover:bg-muted"
            onClick={() => onScrollTabs('right')}
            aria-label={t('shared.fileViewer.tabs.scrollRight')}
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1 border-l border-border bg-card px-1.5" data-testid="file-viewer-tabbar-actions">
        <button
          type="button"
          className="flex h-8 items-center justify-center rounded px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onToggleExpanded}
          title={effectiveExpanded ? t('shared.fileViewer.toolbar.collapse') : t('shared.fileViewer.toolbar.expand')}
          aria-label={effectiveExpanded ? t('shared.fileViewer.toolbar.collapse') : t('shared.fileViewer.toolbar.expand')}
          disabled={!activeTab}
        >
          {effectiveExpanded
            ? <Minimize2 className="h-3.5 w-3.5" aria-hidden="true" />
            : <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />}
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex h-8 items-center justify-center rounded px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title={t('shared.fileViewer.toolbar.more')}
              aria-label={t('shared.fileViewer.toolbar.more')}
            >
              <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <ToolbarMenu
            tabs={tabs}
            activeTab={activeTab}
            adapter={adapter}
            capabilities={capabilities}
            effectiveExpanded={effectiveExpanded}
            canSave={canSave}
            codeEditorRef={codeEditorRef}
            isTabWritable={isTabWritable}
            onToggleExpanded={onToggleExpanded}
            onSaveTab={onSaveTab}
            onSaveAllTabs={onSaveAllTabs}
            onRevertTab={onRevertTab}
            onRevertAllTabs={onRevertAllTabs}
            onCloseAllTabs={onCloseAllTabs}
          />
        </DropdownMenu>
      </div>
    </div>
  ) : null;
};
