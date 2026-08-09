export { FileViewerWorkbench } from './viewer/FileViewerWorkbench';
export { CodeTextEditor } from './viewer/CodeTextEditor';
export { useFileViewerTabs } from './viewer/useFileViewerTabs';
export { useManagedDocumentWorkbenchTabs } from './viewer/useManagedDocumentWorkbenchTabs';

export {
  FileViewerWorkbenchSplitView,
} from './viewer/FileViewerWorkbenchSplitView';

export type {
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchProps,
  FileViewerWorkbenchStatusMetadata,
  FileViewerWorkbenchTab,
  FileViewerTextSelection,
} from './viewer/types';

export type {
  ManagedDocumentWorkbenchAdapter,
  UseManagedDocumentWorkbenchTabsOptions,
  UseManagedDocumentWorkbenchTabsReturn,
} from './viewer/useManagedDocumentWorkbenchTabs';

export type {
  FileWorkbenchPane,
} from './viewer/FileViewerWorkbenchSplitView';
