import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { OnMount } from '@monaco-editor/react';
import { AlertCircle, Building, FileJson2, Laptop, Loader2, RefreshCw, Save, User } from 'lucide-react';
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
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { SettingsWorkflowShell, SettingsWorkflowCountBadge } from '@/shared/components/settings-workflow';
import { claudeCodeApi, type ClaudeCodeSettingsScope } from '../services/claudeCodeApi';

const CLAUDE_CODE_SETTINGS_SCHEMA_URL = 'https://www.schemastore.org/claude-code-settings.json';
const EMPTY_SETTINGS_JSON = '{}';

const normalizeSettingsContent = (content: unknown): Record<string, unknown> => {
  if (!content || typeof content !== 'object' || Array.isArray(content)) {
    return {};
  }
  return content as Record<string, unknown>;
};

const formatSettingsJson = (content: Record<string, unknown>): string => {
  if (Object.keys(content).length === 0) {
    return EMPTY_SETTINGS_JSON;
  }
  return JSON.stringify(content, null, 2);
};

const readEditorTheme = (): 'vs' | 'vs-dark' => {
  if (typeof document === 'undefined') {
    return 'vs';
  }
  return document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs';
};

const SettingsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { workspaceId, runtimeBaseUrl, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;
  const [scope, setScope] = useState<ClaudeCodeSettingsScope>('local');
  const [savedContent, setSavedContent] = useState<Record<string, unknown>>({});
  const [draftJson, setDraftJson] = useState(EMPTY_SETTINGS_JSON);
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
        value: 'local' as const,
        label: t('workspace.claudeCode.permissions.scope.options.local'),
        icon: Laptop,
      },
      {
        value: 'user' as const,
        label: t('workspace.claudeCode.permissions.scope.options.user'),
        icon: User,
      },
      {
        value: 'project' as const,
        label: t('workspace.claudeCode.permissions.scope.options.project'),
        icon: Building,
      },
    ],
    [t],
  );

  const configureJsonSchema = useCallback<OnMount>((_editor, monaco) => {
    monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
      validate: true,
      schemas: [
        {
          uri: CLAUDE_CODE_SETTINGS_SCHEMA_URL,
          fileMatch: ['*'],
          schema: { $ref: CLAUDE_CODE_SETTINGS_SCHEMA_URL },
        },
      ],
    });
  }, []);

  const loadSettings = useCallback(
    async (nextScope: ClaudeCodeSettingsScope) => {
      if (!workspaceId || !runtimeBaseUrl) {
        return;
      }
      setIsLoading(true);
      setLoadError(null);
      setParseError(null);
      try {
        const response = await claudeCodeApi.getRawSettings(runtimeBaseUrl, workspaceId, nextScope);
        const content = normalizeSettingsContent(response.content);
        setSavedContent(content);
        setDraftJson(formatSettingsJson(content));
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

  const handleDraftChange = useCallback(
    (value?: string) => {
      const nextValue = value ?? '';
      setDraftJson(nextValue);
      try {
        JSON.parse(nextValue);
        setParseError(null);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setParseError(message);
      }
    },
    [],
  );

  const handleScopeChange = useCallback(
    (value: string) => {
      const nextScope = value as ClaudeCodeSettingsScope;
      if (nextScope === scope || controlsDisabled) {
        return;
      }
      if (isDirty && !window.confirm(t('workspace.claudeCode.settings.unsavedChangesConfirm'))) {
        return;
      }
      setScope(nextScope);
    },
    [controlsDisabled, isDirty, scope, t],
  );

  const handleRefresh = useCallback(() => {
    void loadSettings(scope);
  }, [loadSettings, scope]);

  const handleSave = useCallback(async () => {
    if (!workspaceId || !runtimeBaseUrl || saveDisabled) {
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draftJson);
      setParseError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setParseError(message);
      return;
    }
    setIsSaving(true);
    try {
      const response = await claudeCodeApi.updateRawSettings(runtimeBaseUrl, workspaceId, scope, parsed);
      const content = normalizeSettingsContent(response.content);
      setSavedContent(content);
      setDraftJson(formatSettingsJson(content));
      toast({ title: t('workspace.claudeCode.settings.saveSuccess') });
    } catch {
      toast({
        variant: 'destructive',
        title: t('workspace.claudeCode.settings.saveFailed'),
      });
    } finally {
      setIsSaving(false);
    }
  }, [draftJson, runtimeBaseUrl, saveDisabled, scope, t, toast, workspaceId]);

  const statusMessage = useMemo(() => {
    if (runtimeError) {
      return t('workspace.claudeCode.permissions.status.runtimeUnavailable', { message: runtimeError });
    }
    if (runtimeLoading && !isRuntimeReady) {
      return t('workspace.claudeCode.permissions.status.runtimeLoading');
    }
    if (!isRuntimeReady) {
      return t('workspace.claudeCode.permissions.status.runtimeMissing');
    }
    if (loadError) {
      return t('workspace.claudeCode.permissions.status.loadFailed');
    }
    return null;
  }, [isRuntimeReady, loadError, runtimeError, runtimeLoading, t]);

  return (
    <SettingsWorkflowShell
        title={t('workspace.claudeCode.settings.header.title')}
        icon={FileJson2}
        summary={isDirty ? (
          <SettingsWorkflowCountBadge label={t('workspace.claudeCode.settings.dirty')} />
        ) : null}
        headerActions={(
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">
                {t('workspace.claudeCode.permissions.scope.label')}
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
              {t('workspace.claudeCode.permissions.actions.refresh')}
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
                ? t('workspace.claudeCode.permissions.actions.saving')
                : t('workspace.claudeCode.permissions.actions.save')}
            </Button>
          </div>
        )}
        hasItems
        emptyTitle={t('workspace.claudeCode.settings.header.title')}
        emptyDescription={t('workspace.claudeCode.settings.header.title')}
        contentClassName="h-full overflow-hidden"
      >
      <div className="flex h-full min-h-0 flex-col gap-4">
        {statusMessage ? (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{statusMessage}</span>
          </div>
        ) : null}

        {parseError ? (
          <div className="mx-4 mt-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>{t('workspace.claudeCode.settings.parseError')}</span>
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
