import type { ReactNode } from 'react';

export interface FileViewerWorkbenchTab {
  id: string;
  path: string;
  name: string;
  content: string;
  originalContent: string;
  isModified: boolean;
  isLoading?: boolean;
  error?: string | null;
}

export interface FileViewerWorkbenchAdapter {
  readFile: (path: string) => Promise<string>;
  readBlob?: (path: string) => Promise<Blob>;
  saveFile?: (path: string, content: string) => Promise<void>;
  getDrawioViewerUrl?: (path: string, mode: 'view' | 'edit') => Promise<string>;
  saveDrawio?: (path: string, content: string) => Promise<void>;
  copyPath?: (path: string) => Promise<void>;
  revealInTree?: (path: string) => void;
}

export interface FileViewerWorkbenchCapabilities {
  canEdit?: boolean;
  canSave?: boolean;
  canReadBlob?: boolean;
  canPreviewDrawio?: boolean;
  canCopyPath?: boolean;
  canRevealInTree?: boolean;
  canCloseTabs?: boolean;
}

export interface FileViewerWorkbenchStatusMetadata {
  encoding?: string;
  lineEnding?: string;
}

export interface FileViewerWorkbenchContextValue {
  registerFormatActions: (node: ReactNode | null, registrationKey?: string, ownerKey?: string) => void;
}

export interface FileViewerWorkbenchProps {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  adapter: FileViewerWorkbenchAdapter;
  capabilities?: FileViewerWorkbenchCapabilities;
  statusMetadata?: FileViewerWorkbenchStatusMetadata;
  className?: string;
  headerActions?: ReactNode;
  hideChrome?: boolean;
  readOnly?: boolean;
  isExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  useViewportExpansion?: boolean;
  isPathWritable?: (path: string) => boolean;
  renderReadOnlyBadge?: (tab: FileViewerWorkbenchTab) => ReactNode;
  onOpenPath?: (path: string) => void;
  onTabsChange: (tabs: FileViewerWorkbenchTab[]) => void;
  onActiveTabChange: (tabId: string | null) => void;
}
