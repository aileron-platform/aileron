import React, { useEffect, useMemo, useState } from 'react';
import { Bug, FileCode2, FileCog, FileText, Save, ShieldCheck } from 'lucide-react';
import { useApp } from '@/app/providers/AppProvider';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { openSpecApi, type OpenSpecCustomizationDiagnostic, type OpenSpecCustomizationFileResponse } from '../../../components/ChatPanel/openSpecApi';
import { useOpenSpecWorkspace } from '../OpenSpecWorkspaceContext';
import { disableMonacoDiagnostics } from '@/shared/components/monaco/disableMonacoDiagnostics';
import { LocalizedMonacoEditor as Editor } from '@/shared/components/monaco/LocalizedMonacoEditor';

const getFileIcon = (kind?: OpenSpecCustomizationFileResponse['kind']) => {
  if (kind === 'config') return FileCog;
  if (kind === 'template') return FileText;
  return FileCode2;
};

const DiagnosticsList: React.FC<{
  title: string;
  items: OpenSpecCustomizationDiagnostic[];
}> = ({ title, items }) => (
  <div className="space-y-2">
    <div className="flex items-center gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
        {items.length}
      </Badge>
    </div>
    <div className="overflow-hidden rounded-md border border-border bg-background">
      {items.map((item, index) => (
        <div
          key={`${title}-${index}`}
          className={cn(
            'border-t border-border px-3 py-2 text-sm first:border-t-0',
            item.level === 'error' && 'bg-destructive/5 text-destructive',
            item.level === 'warning' && 'bg-amber-50 text-amber-800',
            item.level === 'info' && 'text-foreground',
          )}
        >
          {item.message}
        </div>
      ))}
    </div>
  </div>
);

