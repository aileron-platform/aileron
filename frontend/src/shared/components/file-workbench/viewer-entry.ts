export {
  FileViewerWorkbench,
  FileFocusToolbar,
  FileEditor,
  CodeTextEditor,
  useFileViewerTabs,
  SharedImageViewer,
  SharedDrawioViewer,
  SharedMarkdownViewer,
  SharedMermaidViewer,
} from './viewer';

export {
  toFileWorkbenchTab,
} from './adapters';

export type {
  FileEditorProps,
  UseFileViewerTabsReturn,
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchProps,
  FileViewerWorkbenchStatusMetadata,
  FileViewerWorkbenchTab,
} from './viewer';

export type {
  FileWorkbenchTabSource,
} from './adapters';
