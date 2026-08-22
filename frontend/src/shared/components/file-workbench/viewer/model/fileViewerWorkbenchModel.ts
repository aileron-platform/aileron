import { isImageFile } from '../../model/fileTypeUtils';
import {
  isMarkdownFile,
  isMermaidFile,
} from '../../model/fileIconUtils';
import type { FileViewerWorkbenchTab } from '../types';

export const EMPTY_FORMAT_ACTIONS_KEY = '__empty__';
export const DEFAULT_FORMAT_ACTIONS_KEY = '__default__';
export const DEFAULT_FORMAT_ACTIONS_OWNER_KEY = '__default_owner__';
export const FILE_WORKBENCH_TAB_DND_MIME = 'application/x-aileron-file-workbench-tab';

export const getStats = (content: string) => ({
  lines: content.split('\n').length,
  characters: content.length,
});

export const getViewerOwnerKey = (tab: FileViewerWorkbenchTab | null): string | null => {
  if (!tab) return null;
  if (isImageFile(tab.name)) return `image:${tab.path}`;
  if (isMarkdownFile(tab.name)) return `markdown:${tab.path}`;
  if (isMermaidFile(tab.name)) return `mermaid:${tab.path}`;
  return null;
};

export const reorderTabs = (
  tabs: FileViewerWorkbenchTab[],
  draggedTabId: string,
  targetTabId: string,
  position: 'before' | 'after',
): FileViewerWorkbenchTab[] => {
  if (draggedTabId === targetTabId) return tabs;

  const draggedTab = tabs.find((tab) => tab.id === draggedTabId);
  if (!draggedTab) return tabs;

  const remainingTabs = tabs.filter((tab) => tab.id !== draggedTabId);
  const targetIndex = remainingTabs.findIndex((tab) => tab.id === targetTabId);
  if (targetIndex < 0) return tabs;

  const insertIndex = position === 'before' ? targetIndex : targetIndex + 1;
  const nextTabs = [
    ...remainingTabs.slice(0, insertIndex),
    draggedTab,
    ...remainingTabs.slice(insertIndex),
  ];

  return nextTabs.every((tab, index) => tab === tabs[index]) ? tabs : nextTabs;
};

// Shared by same-pane reordering and cross-pane drops: the insert side is
// derived from the pointer position relative to the hovered tab's midpoint.
export const getPointerDropPosition = (
  clientX: number,
  targetRect: Pick<DOMRect, 'left' | 'width'>,
): 'before' | 'after' => (
  clientX < targetRect.left + targetRect.width / 2 ? 'before' : 'after'
);
