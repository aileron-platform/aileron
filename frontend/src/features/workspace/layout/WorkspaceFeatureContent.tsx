import React from 'react';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { getAgentToolConfig } from '../features/agent-settings/model/agentSettingsModel';
import type { AgentSettingsToolId } from '../features/agent-settings/model/capabilities';
import type { AgentSelectedFile } from '../features/agent-settings/model/documents';
import { AuthorizationDeniedState } from '@/features/auth/public';
import { WorkspaceFeatureLoading } from '../components/WorkspaceFeatureLoading';
import { useI18n } from '@/shared/hooks/useI18n';
import { useQueryClient } from '@tanstack/react-query';
import {
  clearSensitiveAgentSettingsQueries,
} from '../features/agent-settings/api/sensitiveAgentSettingsQueries';

const FileManagementSidebar = React.lazy(() =>
  import('../features/file-management/components/FileManagementSidebar').then((module) => ({
    default: module.FileManagementSidebar,
  })),
);

const VersionControlSidebar = React.lazy(() =>
  import('../features/version-control/VersionControlPage').then((module) => ({
    default: module.VersionControlSidebar,
  })),
);

const VersionControlMainContent = React.lazy(() =>
  import('../features/version-control/VersionControlPage').then((module) => ({
    default: module.VersionControlMainContent,
  })),
);

const WorkspaceSettingsPage = React.lazy(() =>
  import('../features/workspace-settings/WorkspaceSettingsPage').then((module) => ({
    default: module.WorkspaceSettingsPage,
  })),
);

const ContainerManagementPage = React.lazy(() =>
  import('../features/container-management/ContainerManagementPage').then((module) => ({
    default: module.ContainerManagementPage,
  })),
);

const AgentSettingsPage = React.lazy(() =>
  import('../features/agent-settings/AgentSettingsPage'),
);

const AgentFileManager = React.lazy(() =>
  import('../features/agent-settings/components/AgentFileManager'),
);

const AgentDocumentSidebar = React.lazy(() =>
  import('../features/agent-settings/components/AgentDocumentSidebar'),
);

const CodexDocumentSidebar = React.lazy(() =>
  import('../features/agent-settings/components/CodexDocumentSidebar'),
);

const WebCanvasPage = React.lazy(() =>
  import('../features/canvas/WebCanvasPage').then((module) => ({
    default: module.WebCanvasPage,
  })),
);

const BrowserPage = React.lazy(() =>
  import('../features/browser/BrowserPage').then((module) => ({
    default: module.BrowserPage,
  })),
);

interface WorkspaceFeatureContentProps {
  column: 'second' | 'main';
  columnCollapsed: boolean;
  fallback?: React.ReactNode;
  activeAgentToolId: AgentSettingsToolId;
  isAgentToolFeatureActive: boolean;
  skillSelectedFile: AgentSelectedFile | null;
  onSkillSelect: (file: AgentSelectedFile | null) => void;
  documentSelectedId: string | null;
  onDocumentSelect: (id: string | null) => void;
  onDocumentDirtyChange: (dirty: boolean) => void;
  documentSelectionBlocked: boolean;
  fileTreeRefreshSignal: number;
  onFileTreeRefreshingChange: (isRefreshing: boolean) => void;
}