const OpenSpecCustomizationFeature: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { state: appState } = useApp();
  const { workspaceRuntime, state, dispatch } = useWorkspace();
  const {
    customization,
    customizationValidation,
    customizationDebug,
    customizationDialog,
    closeCustomizationDialog,
  } = useOpenSpecWorkspace();
  const [file, setFile] = useState<OpenSpecCustomizationFileResponse | null>(null);
  const [editorValue, setEditorValue] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const selectedPath = state.openspec.selectedPath;

  useEffect(() => {
    if (!customization) {
      return;
    }
    if (!selectedPath) {
      dispatch({ type: 'SET_OPENSPEC_SELECTED_PATH', payload: customization.configPath });
    }
  }, [customization, dispatch, selectedPath]);

  useEffect(() => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId || !selectedPath) {
      setFile(null);
      setEditorValue('');
      setIsDirty(false);
      return;
    }
    let cancelled = false;
    setIsLoadingFile(true);
    void openSpecApi.getCustomizationFile(
      workspaceRuntime.runtimeBaseUrl,
      workspaceRuntime.workspaceId,
      selectedPath,
    ).then((result) => {
      if (cancelled) return;
      setFile(result);
      setEditorValue(result.content);
      setIsDirty(false);
    }).catch((error) => {
      if (cancelled) return;
      setFile(null);
      setEditorValue('');
      toast({
        title: t('workspace.openspec.customization.messages.loadFailed'),
        description: error instanceof Error ? error.message : t('workspace.openspec.customization.messages.genericError'),
        variant: 'destructive',
      });
    }).finally(() => {
      if (!cancelled) {
        setIsLoadingFile(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selectedPath, t, toast, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const theme = useMemo(
    () => (appState.ui.currentTheme === 'dark' ? 'vs-dark' : 'vs'),
    [appState.ui.currentTheme],
  );

  const headerIcon = getFileIcon(file?.kind);

  const handleSave = async () => {
    if (!file || !workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) {
      return;
    }
    setIsSaving(true);
    try {
      const result = await openSpecApi.updateCustomizationFile(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        file.path,
        editorValue,
      );
      setFile((current) => (current ? { ...current, content: editorValue } : current));
      setIsDirty(false);
      toast({ title: t('workspace.openspec.customization.messages.saved'), description: result.message });
    } catch (error) {
      toast({
        title: t('workspace.openspec.customization.messages.saveFailed'),
        description: error instanceof Error ? error.message : t('workspace.openspec.customization.messages.genericError'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <div className="flex-1 overflow-hidden bg-background">
        <div className="flex h-full flex-col overflow-hidden bg-background">
          {file ? (
            <>
              <div className="border-b border-border bg-background">
                <div className="flex min-h-12 flex-wrap items-center justify-between gap-3 px-4 py-2.5">
                  <div className="flex min-w-0 items-center gap-2">
                    {React.createElement(headerIcon, { className: 'h-4 w-4 shrink-0 text-primary' })}
                    <span className="truncate text-sm font-medium">{file.name}</span>
                    <Badge variant="secondary" className="h-5 px-1.5 text-[10px] uppercase tracking-wide">
                      {file.kind}
                    </Badge>
                    {file.schemaName ? (
                      <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                        {file.schemaName}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 gap-1.5 px-2.5 text-xs"
                      onClick={() => void handleSave()}
                      disabled={!isDirty || isSaving}
                      aria-label={t('common.save')}
                      title={t('common.save')}
                    >
                      <Save className="h-3.5 w-3.5" />
                      {t('common.save')}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="flex min-h-9 flex-wrap items-center gap-x-4 gap-y-1 border-b border-border px-4 py-1.5 text-[11px] text-muted-foreground">
                <span className="truncate font-mono">{file.path}</span>
                <span>{t('workspace.openspec.customization.fields.schemaName')}: {String(file.schemaName ?? '-')}</span>
                {file.kind === 'schema' ? (
                  <>
                    <span>{t('workspace.openspec.customization.fields.defaultSchema')}: {String(file.metadata.isDefault ? t('workspace.openspec.customization.defaultBadge') : '-')}</span>
                    <span>{t('workspace.openspec.customization.fields.templateCount')}: {String(file.metadata.templateCount ?? 0)}</span>
                  </>
                ) : null}
              </div>

              <div className="min-h-0 flex-1">
                <Editor
                  height="100%"
                  language={file.language}
                  theme={theme}
                  value={editorValue}
                  onMount={(_editor, monaco) => disableMonacoDiagnostics(monaco)}
                  onChange={(value) => {
                    setEditorValue(value ?? '');
                    setIsDirty((value ?? '') !== file.content);
                  }}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 13,
                    wordWrap: 'on',
                    automaticLayout: true,
                    scrollBeyondLastLine: false,
                    lineNumbers: 'on',
                    tabSize: 2,
                    padding: { top: 12, bottom: 12 },
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              {isLoadingFile
                ? t('workspace.openspec.customization.loadingFile')
                : t('workspace.openspec.customization.emptyEditor')}
            </div>
          )}
        </div>
      </div>

      <Dialog open={customizationDialog === 'validation'} onOpenChange={(open) => { if (!open) closeCustomizationDialog(); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              {t('workspace.openspec.customization.validationTitle')}
            </DialogTitle>
            <DialogDescription>{customizationValidation?.targetPath ?? t('workspace.openspec.customization.diagnosticsPlaceholder')}</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            <div className="pr-3">
              {customizationValidation ? (
                <DiagnosticsList
                  title={t('workspace.openspec.customization.validationTitle')}
                  items={customizationValidation.diagnostics}
                />
              ) : (
                <p className="text-sm text-muted-foreground">{t('workspace.openspec.customization.diagnosticsPlaceholder')}</p>
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <Dialog open={customizationDialog === 'debug'} onOpenChange={(open) => { if (!open) closeCustomizationDialog(); }}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bug className="h-5 w-5 text-primary" />
              {t('workspace.openspec.customization.debugTitle')}
            </DialogTitle>
            <DialogDescription>{customizationDebug?.targetPath ?? t('workspace.openspec.customization.diagnosticsPlaceholder')}</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            <div className="space-y-4 pr-3">
              {customizationDebug ? (
                <>
                  <div className="rounded-md border border-border bg-background px-3 py-3 text-sm">
                    <p>{t('workspace.openspec.customization.debugResolvedName')}: {customizationDebug.resolvedName ?? '-'}</p>
                    <p>{t('workspace.openspec.customization.debugSource')}: {customizationDebug.source ?? '-'}</p>
                    <p>{t('workspace.openspec.customization.debugPath')}: {customizationDebug.path ?? '-'}</p>
                  </div>
                  <div className="space-y-1.5">
                    {customizationDebug.resolutionOrder.map((step) => (
                      <div key={`${step.order}-${step.label}`} className="rounded-md border border-border bg-background px-3 py-2 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{step.order}. {step.label}</span>
                          {step.selected ? <Badge variant="secondary">{t('workspace.openspec.customization.selectedStep')}</Badge> : null}
                        </div>
                        <p className="mt-1 text-muted-foreground">{step.value ?? '-'}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">{t('workspace.openspec.customization.diagnosticsPlaceholder')}</p>
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default OpenSpecCustomizationFeature;
