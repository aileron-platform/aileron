import React, { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Edit,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  MultiDocumentEditorShell,
  MultiDocumentSidebar,
  type MultiDocumentSidebarItem,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import type { AgentDocument } from '../types';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import {
  AgentSettingsSourceBadge,
  normalizeAgentSettingsSourceType,
  type AgentSettingsSourceType,
} from './SettingsSourcePrimitives';

const logger = createLogger('DocumentPage');

export type DocumentDialogProps = DocumentWorkflowDialogProps<AgentDocument>;

export interface DocumentPageConfig {
  metaKey: 'slash-commands' | 'output-styles' | 'subagents' | 'memory' | 'prompts';
  contentFormat?: 'markdown' | 'toml';
  createButtonLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  dialogTitle: string;
  hideScopeBadge?: boolean;
  showRawToml?: boolean;
}

export interface DocumentPageProps {
  documents: AgentDocument[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (document: AgentDocument) => Promise<AgentDocument>;
  onUpdate: (document: AgentDocument) => Promise<AgentDocument>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent: React.ComponentType<DocumentDialogProps>;
  config: DocumentPageConfig;
  i18nNamespace?: string;
  showSidebar?: boolean;
}

interface WorkspaceDocumentSidebarItem extends MultiDocumentSidebarItem {
  document: AgentDocument;
}

const documentSourceType = (document: AgentDocument): AgentSettingsSourceType => {
  const source = document.metadata?.source;
  return normalizeAgentSettingsSourceType(typeof source === 'string' ? source : document.scope, document.scope);
};

const TomlContentView: React.FC<{ content: string; i18nNamespace: string; showRaw: boolean }> = ({
  content,
  i18nNamespace,
  showRaw,
}) => {
  const { t } = useI18n();
  const [rawExpanded, setRawExpanded] = useState(false);
  const getTomlLabel = (key: 'description' | 'prompt' | 'developerInstructions' | 'raw') => {
    const namespaceKey = `${i18nNamespace}.documents.toml.${key}`;
    const translated = t(namespaceKey);
    return translated === namespaceKey
      ? t(`workspace.agentSettings.common.documents.toml.${key}`)
      : translated;
  };

  const parsed = useMemo(() => {
    try {
      const descMatch = content.match(/^description\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMatch = content.match(/^prompt\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMultiMatch = content.match(/^prompt\s*=\s*"""([\s\S]*?)"""/m);
      const instructionsMatch = content.match(/^developer_instructions\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const instructionsMultiMatch = content.match(/^developer_instructions\s*=\s*"""([\s\S]*?)"""/m);

      const description = descMatch ? descMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null;
      const prompt = promptMultiMatch
        ? promptMultiMatch[1]
        : (promptMatch ? promptMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);
      const developerInstructions = instructionsMultiMatch
        ? instructionsMultiMatch[1]
        : (instructionsMatch ? instructionsMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);

      return { description, prompt, developerInstructions };
    } catch {
      return { description: null, prompt: null, developerInstructions: null };
    }
  }, [content]);
  const hasParsedFields = Boolean(parsed.description || parsed.prompt || parsed.developerInstructions);
  const showRawFallback = !showRaw && !hasParsedFields;

  return (
    <div className="space-y-4">
      {parsed.description ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('description')}
          </h4>
          <p className="text-sm text-foreground">{parsed.description}</p>
        </div>
      ) : null}

      {parsed.prompt ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('prompt')}
          </h4>
          <MarkdownContent content={parsed.prompt} />
        </div>
      ) : null}

      {parsed.developerInstructions ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('developerInstructions')}
          </h4>
          <MarkdownContent content={parsed.developerInstructions} />
        </div>
      ) : null}

      {showRaw ? (
        <div className="rounded-lg border border-border">
          <button
            type="button"
            className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50"
            onClick={() => setRawExpanded(!rawExpanded)}
          >
            <ChevronDown className={`h-4 w-4 transition-transform ${rawExpanded ? 'rotate-0' : '-rotate-90'}`} />
            {getTomlLabel('raw')}
          </button>
          {rawExpanded ? (
            <div className="border-t border-border p-4">
              <pre className="whitespace-pre-wrap text-xs font-mono text-foreground">{content}</pre>
            </div>
          ) : null}
        </div>
      ) : null}
      {showRawFallback ? (
        <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/30 p-4 text-xs font-mono text-foreground">
          {content}
        </pre>
      ) : null}
    </div>
  );
};

