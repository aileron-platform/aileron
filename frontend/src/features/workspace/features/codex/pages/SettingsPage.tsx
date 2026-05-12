import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Building, Code2, Loader2, RefreshCw, Save, User } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { LocalizedMonacoEditor } from '@/shared/components/monaco/LocalizedMonacoEditor';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { codexSettingsApi, type CodexConfigLayer } from '../services/codexSettingsApi';

const readEditorTheme = (): 'vs' | 'vs-dark' => {
  if (typeof document === 'undefined') {
    return 'vs';
  }
  return document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs';
};

const normalizeTomlContent = (content: unknown): string => (
  typeof content === 'string' ? content : ''
);

const SettingsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { workspaceId, runtimeBaseUrl, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;
  const [layer, setLayer] = useState<CodexConfigLayer>('user');
  const [savedToml, setSavedToml] = useState('');
  const [draftToml, setDraftToml] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editorTheme, setEditorTheme] = useState(readEditorTheme);

  const isRuntimeReady = Boolean(workspaceId && runtimeBaseUrl);
  const isDirty = draftToml !== savedToml;
  const controlsDisabled = runtimeLoading || !isRuntimeReady || isLoading || isSaving;
  const saveDisabled = controlsDisabled || !isDirty;

  const layerOptions = useMemo(
    () => [
      {
        value: 'user' as const,
        label: t('workspace.codex.settings.scope.user'),
        icon: User,
      },
      {
        value: 'project' as const,
        label: t('workspace.codex.settings.scope.project'),
        icon: Building,
      },
    ],
    [t],
  );

  const loadConfig = useCallback(
    async (nextLayer: CodexConfigLayer) => {
      if (!workspaceId || !runtimeBaseUrl) {
        return;
      }
      setIsLoading(true);
      setLoadError(null);
      try {
        const response = await codexSettingsApi.getRawConfig(runtimeBaseUrl, workspaceId, nextLayer);
        const content = normalizeTomlContent(response.content);
        setSavedToml(content);
        setDraftToml(content);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setLoadError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [runtimeBaseUrl, workspaceId],
  );

  useEffect(() => {
    void loadConfig(layer);
  }, [layer, loadConfig]);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const updateEditorTheme = () => setEditorTheme(readEditorTheme());
    updateEditorTheme();

    const observer = new MutationObserver(updateEditorTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });

    return () => observer.disconnect();
  }, []);

  const handleLayerChange = useCallback(
    (value: string) => {
      const nextLayer = value as CodexConfigLayer;
      if (nextLayer === layer || controlsDisabled) {
        return;
      }
      if (isDirty && !window.confirm(t('workspace.codex.settings.unsavedChangesConfirm'))) {
        return;
      }
      setLayer(nextLayer);
    },
    [controlsDisabled, isDirty, layer, t],
  );

  const handleRefresh = useCallback(() => {
    void loadConfig(layer);
  }, [layer, loadConfig]);

  const handleSave = useCallback(async () => {
    if (!workspaceId || !runtimeBaseUrl || saveDisabled) {
      return;
    }
    setIsSaving(true);
    try {
      const response = await codexSettingsApi.updateRawConfig(runtimeBaseUrl, workspaceId, layer, draftToml);
      const content = normalizeTomlContent(response.content);
      setSavedToml(content);
      setDraftToml(content);
      toast({ title: t('workspace.codex.settings.saveSuccess') });
    } catch (error) {
      const description = error instanceof Error ? error.message : String(error);
      toast({
        variant: 'destructive',
        title: t('workspace.codex.settings.saveFailed'),
        description,
      });
    } finally {
      setIsSaving(false);
    }
  }, [draftToml, layer, runtimeBaseUrl, saveDisabled, t, toast, workspaceId]);

  const statusMessage = useMemo(() => {
    if (runtimeError) {
      return t('workspace.agentSettings.common.agentsMd.status.runtimeUnavailable', { message: runtimeError });
    }
    if (runtimeLoading && !isRuntimeReady) {
      return t('workspace.agentSettings.common.agentsMd.status.runtimeLoading');
    }
    if (!isRuntimeReady) {
      return t('workspace.agentSettings.common.agentsMd.status.runtimeMissing');
    }
    if (loadError) {
      return t('workspace.codex.settings.loadFailed');
    }
    return null;
  }, [isRuntimeReady, loadError, runtimeError, runtimeLoading, t]);

  return (
    <SettingsWorkflowShell
      title={t('workspace.codex.settings.header.title')}
      icon={Code2}
      summary={isDirty ? (
        <SettingsWorkflowCountBadge label={t('workspace.codex.settings.dirty')} />
      ) : null}
      headerActions={(
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
            <span className="text-xs text-muted-foreground">
              {t('workspace.codex.settings.scope.label')}
            </span>
            <Select value={layer} onValueChange={handleLayerChange} disabled={controlsDisabled}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {layerOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex items-center gap-2">
                        <Icon className="h-3 w-3" /> {option.label}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleRefresh}
            disabled={controlsDisabled}
          >
            <RefreshCw className={`mr-1 h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
            {t('workspace.codex.settings.actions.refresh')}
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleSave}
            disabled={saveDisabled}
          >
            {isSaving ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Save className="mr-1 h-3 w-3" />
            )}
            {isSaving
              ? t('workspace.codex.settings.actions.saving')
              : t('workspace.codex.settings.actions.save')}
          </Button>
        </div>
      )}
      hasItems
      emptyTitle={t('workspace.codex.settings.header.title')}
      emptyDescription={t('workspace.codex.settings.header.title')}
      contentClassName="h-full overflow-hidden"
    >
      <div className="flex h-full min-h-0 flex-col">
        {statusMessage ? (
          <div className="mx-4 mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {statusMessage}
          </div>
        ) : null}

        <div className="relative min-h-0 flex-1 overflow-hidden">
          {isLoading ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : null}
          <LocalizedMonacoEditor
            language="ini"
            value={draftToml}
            onChange={(value) => setDraftToml(value ?? '')}
            theme={editorTheme}
            height="100%"
            options={{
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              tabSize: 2,
              wordWrap: 'on',
              readOnly: controlsDisabled,
              automaticLayout: true,
            }}
          />
        </div>
      </div>
    </SettingsWorkflowShell>
  );
};

export default SettingsPage;
