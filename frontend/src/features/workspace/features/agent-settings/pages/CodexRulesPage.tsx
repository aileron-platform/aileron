import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, FileCode2, Play, Plus, RefreshCw } from 'lucide-react';
import {
  MultiDocumentEditorShell,
  MultiDocumentSidebar,
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
  type MultiDocumentSidebarItem,
} from '@/shared/components/document-workflow';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { AgentSettingsSourceBadge } from '../components/SettingsSourcePrimitives';
import { SettingsDocumentEditor } from '../components/SettingsDocumentEditor';
import {
  createAgentSettingsApi,
  type CodexRulesFileSummary,
  type CodexRulesValidationResponse,
} from '../services/agentSettingsApi';
import type { AgentDocument, AgentScope } from '../types';

type CodexRulesLayer = 'project' | 'user';

interface CodexRulesPageProps {
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

type RulesDocument = AgentDocument & {
  scope: CodexRulesLayer;
  metadata: {
    fileName: string;
    source: CodexRulesLayer;
    sizeBytes: number;
    exists?: boolean;
  };
};

interface RulesSidebarItem extends MultiDocumentSidebarItem {
  document: RulesDocument;
}

const RULES_LAYERS: CodexRulesLayer[] = ['project', 'user'];
const DEFAULT_RULE_FILE_NAME = 'default.rules';

const fileNameFromPath = (path: string) => path.split('/').filter(Boolean).pop() || path;
const buildDocumentId = (layer: CodexRulesLayer, path: string) => `${layer}:${path}`;

const isCodexRulesLayer = (value: unknown): value is CodexRulesLayer => value === 'project' || value === 'user';

export const isValidCodexRulesPath = (path: string) => {
  const trimmed = path.trim();
  return Boolean(trimmed)
    && trimmed.endsWith('.rules')
    && !trimmed.startsWith('/')
    && !trimmed.split('/').includes('..');
};

const splitCommand = (command: string) => command.split(/\s+/).filter(Boolean);

const mapSummaryToDocument = (
  layer: CodexRulesLayer,
  summary: CodexRulesFileSummary,
  content = '',
): RulesDocument => ({
  id: buildDocumentId(layer, summary.path),
  title: fileNameFromPath(summary.path),
  description: '',
  content,
  scope: layer,
  size: formatDocumentContentSize(content || ' '),
  metadata: {
    fileName: summary.path,
    source: layer,
    sizeBytes: summary.sizeBytes,
  },
});

const buildDocumentPath = (document: AgentDocument) => {
  const metadataPath = typeof document.metadata?.fileName === 'string' ? document.metadata.fileName : '';
  return metadataPath || document.title || DEFAULT_RULE_FILE_NAME;
};

const RulesContentView: React.FC<{ content: string }> = ({ content }) => (
  <pre className="min-h-full overflow-auto rounded-md border border-border bg-muted/30 p-4 font-mono text-xs leading-5 text-foreground">
    {content}
  </pre>
);

interface CodexRulesValidationDialogProps {
  open: boolean;
  document: RulesDocument | null;
  command: string;
  validation?: CodexRulesValidationResponse;
  validating: boolean;
  onCommandChange: (command: string) => void;
  onValidate: (document: RulesDocument) => void;
  onClose: () => void;
}

const CodexRulesValidationDialog: React.FC<CodexRulesValidationDialogProps> = ({
  open,
  document,
  command,
  validation,
  validating,
  onCommandChange,
  onValidate,
  onClose,
}) => {
  const { t } = useI18n();
  const commandArgs = splitCommand(command);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[85vh] w-[calc(100vw-2rem)] max-w-2xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Play className="h-5 w-5 text-primary" />
            {t('workspace.agentSettings.codex.rules.validationDialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t('workspace.agentSettings.codex.rules.validationDialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="min-w-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {document ? (
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <Badge variant="outline" className="max-w-full truncate">
                {t(`workspace.agentSettings.codex.common.layers.${document.scope}`)}
              </Badge>
              <Badge variant="outline" className="max-w-full truncate">
                {t('workspace.agentSettings.codex.rules.fileName', { fileName: document.metadata.fileName })}
              </Badge>
            </div>
          ) : null}

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              {t('workspace.agentSettings.codex.rules.validationDialog.fields.command.label')}
            </label>
            <Input
              value={command}
              onChange={(event) => onCommandChange(event.target.value)}
              placeholder={t('workspace.agentSettings.codex.rules.commandPlaceholder')}
            />
            <p className="text-xs text-muted-foreground">
              {t('workspace.agentSettings.codex.rules.validationDialog.fields.command.helper')}
            </p>
          </div>

          {validation ? (
            <Alert variant={validation.valid ? 'default' : 'destructive'}>
              <AlertDescription>
                {validation.valid
                  ? t('workspace.agentSettings.codex.rules.validation.valid', { exitCode: validation.exitCode })
                  : t('workspace.agentSettings.codex.rules.validation.invalid', { exitCode: validation.exitCode })}
                {(validation.stderr || validation.stdout) ? (
                  <pre className="mt-2 max-h-56 max-w-full overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-2 text-xs">
                    {[validation.stdout, validation.stderr].filter(Boolean).join('\n')}
                  </pre>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={validating}>
            {t('workspace.agentSettings.codex.rules.validationDialog.actions.close')}
          </Button>
          <Button
            type="button"
            onClick={() => document && onValidate(document)}
            disabled={!document || validating || commandArgs.length === 0}
          >
            <Play className="mr-2 h-4 w-4" />
            {t('workspace.agentSettings.codex.rules.validationDialog.actions.validate')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const CodexRulesDialog: React.FC<DocumentWorkflowDialogProps<RulesDocument>> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [fileName, setFileName] = useState(DEFAULT_RULE_FILE_NAME);
  const [scope, setScope] = useState<CodexRulesLayer>('project');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';

  useEffect(() => {
    if (!open) return;
    const initialScope = isCodexRulesLayer(initialValue?.scope) ? initialValue.scope : 'project';
    setScope(initialScope);
    setFileName((initialValue?.metadata?.fileName as string | undefined) || DEFAULT_RULE_FILE_NAME);
    setContent(initialValue?.content ?? t('workspace.agentSettings.codex.rules.defaultContent'));
    setErrors({});
    setSubmitting(false);
  }, [initialValue, open, t]);

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    if (!isValidCodexRulesPath(fileName)) {
      nextErrors.fileName = t('workspace.agentSettings.codex.rules.dialog.validation.fileName');
    }
    if (!content.trim()) {
      nextErrors.content = t('workspace.agentSettings.codex.rules.dialog.validation.content');
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      const normalizedPath = fileName.trim();
      await onSubmit({
        id: buildDocumentId(scope, normalizedPath),
        title: fileNameFromPath(normalizedPath),
        description: '',
        content,
        scope,
        size: formatDocumentContentSize(content),
        metadata: {
          fileName: normalizedPath,
          source: scope,
          sizeBytes: content.length,
        },
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5 text-primary" />
            {isEdit
              ? t('workspace.agentSettings.codex.rules.dialog.title.edit')
              : t('workspace.agentSettings.codex.rules.dialog.title.create')}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? t('workspace.agentSettings.codex.rules.dialog.description.edit')
              : t('workspace.agentSettings.codex.rules.dialog.description.create')}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex-1 overflow-hidden px-6 pb-6 pt-4">
            <div className="flex h-full flex-col gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t('workspace.agentSettings.codex.rules.dialog.fields.scope.label')}
                  </label>
                  {isEdit ? (
                    <Badge variant="outline" className="text-sm">
                      {t(`workspace.agentSettings.codex.common.layers.${scope}`)}
                    </Badge>
                  ) : (
                    <Select value={scope} onValueChange={(value) => setScope(value as CodexRulesLayer)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RULES_LAYERS.map((layer) => (
                          <SelectItem key={layer} value={layer}>
                            {t(`workspace.agentSettings.codex.common.layers.${layer}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t('workspace.agentSettings.codex.rules.dialog.fields.fileName.label')}
                  </label>
                  <Input
                    value={fileName}
                    onChange={(event) => setFileName(event.target.value)}
                    placeholder={t('workspace.agentSettings.codex.rules.fileNamePlaceholder')}
                  />
                  {errors.fileName ? <p className="text-xs text-destructive">{errors.fileName}</p> : null}
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.agentSettings.codex.rules.dialog.fields.fileName.helper')}
                  </p>
                </div>
              </div>

              <div className="flex min-h-0 flex-1 flex-col space-y-2">
                <label className="text-sm font-medium text-foreground">
                  {t('workspace.agentSettings.codex.rules.dialog.fields.content.label')}
                </label>
                <div className="min-h-0 flex-1 overflow-hidden rounded-lg border">
                  <SettingsDocumentEditor
                    value={content}
                    format="starlark"
                    onChange={setContent}
                    footerExtras={
                      <span className="text-xs text-muted-foreground">
                        {t('workspace.agentSettings.codex.rules.dialog.fields.content.estimatedSize', {
                          size: formatDocumentContentSize(content),
                        })}
                      </span>
                    }
                  />
                </div>
                {errors.content ? <p className="text-xs text-destructive">{errors.content}</p> : null}
              </div>
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {t('workspace.agentSettings.codex.rules.dialog.actions.cancel')}
            </Button>
            <Button type="submit" disabled={submitting}>
              {isEdit
                ? t('workspace.agentSettings.codex.rules.dialog.actions.save')
                : t('workspace.agentSettings.codex.rules.dialog.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

const CodexRulesPage: React.FC<CodexRulesPageProps> = ({
  selectedId: selectedIdProp,
  onSelect: onSelectProp,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null);
  const [command, setCommand] = useState('git status');
  const [validationById, setValidationById] = useState<Record<string, CodexRulesValidationResponse | undefined>>({});
  const [validationDialogId, setValidationDialogId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeDocument, setActiveDocument] = useState<RulesDocument | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const selectedId = selectedIdProp !== undefined ? selectedIdProp : internalSelectedId;
  const setSelectedId = onSelectProp ?? setInternalSelectedId;

  const documentsQuery = useQuery({
    queryKey: ['codex-rules-documents', runtimeBaseUrl, workspaceId],
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    queryFn: async () => {
      const documents: RulesDocument[] = [];
      for (const layer of RULES_LAYERS) {
        const response = await api.listCodexRules(runtimeBaseUrl || '', workspaceId || '', layer);
        documents.push(...response.files.map((summary) => mapSummaryToDocument(layer, summary)));
      }
      return documents.sort((a, b) => `${a.scope}:${a.metadata.fileName}`.localeCompare(`${b.scope}:${b.metadata.fileName}`));
    },
  });

  const baseDocuments = documentsQuery.data ?? [];
  const selectedDocumentSummary = useMemo(() => {
    const document = baseDocuments.find((item) => item.id === selectedId);
    if (!document) return null;
    return { layer: document.scope, path: document.metadata.fileName };
  }, [baseDocuments, selectedId]);

  const selectedDocumentQuery = useQuery({
    queryKey: [
      'codex-rules-selected-content',
      runtimeBaseUrl,
      workspaceId,
      selectedDocumentSummary?.layer,
      selectedDocumentSummary?.path,
    ],
    enabled: Boolean(runtimeBaseUrl && workspaceId && selectedDocumentSummary?.layer && selectedDocumentSummary?.path),
    queryFn: async () => api.getCodexRulesFile(
      runtimeBaseUrl || '',
      workspaceId || '',
      selectedDocumentSummary?.layer ?? 'project',
      selectedDocumentSummary?.path ?? DEFAULT_RULE_FILE_NAME,
    ),
  });

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['codex-rules-documents', runtimeBaseUrl, workspaceId] });
  }, [queryClient, runtimeBaseUrl, workspaceId]);

  const invalidateSelected = useCallback(async (layer: CodexRulesLayer, path: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['codex-rules-documents', runtimeBaseUrl, workspaceId] }),
      queryClient.invalidateQueries({ queryKey: ['codex-rules-selected-content', runtimeBaseUrl, workspaceId, layer, path] }),
    ]);
  }, [queryClient, runtimeBaseUrl, workspaceId]);

  const createDocument = async (document: RulesDocument) => {
    const layer = document.scope;
    const path = buildDocumentPath(document);
    const response = await api.updateCodexRulesFile(runtimeBaseUrl || '', workspaceId || '', layer, path, document.content);
    const created = mapSummaryToDocument(layer, {
      name: fileNameFromPath(path),
      path,
      sizeBytes: document.content.length,
    }, response.content);
    await invalidateSelected(layer, path);
    toast({ title: t('workspace.agentSettings.codex.rules.notifications.saved') });
    return created;
  };

  const updateDocument = async (document: RulesDocument) => {
    const layer = document.scope;
    const path = buildDocumentPath(document);
    const response = await api.updateCodexRulesFile(runtimeBaseUrl || '', workspaceId || '', layer, path, document.content);
    const updated = mapSummaryToDocument(layer, {
      name: fileNameFromPath(path),
      path,
      sizeBytes: document.content.length,
    }, response.content);
    await invalidateSelected(layer, path);
    setValidationById((current) => ({ ...current, [document.id]: undefined }));
    toast({ title: t('workspace.agentSettings.codex.rules.notifications.saved') });
    return updated;
  };

  const deleteDocument = async (id: string) => {
    const document = baseDocuments.find((item) => item.id === id);
    if (!document) return;
    await api.deleteCodexRulesFile(runtimeBaseUrl || '', workspaceId || '', document.scope, document.metadata.fileName);
    await refresh();
    setValidationById((current) => ({ ...current, [id]: undefined }));
    toast({ title: t('workspace.agentSettings.codex.rules.notifications.deleted') });
  };

  const validateMutation = useMutation({
    mutationFn: async (document: RulesDocument) => api.validateCodexRulesFile(
      runtimeBaseUrl || '',
      workspaceId || '',
      document.scope,
      document.metadata.fileName,
      splitCommand(command),
    ),
    onSuccess: (response, document) => {
      setValidationById((current) => ({ ...current, [document.id]: response }));
    },
    onError: (error) => toast({
      variant: 'destructive',
      title: t('workspace.agentSettings.codex.rules.notifications.validateFailed'),
      description: error instanceof Error ? error.message : undefined,
    }),
  });

  const documents = useMemo(() => {
    if (!selectedId || !selectedDocumentQuery.data) {
      return baseDocuments;
    }
    return baseDocuments.map((document) => {
      if (document.id !== selectedId) return document;
      const content = selectedDocumentQuery.data.content;
      return {
        ...document,
        content,
        size: formatDocumentContentSize(content || ' '),
        metadata: {
          ...document.metadata,
          exists: selectedDocumentQuery.data.exists,
          sizeBytes: content.length,
        },
      };
    });
  }, [baseDocuments, selectedDocumentQuery.data, selectedId]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId],
  );
  const sidebarItems = useMemo<RulesSidebarItem[]>(
    () => documents.map((document) => ({
      id: document.id,
      label: document.title,
      description: document.metadata.fileName,
      document,
    })),
    [documents],
  );
  const currentIndex = selectedDocument
    ? documents.findIndex((document) => document.id === selectedDocument.id)
    : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < documents.length - 1;

  useEffect(() => {
    const selectedExists = selectedId ? documents.some((document) => document.id === selectedId) : false;
    if (documents.length > 0 && (!selectedId || !selectedExists)) {
      setSelectedId(documents[0].id);
    }
  }, [documents, selectedId, setSelectedId]);

  const validationDialogDocument = useMemo(
    () => documents.find((document) => document.id === validationDialogId) ?? null,
    [documents, validationDialogId],
  );

  const handleCreateRequest = () => {
    setDialogMode('create');
    setActiveDocument(null);
    setDialogOpen(true);
  };

  const handleEditRequest = () => {
    if (!selectedDocument) {
      return;
    }
    setDialogMode('edit');
    setActiveDocument(selectedDocument);
    setDialogOpen(true);
  };

  const handleRefresh = async () => {
    try {
      setIsProcessing(true);
      await refresh();
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDialogSubmit = async (document: RulesDocument) => {
    try {
      setIsProcessing(true);
      if (dialogMode === 'create') {
        const created = await createDocument(document);
        setSelectedId(created.id);
      } else {
        const updated = await updateDocument(document);
        setSelectedId(updated.id);
      }
      setDialogOpen(false);
      setActiveDocument(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (!selectedDocument) {
      return;
    }
    const confirmed = window.confirm(
      t('workspace.agentSettings.codex.rules.confirmDelete', { title: selectedDocument.title }),
    );
    if (!confirmed) {
      return;
    }
    try {
      setIsProcessing(true);
      await deleteDocument(selectedDocument.id);
      const nextDocuments = documents.filter((document) => document.id !== selectedDocument.id);
      setSelectedId(nextDocuments[0]?.id ?? null);
    } finally {
      setIsProcessing(false);
    }
  };

  const headerActions = (
    <div className="flex items-center gap-2">
      <Badge variant="secondary" className="text-[11px]">
        {t('workspace.agentSettings.codex.documents.stats.total', { count: documents.length })}
      </Badge>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={() => void handleRefresh()}
        disabled={isProcessing || (documentsQuery.isFetching && documents.length === 0)}
      >
        <RefreshCw className="mr-1 h-3 w-3" /> {t('workspace.agentSettings.codex.documents.actions.refresh')}
      </Button>
      <Button size="sm" className="h-7 px-2 text-xs" onClick={handleCreateRequest} disabled={isProcessing}>
        <Plus className="mr-1 h-3 w-3" /> {t('workspace.agentSettings.codex.rules.actions.create')}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2 text-xs"
        onClick={handleEditRequest}
        disabled={isProcessing || !selectedDocument}
      >
        {t('workspace.agentSettings.codex.documents.actions.edit')}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2 text-xs"
        onClick={() => selectedDocument && setValidationDialogId(selectedDocument.id)}
        disabled={isProcessing || !selectedDocument}
      >
        <Play className="mr-1 h-3 w-3" />
        {t('workspace.agentSettings.codex.rules.actions.validate')}
      </Button>
    </div>
  );

  const sidebar = (
    <MultiDocumentSidebar<RulesSidebarItem>
      title={t('workspace.agentSettings.codex.rules.title')}
      icon={FileCode2}
      items={sidebarItems}
      selectedId={selectedId}
      onSelect={setSelectedId}
      isLoading={documentsQuery.isFetching && documents.length === 0}
      labels={{
        searchPlaceholder: t('workspace.agentSettings.codex.documents.sidebar.searchPlaceholder'),
        loading: t('workspace.agentSettings.codex.rules.loading'),
        empty: t('workspace.agentSettings.codex.rules.empty.title'),
        dirty: t('workspace.agentSettings.codex.rules.validationDialog.title'),
      }}
      renderItemMeta={(item) => (
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-[11px]">
            {t(`workspace.agentSettings.codex.common.layers.${item.document.scope}`)}
          </Badge>
          <Badge variant="outline" className="text-[11px]">
            {t('workspace.agentSettings.codex.rules.fileName', { fileName: item.document.metadata.fileName })}
          </Badge>
          <Badge variant="outline" className="text-[11px]">
            {t('workspace.agentSettings.codex.documents.size.badge', { size: item.document.size })}
          </Badge>
        </div>
      )}
    />
  );

  const mainArea = selectedDocument ? (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-background px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-foreground">{selectedDocument.title}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <AgentSettingsSourceBadge
                source={{
                  type: selectedDocument.scope as AgentScope,
                  label: t(`workspace.agentSettings.codex.documents.scope.values.${selectedDocument.scope}`),
                }}
              />
              <Badge variant="outline" className="text-[11px]">
                {t('workspace.agentSettings.codex.rules.fileName', { fileName: selectedDocument.metadata.fileName })}
              </Badge>
              <Badge variant="outline" className="text-[11px]">
                {t('workspace.agentSettings.codex.documents.size.badge', { size: selectedDocument.size })}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={() => canNavigatePrevious && setSelectedId(documents[currentIndex - 1].id)}
              disabled={!canNavigatePrevious || isProcessing}
            >
              <ChevronDown className="h-3.5 w-3.5 rotate-90" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              onClick={() => canNavigateNext && setSelectedId(documents[currentIndex + 1].id)}
              disabled={!canNavigateNext || isProcessing}
            >
              <ChevronDown className="h-3.5 w-3.5 -rotate-90" />
            </Button>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <RulesContentView content={selectedDocument.content} />
      </div>
    </div>
  ) : (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="rounded-full bg-muted p-3">
        <FileCode2 className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-base font-medium text-foreground">{t('workspace.agentSettings.codex.rules.empty.title')}</h3>
      <p className="text-sm text-muted-foreground">{t('workspace.agentSettings.codex.rules.empty.description')}</p>
      <Button size="sm" onClick={handleCreateRequest} disabled={isProcessing}>
        <Plus className="mr-1 h-4 w-4" />
        {t('workspace.agentSettings.codex.rules.actions.create')}
      </Button>
    </div>
  );

  return (
    <>
      {documentsQuery.error instanceof Error ? (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {documentsQuery.error.message}
        </div>
      ) : null}
      <MultiDocumentEditorShell
        title={t('workspace.agentSettings.codex.rules.title')}
        icon={FileCode2}
        sidebar={sidebar}
        headerActions={headerActions}
        emptyState={documents.length === 0 ? mainArea : undefined}
        isLoading={documentsQuery.isFetching && documents.length === 0}
        labels={{ loading: t('workspace.agentSettings.codex.rules.loading') }}
        mainArea={mainArea}
      />
      <CodexRulesDialog
        open={dialogOpen}
        mode={dialogMode}
        initialValue={activeDocument}
        onClose={() => {
          setDialogOpen(false);
          setActiveDocument(null);
        }}
        onSubmit={handleDialogSubmit}
      />
      <CodexRulesValidationDialog
        open={Boolean(validationDialogId)}
        document={validationDialogDocument}
        command={command}
        validation={validationDialogDocument ? validationById[validationDialogDocument.id] : undefined}
        validating={validateMutation.isPending}
        onCommandChange={setCommand}
        onValidate={(document) => validateMutation.mutate(document)}
        onClose={() => setValidationDialogId(null)}
      />
    </>
  );
};

export default CodexRulesPage;
