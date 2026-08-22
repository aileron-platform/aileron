import React, { useCallback, useEffect, useMemo } from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  FileViewerWorkbench,
  useManagedDocumentWorkbenchTabs,
  type ManagedDocumentWorkbenchAdapter,
} from '@/shared/components/file-workbench/viewer-entry';
import { useWorkspace } from '../../../../providers/WorkspaceProvider';
import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import { isReadOnlyAgentScope, toCodexFileScope } from '../../agentSettingsScopeModel';
import type { AgentSelectedFile } from '../../model/documents';
import { createLogger } from '@/shared/services/logger';
import { useAgentSettingsAuthorization } from '../../AgentSettingsAuthorizationContext';

const logger = createLogger('SkillsPage');

export interface SkillsPageProps {
  selectedFile: AgentSelectedFile | null;
  apiPrefix?: string;
  i18nNamespace?: string;
  onSelect?: (file: AgentSelectedFile | null) => void;
}

interface SkillsWorkbenchState {
  documents: AgentSelectedFile[];
  activeTabId: string | null;
  contents: Record<string, string>;
  originalContents: Record<string, string>;
}

type SkillsWorkbenchProps = Omit<SkillsPageProps, 'apiPrefix' | 'i18nNamespace'> & {
  apiPrefix: string;
  i18nNamespace: string;
  initialState?: SkillsWorkbenchState;
  onStateChange?: (state: SkillsWorkbenchState) => void;
};

type ProviderScopedSkillsWorkbenchProps = Omit<
  SkillsWorkbenchProps,
  'initialState' | 'onStateChange'
>;

const buildTabKey = (file: AgentSelectedFile): string => (
  `${file.scope}|${file.pluginId ?? ''}|${file.path}`
);

const fileBasename = (path: string): string => path.split('/').pop() || path;

const SkillsWorkbench: React.FC<SkillsWorkbenchProps> = ({
  selectedFile,
  apiPrefix,
  i18nNamespace,
  initialState,
  onStateChange,
  onSelect,
}) => {
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const { readOnly } = useAgentSettingsAuthorization();

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const loadFileContent = useCallback(async (file: AgentSelectedFile) => {
    try {
      const response = apiPrefix === 'codex'
        ? await api.getCodexFile(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          'skills',
          toCodexFileScope(file.scope),
          file.path,
          file.pluginId,
        )
        : await api.getSkill(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          file.path,
          file.scope,
        );
      const content = response.content || '';
      return content;
    } catch (error) {
      logger.error('Failed to load file', { error });
      return '';
    }
  }, [api, apiPrefix, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const loadFileBlob = useCallback((file: AgentSelectedFile) => {
    if (apiPrefix === 'codex' && file.scope === 'plugin') {
      return api.getCodexFileBlob(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        'skills',
        'plugin',
        file.path,
        file.pluginId,
      );
    }
    return api.getSkillBlob(
      workspaceRuntime.runtimeBaseUrl,
      workspaceRuntime.workspaceId,
      file.path,
      file.scope,
    );
  }, [api, apiPrefix, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const saveFile = useCallback(async (file: AgentSelectedFile, content: string) => {
    if (readOnly) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    if (apiPrefix === 'codex') {
      await api.updateCodexFile(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        'skills',
        file.scope === 'user' ? 'user' : 'project',
        file.path,
        content,
      );
    } else {
      await api.updateSkill(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        file.path,
        { content },
        file.scope as 'project' | 'user',
      );
    }
  }, [api, apiPrefix, readOnly, t, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const workbench = useManagedDocumentWorkbenchTabs<AgentSelectedFile>({
    initialState,
    onStateChange,
    adapter: {
      getKey: buildTabKey,
      getName: file => fileBasename(file.path),
      readFile: loadFileContent,
      readBlob: loadFileBlob,
      saveFile: async (file, content) => {
        if (readOnly || isReadOnlyAgentScope(file.scope)) {
          return;
        }
        try {
          await saveFile(file, content);
        } catch (error) {
          logger.error('Failed to save file', { error });
          throw error;
        }
      },
      isWritable: file => !readOnly && !isReadOnlyAgentScope(file.scope),
    } satisfies ManagedDocumentWorkbenchAdapter<AgentSelectedFile>,
  });

  const lastProcessedSelectionKey = React.useRef<string | null>(null);
  const { openDocument } = workbench;

  useEffect(() => {
    if (!selectedFile) {
      lastProcessedSelectionKey.current = null;
      return;
    }
    const key = buildTabKey(selectedFile);
    if (lastProcessedSelectionKey.current === key) return;
    lastProcessedSelectionKey.current = key;
    openDocument(selectedFile);
  }, [selectedFile, openDocument]);

  const handleActiveTabChange = useCallback((nextKey: string | null) => {
    workbench.setActiveTabId(nextKey);
    if (!onSelect) return;
    if (!nextKey) {
      onSelect(null);
      return;
    }
    const file = workbench.getDocumentByPath(nextKey);
    onSelect(file ?? null);
  }, [onSelect, workbench]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-1 overflow-hidden bg-background">
        {workbench.tabs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t(`${i18nNamespace}.skills.noSelection`)}
          </div>
        ) : (
          <FileViewerWorkbench
            tabs={workbench.tabs}
            activeTabId={workbench.activeTabId}
            adapter={workbench.adapter}
            capabilities={{
              canEdit: !readOnly && !workbench.isSavingActive,
              canSave: !readOnly && workbench.canSaveActive && !workbench.isSavingActive,
              canCopyPath: false,
              canRevealInTree: false,
              canCloseTabs: true,
            }}
            isPathWritable={workbench.isPathWritable}
            onTabsChange={workbench.applyTabsChange}
            onActiveTabChange={handleActiveTabChange}
          />
        )}
      </div>
    </div>
  );
};

const ProviderScopedSkillsWorkbench: React.FC<ProviderScopedSkillsWorkbenchProps> = (props) => {
  const { apiPrefix } = props;
  const statesByProvider = React.useRef(new Map<string, SkillsWorkbenchState>());
  const handleStateChange = useCallback((state: SkillsWorkbenchState) => {
    statesByProvider.current.set(apiPrefix, state);
  }, [apiPrefix]);

  return (
    <SkillsWorkbench
      key={apiPrefix}
      {...props}
      initialState={statesByProvider.current.get(apiPrefix)}
      onStateChange={handleStateChange}
    />
  );
};

const SkillsPage: React.FC<SkillsPageProps> = ({
  apiPrefix = 'claude-code',
  i18nNamespace = 'workspace.agentSettings.common',
  ...props
}) => {
  const { workspaceRuntime } = useWorkspace();
  const workspaceScopeKey = JSON.stringify([
    workspaceRuntime.workspaceId,
    workspaceRuntime.runtimeBaseUrl,
  ]);

  return (
    <ProviderScopedSkillsWorkbench
      key={workspaceScopeKey}
      {...props}
      apiPrefix={apiPrefix}
      i18nNamespace={i18nNamespace}
    />
  );
};

export default SkillsPage;