export const DocumentPage: React.FC<DocumentPageProps> = ({
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
  i18nNamespace = 'workspace.agentSettings.common',
  showSidebar = true,
}) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeDocument, setActiveDocument] = useState<AgentDocument | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const Icon = useMemo(() => {
    switch (config.metaKey) {
      case 'slash-commands':
        return CLAUDE_CODE_ICONS['slash-commands'];
      case 'output-styles':
        return CLAUDE_CODE_ICONS['output-styles'];
      case 'subagents':
        return CLAUDE_CODE_ICONS['subagents'];
      case 'prompts':
        return CLAUDE_CODE_ICONS['slash-commands'];
      case 'memory':
        return CLAUDE_CODE_ICONS['memory'];
      default:
        return CLAUDE_CODE_ICONS['slash-commands'];
    }
  }, [config.metaKey]);

  const metaLabelKey = `${i18nNamespace}.documents.meta.${config.metaKey}.title`;
  const translatedMetaLabel = t(metaLabelKey);
  const title = translatedMetaLabel === metaLabelKey ? config.dialogTitle : translatedMetaLabel;

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId],
  );
  const sidebarItems = useMemo<WorkspaceDocumentSidebarItem[]>(
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
    if (!selectedDocument || selectedDocument.scope === 'plugin' || selectedDocument.scope === 'extension') {
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

  const handleDialogSubmit = async (document: AgentDocument) => {
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
    if (!selectedDocument || selectedDocument.scope === 'plugin' || selectedDocument.scope === 'extension') {
      return;
    }
    const confirmed = window.confirm(
      t(`${i18nNamespace}.documents.confirmDelete`, { title: selectedDocument.title }),
    );
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
      <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
        <Plus className="mr-1 h-3 w-3" /> {config.createButtonLabel}
      </Button>
    </div>
  );

  const sidebar = showSidebar ? (
    <MultiDocumentSidebar<WorkspaceDocumentSidebarItem>
      title={title}
      icon={Icon}
      items={sidebarItems}
      selectedId={selectedId}
      onSelect={onSelect}
      isLoading={isLoading}
      labels={{
        searchPlaceholder: t(`${i18nNamespace}.documents.sidebar.searchPlaceholder`),
        loading: t(`${i18nNamespace}.documents.sidebar.loading`),
        empty: t(`${i18nNamespace}.documents.sidebar.empty`),
        dirty: t(`${i18nNamespace}.documents.sidebar.dirty`),
      }}
      getDirty={() => false}
      renderItemMeta={(item) => (
        <div className="flex flex-wrap items-center gap-1">
          {!config.hideScopeBadge ? (
            <AgentSettingsSourceBadge
              source={{
                type: documentSourceType(item.document),
                label: t(`${i18nNamespace}.documents.scope.values.${item.document.metadata?.source ?? item.document.scope}`, {
                  defaultValue: String(item.document.metadata?.source ?? item.document.scope),
                }),
                pluginName: item.document.pluginName,
                marketplaceName: item.document.marketplaceName,
                extensionName: item.document.extensionName,
                extensionVersion: item.document.extensionVersion,
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
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="rounded-full bg-muted p-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-base font-medium text-foreground">{config.emptyStateTitle}</h3>
      <p className="text-sm text-muted-foreground">{config.emptyStateDescription}</p>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
          <Plus className="mr-1 h-4 w-4" /> {config.createButtonLabel}
        </Button>
        {onRefresh ? (
          <Button size="sm" variant="ghost" onClick={() => void handleRefresh()} disabled={isProcessing || isLoading}>
            <RefreshCw className="mr-1 h-4 w-4" /> {t(`${i18nNamespace}.documents.actions.refresh`)}
          </Button>
        ) : null}
      </div>
    </div>
  );

  const renderDocumentContent = (document: AgentDocument) => (
    (config.contentFormat ?? (document.metadata?.format as string)) === 'toml'
      ? <TomlContentView content={document.content} i18nNamespace={i18nNamespace} showRaw={config.showRawToml ?? true} />
      : <MarkdownContent content={document.content} />
  );

  const canEditSelected = selectedDocument
    ? selectedDocument.scope !== 'plugin' && selectedDocument.scope !== 'extension'
    : false;
  const canDeleteSelected = canEditSelected;

  const mainArea = selectedDocument ? (
    <div className="flex h-full flex-col">
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
                <DropdownMenuItem onClick={handleEditRequest} disabled={isProcessing || !canEditSelected}>
                  <Edit className="mr-2 h-3 w-3" />
                  {t(`${i18nNamespace}.documents.actions.edit`)}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    void navigator.clipboard.writeText(selectedDocument.content).catch((err) => {
                      logger.error('copyToClipboardFailed', { error: err });
                    });
                  }}
                  disabled={isProcessing}
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
                  disabled={isProcessing}
                >
                  <Download className="mr-2 h-3 w-3" />
                  {t(`${i18nNamespace}.documents.actions.download`)}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => void handleDelete()}
                  className="text-destructive"
                  disabled={isProcessing || !canDeleteSelected}
                >
                  <Trash2 className="mr-2 h-3 w-3" />
                  {t(`${i18nNamespace}.documents.actions.delete`)}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {!config.hideScopeBadge || selectedDocument.metadata?.effective || selectedDocument.metadata?.overridden || selectedDocument.size ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {!config.hideScopeBadge ? (
              <AgentSettingsSourceBadge
                source={{
                  type: documentSourceType(selectedDocument),
                  label: t(`${i18nNamespace}.documents.scope.values.${selectedDocument.metadata?.source ?? selectedDocument.scope}`, {
                    defaultValue: String(selectedDocument.metadata?.source ?? selectedDocument.scope),
                  }),
                  pluginName: selectedDocument.pluginName,
                  marketplaceName: selectedDocument.marketplaceName,
                  extensionName: selectedDocument.extensionName,
                  extensionVersion: selectedDocument.extensionVersion,
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
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {renderDocumentContent(selectedDocument)}
      </div>
    </div>
  ) : renderEmptyState();

  return (
    <>
      {error ? (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}
      <MultiDocumentEditorShell
        title={title}
        icon={Icon}
        sidebar={sidebar}
        headerActions={headerActions}
        emptyState={documents.length === 0 ? renderEmptyState() : undefined}
        isLoading={isLoading}
        labels={{ loading: t(`${i18nNamespace}.documents.loading`) }}
        contentClassName="overflow-hidden"
        mainArea={mainArea}
      />
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
    </>
  );
};

DocumentPage.displayName = 'DocumentPage';

export { DocumentPage as AgentDocumentPage };

export default DocumentPage;
