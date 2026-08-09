import type { FileViewerWorkbenchTab } from '../viewer/types';

export interface FileWorkbenchTabSource {
  id?: string;
  path: string;
  name: string;
  content: string;
  originalContent: string;
  isModified: boolean;
  isLoading?: boolean;
  error?: string | null;
  readable?: boolean;
  unreadableReason?: 'binary';
}

export const toFileWorkbenchTab = (tab: FileWorkbenchTabSource): FileViewerWorkbenchTab => ({
  id: tab.id ?? tab.path,
  path: tab.path,
  name: tab.name,
  content: tab.content,
  originalContent: tab.originalContent,
  isModified: tab.isModified,
  isLoading: tab.isLoading,
  error: tab.error,
  readable: tab.readable,
  unreadableReason: tab.unreadableReason,
});
