import React, { useMemo, useState } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Edit,
  MoreHorizontal,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  DocumentContentDetail,
  DocumentListSidebar,
  type DocumentListSidebarItem,
  DocumentMetadataDialog,
} from '@/shared/components/document-workflow';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import type { DocumentWorkbenchRenderSurface } from '@/shared/components/document-workflow';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { getDocumentWorkbenchIcon } from './documentIcons';
import {
  DocumentSourceBadge,
  normalizeDocumentSourceType,
  type DocumentSourceType,
} from './DocumentSourceBadge';
import type {
  DocumentDialogProps,
  DocumentResourceItem,
  DocumentWorkbenchProps,
} from './model/documentResourceTypes';
import { TomlContentViewer } from './TomlContentViewer';
import { useDocumentWorkbenchController } from './useDocumentWorkbenchController';

const logger = createLogger('DocumentWorkbench');

interface DocumentResourceSidebarItem extends DocumentListSidebarItem {
  document: DocumentResourceItem;
}

const documentSourceType = (document: DocumentResourceItem): DocumentSourceType => {
  const source = document.metadata?.source;
  return normalizeDocumentSourceType(typeof source === 'string' ? source : document.scope, document.scope);
};

export const DocumentWorkbench: React.FC<DocumentWorkbenchProps> = ({
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
  config,
  i18nNamespace,
  showSidebar = true,
  metadataAdapter,
  templateResourceType,
  onDocumentDirtyChange,
  documentSelectionBlocked,
  onRename,
  showSidebarSearch = false,
  useShellSidebarHeader = false,
  renderDocumentMeta,
  readOnly = false,
  renderSurface,
}) => {
  const { t } = useI18n();
  const [sidebarSearch, setSidebarSearch] = useState('');
  const {
    dialogOpen,
    dialogMode,
    activeDocument,
    createDialogOpen,
    renameDocument,
    metadataValue,
    setMetadataValue,
    detailModeByDocumentId,
    detailContentMode,
    detailSaving,
    inlineError,
    isProcessing,
    detailRef,
    documentWorkflowEnabled,
    scopeHidden,
    metadataCapabilities,
    metadataScopeOptions,
    selectedDocument,
    canNavigatePrevious,
    canNavigateNext,
    selectedDocumentActions,
    handleCreateRequest,
    handleEditRequest,
    handleDetailModeChange,
    handleMetadataCreate,
    handleRenameRequest,
    handleMetadataRename,
    handleRefresh,
    handleDialogSubmit,
    handleDelete,
    handleNavigatePrevious,
    handleNavigateNext,
    handleDetailCancel,
    handleDetailSave,
    handleContentSave,
    closeDialog,
    closeCreateDialog,
    closeRenameDialog,
  } = useDocumentWorkbenchController({
    documents,
    selectedId,
    onSelect,
    onCreate,
    onUpdate,
    onDelete,
    onRefresh,
    config,
    i18nNamespace,
    metadataAdapter,
    templateResourceType,
    onDocumentDirtyChange,
    onRename,
  });

  const Icon = useMemo(() => getDocumentWorkbenchIcon(config.metaKey), [config.metaKey]);

  const metaLabelKey = `${i18nNamespace}.documents.meta.${config.metaKey}.title`;
  const translatedMetaLabel = t(metaLabelKey);
  const title = translatedMetaLabel === metaLabelKey ? config.dialogTitle : translatedMetaLabel;

  const sidebarItems = useMemo<DocumentResourceSidebarItem[]>(
    () => documents.map((document) => ({
      id: document.id,
      label: document.title,
      description: typeof document.metadata?.fileName === 'string'
        ? document.metadata.fileName
        : document.title,
      document,
    })),
    [documents],
  );
  const headerActions = (
    <div className="flex items-center gap-2">
      <Badge variant="secondary" className="text-[11px]">
        {t(`${i18nNamespace}.documents.stats.total`, { count: documents.length })}
      </Badge>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={() => void handleRefresh()}
        disabled={isProcessing || isLoading || !onRefresh}
      >
        <RefreshCw className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
      </Button>
      {!config.hideCreate && !readOnly ? (
        <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
          <Plus className="mr-1 h-3 w-3" /> {config.createButtonLabel}
        </Button>
      ) : null}
    </div>
  );

  const sidebarHeaderActions = useShellSidebarHeader ? (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 w-7 p-0"
      title={t(`${i18nNamespace}.documents.actions.refresh`)}
      aria-label={t(`${i18nNamespace}.documents.actions.refresh`)}
      onClick={() => void handleRefresh()}
      disabled={isProcessing || isLoading || !onRefresh}
    >
      <RefreshCw className="h-4 w-4" />
    </Button>
  ) : undefined;

  const sidebar = showSidebar ? (
    <DocumentListSidebar<DocumentResourceSidebarItem>
      title={title}
      icon={Icon}
      items={sidebarItems}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={isLoading}
      showHeader={!useShellSidebarHeader}
      labels={{
        searchPlaceholder: t(`${i18nNamespace}.documents.sidebar.searchPlaceholder`),
        loading: t(`${i18nNamespace}.documents.sidebar.loading`),
        empty: t(`${i18nNamespace}.documents.sidebar.empty`),
        dirty: t(`${i18nNamespace}.documents.sidebar.dirty`),
      }}
      showSearch={showSidebarSearch}
      searchValue={sidebarSearch}
      onSearchChange={setSidebarSearch}
      getDirty={() => false}
      renderItemMeta={(item) => (
        <div className="flex flex-wrap items-center gap-1">
          {!scopeHidden ? (
            <DocumentSourceBadge
              source={{
                type: documentSourceType(item.document),
                label: t(`${i18nNamespace}.documents.scope.values.${item.document.metadata?.source ?? item.document.scope}`, {
                  defaultValue: String(item.document.metadata?.source ?? item.document.scope),
                }),
                pluginName: item.document.pluginName,
                marketplaceName: item.document.marketplaceName,
              }}
            />
          ) : null}
          {item.document.size ? (
            <Badge variant="outline" className="text-[11px]">
              {t(`${i18nNamespace}.documents.size.badge`, { size: item.document.size })}
            </Badge>
          ) : null}
        </div>
      )}
    />
  ) : undefined;

  const renderEmptyState = () => (
    <EmptyState
      icon={Icon}
      title={config.emptyStateTitle}
      description={config.emptyStateDescription}
      action={(
        <div className="flex items-center gap-2">
          {!config.hideCreate && !readOnly ? (
            <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
              <Plus className="mr-1 h-4 w-4" /> {config.createButtonLabel}
            </Button>
          ) : null}
          {onRefresh ? (
            <Button size="sm" variant="ghost" onClick={() => void handleRefresh()} disabled={isProcessing || isLoading}>
              <RefreshCw className="mr-1 h-4 w-4" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
            </Button>
          ) : null}
        </div>
      )}
    />
  );

  const renderDocumentContent = (document: DocumentResourceItem) => {
    const contentFormat = config.contentFormat ?? (document.metadata?.format as string);
    if (documentWorkflowEnabled && metadataAdapter) {
      const metadata = metadataAdapter.read(document);
      return (
        <DocumentContentDetail
          ref={detailRef}
          title={document.title}
          content={document.content}
          format={config.contentFormat ?? 'markdown'}
          metadata={[
            ...(!scopeHidden
              ? [{ label: t('shared.documentWorkflow.metadata.scope.label'), value: document.scope }]
              : []),
            ...(metadata.namespace
              ? [{ label: t('shared.documentWorkflow.metadata.namespace.label'), value: metadata.namespace }]
              : []),
          ]}
          initialMode={detailModeByDocumentId[document.id] ?? 'preview'}
          showHeader={false}
          onDirtyChange={onDocumentDirtyChange}
          onModeChange={handleDetailModeChange}
          onSave={(content) => handleContentSave(document, content)}
          readOnly={readOnly}
        />
      );
    }
    if (contentFormat === 'toml') {
      return (
        <TomlContentViewer
          content={document.content}
          i18nNamespace={i18nNamespace}
          showRaw={config.showRawToml ?? true}
        />
      );
    }
    if (contentFormat === 'plain') {
      return (
        <pre className="min-h-full overflow-auto rounded-md border border-border bg-muted/30 p-4 font-mono text-xs leading-5 text-foreground">
          {document.content}
        </pre>
      );
    }
    return <MarkdownContent content={document.content} />;
  };

  const isMarkdownEditing = documentWorkflowEnabled
    && detailContentMode === 'edit'
    && config.contentFormat === 'markdown';

  const mainArea = selectedDocument ? (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border bg-background px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <Icon className="h-5 w-5 text-primary" />
              <h3 className="truncate font-semibold text-foreground">{selectedDocument.title}</h3>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={handleNavigatePrevious}
              disabled={!canNavigatePrevious || isProcessing}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={handleNavigateNext}
              disabled={!canNavigateNext || isProcessing}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>

            {documentWorkflowEnabled && detailContentMode === 'edit' ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2"
                  onClick={handleDetailCancel}
                  disabled={detailSaving || isProcessing || readOnly}
                >
                  <X className="mr-1.5 h-3.5 w-3.5" />
                  {t('shared.documentWorkflow.detail.actions.cancel')}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="h-7 px-2"
                  onClick={handleDetailSave}
                  disabled={detailSaving || isProcessing}
                >
                  {detailSaving ? (
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Check className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  {t('shared.documentWorkflow.detail.actions.save')}
                </Button>
              </>
            ) : (
              <>
                {documentWorkflowEnabled && !readOnly ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-2"
                    onClick={handleEditRequest}
                    disabled={isProcessing || !selectedDocumentActions.canEdit}
                  >
                    <Edit className="mr-1.5 h-3.5 w-3.5" />
                    {t('shared.documentWorkflow.detail.actions.edit')}
                  </Button>
                ) : null}

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 px-2"
                      title={t('shared.documentWorkflow.metadata.actions.more')}
                      aria-label={t('shared.documentWorkflow.metadata.actions.more')}
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {!documentWorkflowEnabled && !readOnly ? (
                      <DropdownMenuItem onClick={handleEditRequest} disabled={isProcessing || !selectedDocumentActions.canEdit}>
                        <Edit className="mr-2 h-3 w-3" />
                        {t(`${i18nNamespace}.documents.actions.edit`)}
                      </DropdownMenuItem>
                    ) : null}
                    {documentWorkflowEnabled && !readOnly ? (
                      <DropdownMenuItem onClick={handleRenameRequest} disabled={isProcessing || !selectedDocumentActions.canEdit}>
                        <Edit className="mr-2 h-3 w-3" />
                        {t('shared.documentWorkflow.metadata.actions.rename')}
                      </DropdownMenuItem>
                    ) : null}
                    <DropdownMenuItem
                      onClick={() => {
                        void navigator.clipboard.writeText(selectedDocument.content).catch((err) => {
                          logger.error('copyToClipboardFailed', { error: err });
                        });
                      }}
                      disabled={isProcessing || !selectedDocumentActions.canCopy}
                    >
                      <Copy className="mr-2 h-3 w-3" />
                      {t(`${i18nNamespace}.documents.actions.copyContent`)}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        const blob = new Blob([selectedDocument.content], { type: 'text/plain' });
                        const url = URL.createObjectURL(blob);
                        const anchor = window.document.createElement('a');
                        anchor.href = url;
                        anchor.download = `${selectedDocument.title}.txt`;
                        window.document.body.appendChild(anchor);
                        anchor.click();
                        window.document.body.removeChild(anchor);
                        URL.revokeObjectURL(url);
                      }}
                      disabled={isProcessing || !selectedDocumentActions.canDownload}
                    >
                      <Download className="mr-2 h-3 w-3" />
                      {t(`${i18nNamespace}.documents.actions.download`)}
                    </DropdownMenuItem>
                    {!readOnly ? (
                    <DropdownMenuItem
                      onClick={() => void handleDelete()}
                      className="text-destructive"
                      disabled={isProcessing || !selectedDocumentActions.canDelete}
                    >
                      <Trash2 className="mr-2 h-3 w-3" />
                      {t(`${i18nNamespace}.documents.actions.delete`)}
                    </DropdownMenuItem>
                    ) : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </div>
        </div>

        {!scopeHidden
        || selectedDocument.metadata?.effective
        || selectedDocument.metadata?.overridden
        || selectedDocument.size
        || renderDocumentMeta ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {!scopeHidden ? (
              <DocumentSourceBadge
                source={{
                  type: documentSourceType(selectedDocument),
                  label: t(`${i18nNamespace}.documents.scope.values.${selectedDocument.metadata?.source ?? selectedDocument.scope}`, {
                    defaultValue: String(selectedDocument.metadata?.source ?? selectedDocument.scope),
                  }),
                  pluginName: selectedDocument.pluginName,
                  marketplaceName: selectedDocument.marketplaceName,
                }}
              />
            ) : null}
            {selectedDocument.metadata?.effective ? (
              <Badge variant="outline" className="text-[11px]">
                {t(`${i18nNamespace}.documents.status.effective`)}
              </Badge>
            ) : null}
            {selectedDocument.metadata?.overridden ? (
              <Badge variant="outline" className="text-[11px]">
                {t(`${i18nNamespace}.documents.status.overridden`)}
              </Badge>
            ) : null}
            {selectedDocument.size ? (
              <Badge variant="outline" className="text-[11px]">
                {t(`${i18nNamespace}.documents.size.badge`, { size: selectedDocument.size })}
              </Badge>
            ) : null}
            {renderDocumentMeta?.(selectedDocument)}
          </div>
        ) : null}
      </div>

      <div className={isMarkdownEditing
        ? 'flex min-h-0 flex-1 flex-col overflow-hidden'
        : 'flex-1 overflow-y-auto p-4'}>
        {documentSelectionBlocked ? (
          <Alert className="mb-3">
            <AlertDescription>{t('shared.documentWorkflow.detail.unsavedGuard')}</AlertDescription>
          </Alert>
        ) : null}
        {inlineError ? (
          <Alert className="mb-3" variant="destructive">
            <AlertDescription>{inlineError}</AlertDescription>
          </Alert>
        ) : null}
        {isMarkdownEditing ? (
          <div className="min-h-0 flex-1">
            {renderDocumentContent(selectedDocument)}
          </div>
        ) : renderDocumentContent(selectedDocument)}
      </div>
    </div>
  ) : renderEmptyState();

  const content = isLoading
    ? (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {t(`${i18nNamespace}.documents.loading`)}
      </div>
    )
    : (documents.length === 0 ? renderEmptyState() : mainArea);

  const navigatorRegion: DocumentWorkbenchRenderSurface['navigator'] = sidebar ? {
    content: ({ collapsed }) => collapsed ? null : (
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        {sidebar}
      </div>
    ),
    accessibleLabel: title,
    title,
    icon: Icon,
    actions: sidebarHeaderActions,
    header: {
      leading: <Icon className="h-4 w-4 shrink-0 text-sidebar-primary" />,
      title,
      actions: sidebarHeaderActions,
    },
  } : undefined;

  const surface: DocumentWorkbenchRenderSurface = {
    kind: 'regions',
    header: <FeatureHeader title={title} icon={Icon} actions={headerActions} />,
    navigator: navigatorRegion,
    main: {
      accessibleLabel: title,
      content: (
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {content}
          </div>
        </div>
      ),
    },
  };

  const rawContent = (
    <>
      {surface.header}
      {surface.navigator?.content({ collapsed: false })}
      {surface.main.content}
    </>
  );

  return (
    <>
      {error ? (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}
      {renderSurface ? renderSurface(surface) : rawContent}
      {DialogComponent ? (
        <DialogComponent
          open={dialogOpen}
          mode={dialogMode}
          initialValue={activeDocument}
          onClose={closeDialog}
          onSubmit={handleDialogSubmit}
          submitDisabled={readOnly}
        />
      ) : null}
      {documentWorkflowEnabled && metadataAdapter ? (
        <DocumentMetadataDialog
          open={createDialogOpen}
          mode="create"
          titleKey="shared.documentWorkflow.metadata.create.title"
          descriptionKey="shared.documentWorkflow.metadata.create.description"
          value={metadataValue}
          capabilities={metadataCapabilities ?? metadataAdapter.capabilities}
          scopeOptions={metadataScopeOptions}
          errorMessage={inlineError}
          submitting={isProcessing}
          submitDisabled={readOnly}
          onChange={setMetadataValue}
          onClose={closeCreateDialog}
          onSubmit={(value) => void handleMetadataCreate(value)}
        />
      ) : null}
      {documentWorkflowEnabled && metadataAdapter ? (
        <DocumentMetadataDialog
          open={Boolean(renameDocument)}
          mode="rename"
          titleKey="shared.documentWorkflow.metadata.rename.title"
          descriptionKey="shared.documentWorkflow.metadata.rename.description"
          value={metadataValue}
          capabilities={metadataCapabilities ?? metadataAdapter.capabilities}
          scopeOptions={metadataScopeOptions}
          errorMessage={inlineError}
          submitting={isProcessing}
          submitDisabled={readOnly}
          onChange={setMetadataValue}
          onClose={closeRenameDialog}
          onSubmit={(value) => void handleMetadataRename(value)}
        />
      ) : null}
    </>
  );
};

DocumentWorkbench.displayName = 'DocumentWorkbench';
