import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Building, Loader2, RefreshCw, Save, Sparkles, User } from 'lucide-react';
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
import { ApiError } from '@/shared/api/apiClient';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { geminiSettingsApi, type GeminiSettingsScope } from '../services/geminiSettingsApi';

const GEMINI_SETTINGS_SCHEMA_URL = 'https://raw.githubusercontent.com/google-gemini/gemini-cli/main/schemas/settings.schema.json';

const readEditorTheme = (): 'vs' | 'vs-dark' => {
  if (typeof document === 'undefined') {
    return 'vs';
  }
  return document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs';
};

const normalizeSettingsContent = (content: unknown): Record<string, unknown> => (
  content && typeof content === 'object' && !Array.isArray(content) ? content as Record<string, unknown> : {}
);

const formatSettingsJson = (content: Record<string, unknown>): string => JSON.stringify(content, null, 2);

const parseJsonObject = (value: string): Record<string, unknown> => {
  const parsed = JSON.parse(value) as unknown;
  return normalizeSettingsContent(parsed);
};

const isMissingSettingsFileError = (error: unknown): boolean => {
  if (error instanceof ApiError) {
    return error.status === 404;
  }
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return message.includes('http 404')
    || message.includes('not found')
    || (message.includes('settings.json') && message.includes('not found'));
};

const SettingsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { workspaceId, runtimeBaseUrl, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;
  const [scope, setScope] = useState<GeminiSettingsScope>('user');
  const [savedContent, setSavedContent] = useState<Record<string, unknown>>({});
  const [draftJson, setDraftJson] = useState(formatSettingsJson({}));
  const [parseError, setParseError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editorTheme, setEditorTheme] = useState(readEditorTheme);

  const isRuntimeReady = Boolean(workspaceId && runtimeBaseUrl);
  const savedJson = useMemo(() => formatSettingsJson(savedContent), [savedContent]);
  const isDirty = draftJson !== savedJson;
  const controlsDisabled = runtimeLoading || !isRuntimeReady || isLoading || isSaving;
  const saveDisabled = controlsDisabled || !isDirty || Boolean(parseError);

  const scopeOptions = useMemo(
    () => [
      {
        value: 'user' as const,
        label: t('workspace.gemini.settings.scope.user'),
        icon: User,
      },
      {
        value: 'project' as const,
        label: t('workspace.gemini.settings.scope.project'),
        icon: Building,
      },
    ],
    [t],
  );

  const configureJsonSchema = useCallback((_editor: unknown, monaco: unknown) => {
    const jsonDefaults = (monaco as {
      languages?: {
        json?: {
          jsonDefaults?: {
            setDiagnosticsOptions?: (options: unknown) => void;
          };
        };
      };
    }).languages?.json?.jsonDefaults;

    jsonDefaults?.setDiagnosticsOptions?.({
      validate: true,
      schemas: [
        {
          uri: GEMINI_SETTINGS_SCHEMA_URL,
          fileMatch: ['*'],
          schema: { $ref: GEMINI_SETTINGS_SCHEMA_URL },
        },
      ],
    });
  }, []);

  const loadSettings = useCallback(
    async (nextScope: GeminiSettingsScope) => {
      if (!workspaceId || !runtimeBaseUrl) {
        return;
      }
      setIsLoading(true);
      setLoadError(null);
      setParseError(null);
      try {
        const response = await geminiSettingsApi.getRawSettings(runtimeBaseUrl, workspaceId, nextScope);
        const content = normalizeSettingsContent(response.content);
        setSavedContent(content);
        setDraftJson(formatSettingsJson(content));
      } catch (error) {
        if (isMissingSettingsFileError(error)) {
          const content: Record<string, unknown> = {};
          setSavedContent(content);
          setDraftJson(formatSettingsJson(content));
          return;
        }
        setLoadError(error instanceof Error ? error.message : String(error));
      } finally {
        setIsLoading(false);
      }
    },
    [runtimeBaseUrl, workspaceId],
  );

  useEffect(() => {
    void loadSettings(scope);
  }, [loadSettings, scope]);

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

  const handleScopeChange = useCallback(
    (value: string) => {
      const nextScope = value as GeminiSettingsScope;
      if (nextScope === scope || controlsDisabled) {
        return;
      }
      if (isDirty && !window.confirm(t('workspace.gemini.settings.unsavedChangesConfirm'))) {
        return;
      }
      setScope(nextScope);
    },
    [controlsDisabled, isDirty, scope, t],
  );

  const handleDraftChange = useCallback((value?: string) => {
    const nextValue = value ?? '';
    setDraftJson(nextValue);
    try {
      parseJsonObject(nextValue);
      setParseError(null);
    } catch {
      setParseError(t('workspace.gemini.settings.parseError'));
    }
  }, [t]);

  const handleRefresh = useCallback(() => {
    void loadSettings(scope);
  }, [loadSettings, scope]);

  const handleSave = useCallback(async () => {
    if (!workspaceId || !runtimeBaseUrl || saveDisabled) {
      return;
    }
    let parsedContent: Record<string, unknown>;
    try {
      parsedContent = parseJsonObject(draftJson);
    } catch {
      setParseError(t('workspace.gemini.settings.parseError'));
      return;
    }
    setIsSaving(true);
    try {
      const response = await geminiSettingsApi.updateRawSettings(runtimeBaseUrl, workspaceId, scope, parsedContent);
      const content = normalizeSettingsContent(response.content);
      setSavedContent(content);
      setDraftJson(formatSettingsJson(content));
      setParseError(null);
      toast({ title: t('workspace.gemini.settings.saveSuccess') });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('workspace.gemini.settings.saveFailed'),
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setIsSaving(false);
    }
  }, [draftJson, runtimeBaseUrl, saveDisabled, scope, t, toast, workspaceId]);

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
      return t('workspace.gemini.settings.loadFailed');
    }
    return null;
  }, [isRuntimeReady, loadError, runtimeError, runtimeLoading, t]);

  return (
    <SettingsWorkflowShell
      title={t('workspace.gemini.settings.header.title')}
      icon={Sparkles}
      summary={isDirty ? (
        <SettingsWorkflowCountBadge label={t('workspace.gemini.settings.dirty')} />
      ) : null}
      headerActions={(
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
            <span className="text-xs text-muted-foreground">
              {t('workspace.gemini.settings.scope.label')}
            </span>
            <Select value={scope} onValueChange={handleScopeChange} disabled={controlsDisabled}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {scopeOptions.map((option) => {
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
            {t('workspace.gemini.settings.actions.refresh')}
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
              ? t('workspace.gemini.settings.actions.saving')
              : t('workspace.gemini.settings.actions.save')}
          </Button>
        </div>
      )}
      hasItems
      emptyTitle={t('workspace.gemini.settings.header.title')}
      emptyDescription={t('workspace.gemini.settings.header.title')}
      contentClassName="h-full overflow-hidden"
    >
      <div className="flex h-full min-h-0 flex-col">
        {statusMessage ? (
          <div className="mx-4 mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {statusMessage}
          </div>
        ) : null}
        {parseError ? (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{parseError}</span>
          </div>
        ) : null}

        <div className="relative min-h-0 flex-1 overflow-hidden">
          {isLoading ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : null}
          <LocalizedMonacoEditor
            language="json"
            value={draftJson}
            onChange={handleDraftChange}
            onMount={configureJsonSchema}
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
