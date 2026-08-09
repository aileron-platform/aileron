import type React from 'react';
import type {
  DocumentMetadataAdapter,
  DocumentTemplateResourceType,
  DocumentWorkflowDialogProps,
  DocumentWorkbenchRenderSurface,
} from '@/shared/components/document-workflow';

export type DocumentResourceScope = 'project' | 'user' | 'local' | 'plugin';

export interface DocumentResourceItem {
  id: string;
  workspaceId?: string;
  scope: DocumentResourceScope;
  title: string;
  path?: string;
  description?: string;
  content: string;
  size?: string;
  metadata?: Record<string, unknown>;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AvailableScope {
  scope: DocumentResourceScope;
  readOnly: boolean;
}

export interface ResourceListResult {
  items: DocumentResourceItem[];
  availableScopes: AvailableScope[];
  providerResourceGeneration?: number;
}

export interface DocumentSource {
  list(): Promise<ResourceListResult>;
  loadContent?(document: DocumentResourceItem): Promise<DocumentResourceItem>;
  create(document: DocumentResourceItem): Promise<DocumentResourceItem>;
  update(document: DocumentResourceItem): Promise<DocumentResourceItem>;
  move?(
    document: DocumentResourceItem,
    nextPath: string,
  ): Promise<DocumentResourceItem>;
  remove(document: DocumentResourceItem): Promise<void>;
}

export type DocumentDialogProps = DocumentWorkflowDialogProps<DocumentResourceItem>;

export interface DocumentWorkbenchConfig {
  metaKey: 'slash-commands' | 'output-styles' | 'subagents' | 'memory' | 'prompts' | 'rules';
  contentFormat?: 'markdown' | 'toml' | 'plain';
  createButtonLabel?: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  dialogTitle: string;
  scopeMode?: 'visible' | 'hidden';
  showRawToml?: boolean;
  hideCreate?: boolean;
}

export interface DocumentWorkbenchProps {
  documents: DocumentResourceItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate?: (
    document: DocumentResourceItem,
  ) => Promise<DocumentResourceItem>;
  onUpdate: (document: DocumentResourceItem) => Promise<DocumentResourceItem>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent?: React.ComponentType<DocumentDialogProps>;
  config: DocumentWorkbenchConfig;
  i18nNamespace: string;
  showSidebar?: boolean;
  metadataAdapter?: DocumentMetadataAdapter<DocumentResourceItem>;
  templateResourceType?: DocumentTemplateResourceType;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
  onRename?: (
    document: DocumentResourceItem,
    fileName: string,
  ) => Promise<DocumentResourceItem>;
  showSidebarSearch?: boolean;
  useShellSidebarHeader?: boolean;
  renderDocumentMeta?: (
    document: DocumentResourceItem,
  ) => React.ReactNode;
  readOnly?: boolean;
  renderSurface?: (surface: DocumentWorkbenchRenderSurface) => React.ReactNode;
}
