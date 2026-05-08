import React, { useMemo, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Edit,
  MoreHorizontal,
  Plus,
  Puzzle,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

export interface DocumentWorkflowDialogProps<TDocument> {
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: TDocument | null;
  onClose: () => void;
  onSubmit: (document: TDocument) => Promise<void> | void;
}

export interface DocumentWorkflowDocument {
  id: string;
  title: string;
  content: string;
  size?: string;
}

export interface DocumentWorkflowShellProps<TDocument extends DocumentWorkflowDocument> {
  documents: TDocument[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (document: TDocument) => Promise<TDocument>;
  onUpdate: (document: TDocument) => Promise<TDocument>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent: React.ComponentType<DocumentWorkflowDialogProps<TDocument>>;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  createButtonLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  totalLabel: string;
  refreshLabel: string;
  editLabel: string;
  copyLabel: string;
  downloadLabel: string;
  deleteLabel: string;
  loadingLabel: string;
  renderContent: (document: TDocument) => React.ReactNode;
  renderMeta?: (document: TDocument) => React.ReactNode;
  renderSelectedActions?: (document: TDocument) => React.ReactNode;
  canEdit?: (document: TDocument | null) => boolean;
  canDelete?: (document: TDocument | null) => boolean;
  onCopyContent?: (document: TDocument) => Promise<void> | void;
  onDownload?: (document: TDocument) => void;
  confirmDelete?: (document: TDocument) => boolean | Promise<boolean>;
}

export const DocumentWorkflowShell = <TDocument extends DocumentWorkflowDocument>({
  documents,
  selectedId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  isLoading = false,
  error = null,
  onRefresh,
  dialogComponent: DialogComponent,
  title,
  icon: Icon,
  createButtonLabel,
  emptyStateTitle,
  emptyStateDescription,
  totalLabel,
  refreshLabel,
  editLabel,
  copyLabel,
  downloadLabel,
  deleteLabel,
  loadingLabel,
  renderContent,
  renderMeta,
  renderSelectedActions,
  canEdit = () => true,
  canDelete = () => true,
  onCopyContent,
  onDownload,
  confirmDelete,
}: DocumentWorkflowShellProps<TDocument>) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeDocument, setActiveDocument] = useState<TDocument | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId],
  );

  const currentIndex = selectedDocument
    ? documents.findIndex((document) => document.id === selectedDocument.id)
    : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < documents.length - 1;

  const handleCreateRequest = () => {
    setDialogMode('create');
    setActiveDocument(null);
    setDialogOpen(true);
  };

  const handleEditRequest = () => {
    if (!selectedDocument || !canEdit(selectedDocument)) {
      return;
    }
    setDialogMode('edit');
    setActiveDocument(selectedDocument);
    setDialogOpen(true);
  };

  const handleRefresh = async () => {
    if (!onRefresh) return;
    try {
      setIsProcessing(true);
      await onRefresh();
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDialogSubmit = async (document: TDocument) => {
    try {
      setIsProcessing(true);
      if (dialogMode === 'create') {
        const created = await onCreate(document);
        onSelect(created?.id ?? document.id);
      } else {
        const updated = await onUpdate(document);
        onSelect(updated?.id ?? document.id);
      }
      setDialogOpen(false);
      setActiveDocument(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedDocument || !canDelete(selectedDocument)) {
      return;
    }
    const confirmed = confirmDelete ? await confirmDelete(selectedDocument) : true;
    if (!confirmed) {
      return;
    }
    try {
      setIsProcessing(true);
      await onDelete(selectedDocument.id);
      const nextDocuments = documents.filter((document) => document.id !== selectedDocument.id);
      onSelect(nextDocuments[0]?.id ?? null);
    } finally {
      setIsProcessing(false);
    }
  };

  const headerActions = (
    <div className="flex items-center gap-2">
      <Badge variant="secondary" className="text-[11px]">
        {totalLabel}
      </Badge>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={handleRefresh}
        disabled={isProcessing || isLoading || !onRefresh}
      >
        <RefreshCw className="mr-1 h-3 w-3" /> {refreshLabel}
      </Button>
      <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
        <Plus className="mr-1 h-3 w-3" /> {createButtonLabel}
      </Button>
    </div>
  );

  const renderEmptyState = () => (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="rounded-full bg-muted p-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-base font-medium text-foreground">{emptyStateTitle}</h3>
      <p className="text-sm text-muted-foreground">{emptyStateDescription}</p>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
          <Plus className="mr-1 h-4 w-4" /> {createButtonLabel}
        </Button>
        {onRefresh ? (
          <Button size="sm" variant="ghost" onClick={handleRefresh} disabled={isProcessing || isLoading}>
            <RefreshCw className="mr-1 h-4 w-4" /> {refreshLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col gap-0 overflow-hidden">
      {error ? (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}
      <div className="flex-1 overflow-hidden">
        {isLoading && documents.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {loadingLabel}
          </div>
        ) : documents.length === 0 ? (
          renderEmptyState()
        ) : selectedDocument ? (
          <div className="flex h-full flex-col">
            <FeatureHeader title={title} icon={Icon} actions={headerActions} />

            <div className="border-b border-border bg-background px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold text-foreground">{selectedDocument.title}</h3>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {renderSelectedActions ? renderSelectedActions(selectedDocument) : null}

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2"
                    onClick={() => canNavigatePrevious && onSelect(documents[currentIndex - 1].id)}
                    disabled={!canNavigatePrevious || isProcessing}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2"
                    onClick={() => canNavigateNext && onSelect(documents[currentIndex + 1].id)}
                    disabled={!canNavigateNext || isProcessing}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="h-7 px-2">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={handleEditRequest}
                        disabled={isProcessing || !canEdit(selectedDocument)}
                      >
                        <Edit className="mr-2 h-3 w-3" />
                        {editLabel}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => selectedDocument && onCopyContent?.(selectedDocument)}
                        disabled={isProcessing || !onCopyContent}
                      >
                        <Copy className="mr-2 h-3 w-3" />
                        {copyLabel}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => selectedDocument && onDownload?.(selectedDocument)}
                        disabled={isProcessing || !onDownload}
                      >
                        <Download className="mr-2 h-3 w-3" />
                        {downloadLabel}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={handleDelete}
                        className="text-destructive"
                        disabled={isProcessing || !canDelete(selectedDocument)}
                      >
                        <Trash2 className="mr-2 h-3 w-3" />
                        {deleteLabel}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>

              {renderMeta ? <div className="mt-1.5">{renderMeta(selectedDocument)}</div> : null}
            </div>

            <div className="flex-1 overflow-y-auto p-4">{renderContent(selectedDocument)}</div>
          </div>
        ) : (
          <div className="flex h-full flex-col bg-background">
            <FeatureHeader title={title} icon={Icon} actions={headerActions} />
            {renderEmptyState()}
          </div>
        )}
      </div>

      <DialogComponent
        open={dialogOpen}
        mode={dialogMode}
        initialValue={activeDocument}
        onClose={() => {
          setDialogOpen(false);
          setActiveDocument(null);
        }}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
};

DocumentWorkflowShell.displayName = 'DocumentWorkflowShell';

export const PluginSourceBadge: React.FC<{ label: string }> = ({ label }) => (
  <Badge variant="outline" className="flex items-center gap-1 text-[11px]">
    <Puzzle className="h-3 w-3" />
    {label}
  </Badge>
);

export default DocumentWorkflowShell;