export const WorkspaceFeatureContent: React.FC<WorkspaceFeatureContentProps> = ({
  column,
  columnCollapsed,
  fallback,
  activeAgentToolId,
  isAgentToolFeatureActive,
  skillSelectedFile,
  onSkillSelect,
  documentSelectedId,
  onDocumentSelect,
  onDocumentDirtyChange,
  documentSelectionBlocked,
  fileTreeRefreshSignal,
  onFileTreeRefreshingChange,
}) => {
  const { state, workspaceRuntime, permissions } = useWorkspace();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const isSensitiveAgentSettingsSubview = isAgentToolFeatureActive
    && (
      state.agentToolSettings.subView === 'mcp'
      || state.agentToolSettings.subView === 'settings'
    );

  React.useEffect(() => {
    if (permissions.canUseSensitiveSettings) {
      return;
    }
    clearSensitiveAgentSettingsQueries(queryClient);
  }, [permissions.canUseSensitiveSettings, queryClient]);

  if (column === 'second') {
    if (state.currentFeature === 'file-management') {
      if (!permissions.canRead) {
        return null;
      }
      return (
        <React.Suspense
          fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.fileTree" className="p-3" />}
        >
          <FileManagementSidebar
            collapsed={columnCollapsed}
            showHeader={false}
            refreshSignal={fileTreeRefreshSignal}
            onRefreshingChange={onFileTreeRefreshingChange}
          />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'version-control') {
      if (!permissions.canRead) {
        return null;
      }
      return (
        <React.Suspense
          fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.versionControlSidebar" className="p-3" />}
        >
          <VersionControlSidebar collapsed={columnCollapsed} />
        </React.Suspense>
      );
    }
    if (isAgentToolFeatureActive) {
      if (
        !permissions.canRead
        || (isSensitiveAgentSettingsSubview && !permissions.canUseSensitiveSettings)
      ) {
        return null;
      }
      const subView = state.agentToolSettings.subView;
      const isClaudeDocumentResource =
        state.currentFeature === 'claude-code'
        && (
          subView === 'slash-commands'
          || subView === 'output-styles'
          || subView === 'subagents'
          || subView === 'memory'
        );
      const isOpenCodeDocumentResource =
        state.currentFeature === 'opencode'
        && (subView === 'slash-commands' || subView === 'subagents');
      if (isClaudeDocumentResource || isOpenCodeDocumentResource) {
        const cliConfig = getAgentToolConfig(isOpenCodeDocumentResource ? 'opencode' : 'claude');
        const documentResource = subView as 'slash-commands' | 'output-styles' | 'subagents' | 'memory';
        const availableScopes = subView === 'slash-commands'
          ? cliConfig.capabilities.slashCommands?.scopes
          : subView === 'subagents'
            ? cliConfig.capabilities.agentDefinitions?.scopes
            : subView === 'output-styles'
              ? ['project', 'user'] as const
              : undefined;
        return (
          <React.Suspense
            fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.agentSettings" className="p-3" />}
          >
            <AgentDocumentSidebar
              resource={documentResource}
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
              apiPrefix={cliConfig.apiPathPrefix}
              availableScopes={availableScopes ? [...availableScopes] : undefined}
              collapsed={columnCollapsed}
              showHeader={false}
            />
          </React.Suspense>
        );
      }
      if (state.currentFeature === 'codex' && (subView === 'subagents' || subView === 'prompts' || subView === 'rules')) {
        return (
          <React.Suspense
            fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.agentSettings" className="p-3" />}
          >
            <CodexDocumentSidebar
              resource={subView}
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
              collapsed={columnCollapsed}
              showHeader={false}
            />
          </React.Suspense>
        );
      }
      if (subView === 'skills') {
        const cliConfig = getAgentToolConfig(activeAgentToolId);
        if (!workspaceRuntime.workspaceId) {
          return <WorkspaceFeatureLoading labelKey="workspace.layout.loading.workspace" />;
        }
        return (
          <React.Suspense
            fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.skillsTree" className="p-3" />}
          >
            <AgentFileManager
              config={cliConfig}
              collectionType="skills"
              onSelect={onSkillSelect}
              workspaceId={workspaceRuntime.workspaceId}
              collapsed={columnCollapsed}
              showHeader={false}
            />
          </React.Suspense>
        );
      }
    }
    return <>{fallback}</>;
  }

  if (state.currentFeature === 'version-control') {
    if (!permissions.canRead) {
      return <AuthorizationDeniedState />;
    }
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.versionControlContent" />}
      >
        <VersionControlMainContent />
      </React.Suspense>
    );
  }
  if (state.currentFeature === 'workspace-settings') {
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.workspaceSettings" />}
      >
        <WorkspaceSettingsPage />
      </React.Suspense>
    );
  }
  if (state.currentFeature === 'container-management') {
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.containerManagement" />}
      >
        <ContainerManagementPage />
      </React.Suspense>
    );
  }
  if (isAgentToolFeatureActive) {
    if (
      !permissions.canRead
      || (isSensitiveAgentSettingsSubview && !permissions.canUseSensitiveSettings)
    ) {
      return <AuthorizationDeniedState />;
    }
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.agentSettings" />}
      >
        <AgentSettingsPage
          toolId={activeAgentToolId}
          subView={state.agentToolSettings.subView}
          skillSelectedFile={skillSelectedFile}
          onSkillSelect={onSkillSelect}
          documentSelectedId={documentSelectedId}
          onDocumentSelect={onDocumentSelect}
          onDocumentDirtyChange={onDocumentDirtyChange}
          documentSelectionBlocked={documentSelectionBlocked}
          readOnly={!permissions.canWrite}
        />
      </React.Suspense>
    );
  }
  if (state.currentFeature === 'canvas') {
    if (!permissions.canRead) {
      return <AuthorizationDeniedState />;
    }
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.canvas.header.loading" />}
      >
        <WebCanvasPage />
      </React.Suspense>
    );
  }
  if (state.currentFeature === 'browser') {
    if (!permissions.canUseBrowser) {
      return <AuthorizationDeniedState />;
    }
    return (
      <React.Suspense
        fallback={<WorkspaceFeatureLoading labelKey="workspace.browser.loading" />}
      >
        <BrowserPage />
      </React.Suspense>
    );
  }
  return <>{fallback}</>;
};
