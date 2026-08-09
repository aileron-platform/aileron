/**
 * 
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { useWorkspace } from './providers/WorkspaceProvider';
import { WorkspaceShell } from './layout/WorkspaceShell';
import { fetchWorkspaceList } from './api/workspaceListApi';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import {
  useAuth,
} from '@/features/auth/public';
import { useWorkspaceFileOpenQuery } from './deep-link/useWorkspaceFileOpenQuery';
import { useWorkspaceSelection } from './selection/WorkspaceSelectionContext';
import { loadAiChatPage } from '@/features/ai-chat/public';
import { WorkspaceEntryGate } from './entry/WorkspaceEntryGate';
import { projectWorkspaceEntry } from './entry/workspaceEntryProjection';
import { RequireWorkspaceOperation } from './components/RequireWorkspaceOperation';
import { WorkspaceFeatureLoading } from './components/WorkspaceFeatureLoading';
import { resolveWorkspacePermissions } from './model/workspacePermissions';
import type { WorkspaceListItem } from './model/workspaceTypes';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

const FileManagementPage = React.lazy(() => import('./features/file-management/FileManagementPage'));
const VersionControlPage = React.lazy(() => import('./features/version-control/VersionControlPage'));
const WorkspaceSettingsPage = React.lazy(() => import('./features/workspace-settings/WorkspaceSettingsPage'));
const ContainerManagementPage = React.lazy(() => import('./features/container-management/ContainerManagementPage'));
const WorkspaceAutomationRoute = React.lazy(() => import('./routes/WorkspaceAutomationRoute'));
const AiChatPage = React.lazy(loadAiChatPage);

interface WorkspaceModuleProps {
  navigationSlot: React.ReactNode;
}

const WorkspaceFilesRoute: React.FC = () => {
  useWorkspaceFileOpenQuery();
  return (
    <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.fileTree" />}>
      <FileManagementPage />
    </React.Suspense>
  );
};

interface WorkspaceHomeRouteProps {
  workspaceId: string;
  userId: string;
}

const WorkspaceHomeRoute: React.FC<WorkspaceHomeRouteProps> = ({
  workspaceId,
  userId,
}) => {
  const { permissions, workspaceRuntime } = useWorkspace();

  if (workspaceRuntime.isLoading) {
    return <WorkspaceFeatureLoading labelKey="workspace.layout.loading.workspace" />;
  }

  if (!permissions.canUseChat && permissions.canRead) {
    return <Navigate to={ROUTES.workspace.files(workspaceId)} replace />;
  }

  return (
    <RequireWorkspaceOperation operation={OPERATION_IDS.workspaceAgentChatUse}>
      <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.aiChatHome" />}>
        <AiChatPage workspaceId={workspaceId} userId={userId} />
      </React.Suspense>
    </RequireWorkspaceOperation>
  );
};

/**
 * 
 */
interface WorkspaceRootResolverProps {
  navigationSlot: React.ReactNode;
}

type WorkspaceRootState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'empty' }
  | {
    status: 'ready';
    workspaceId: string;
    accessRole: WorkspaceListItem['accessRole'];
    allowedOperations: WorkspaceListItem['allowedOperations'];
  };

const WorkspaceRootResolver: React.FC<WorkspaceRootResolverProps> = ({
  navigationSlot,
}) => {
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();
  const { hasPlatformOperation } = useAuth();
  const navigate = useNavigate();
  const canCreateWorkspace = hasPlatformOperation(OPERATION_IDS.workspaceCreate);
  const selectedWorkspaceIdRef = useRef(selectedWorkspaceId);
  const [reloadToken, setReloadToken] = useState(0);
  const [rootState, setRootState] = useState<WorkspaceRootState>({
    status: 'loading',
  });

  useEffect(() => {
    selectedWorkspaceIdRef.current = selectedWorkspaceId;
  }, [selectedWorkspaceId]);

  useEffect(() => {
    let isActive = true;
    setRootState({ status: 'loading' });

    void fetchWorkspaceList()
      .then((response) => {
        if (!isActive) {
          return;
        }
        const items = Array.isArray(response.items) ? response.items : [];
        if (items.length === 0) {
          setSelectedWorkspaceId(null);
          setRootState({ status: 'empty' });
          return;
        }

        const currentSelection = selectedWorkspaceIdRef.current;
        const selectedIsValid = Boolean(
          currentSelection
          && items.some(workspace => workspace.id === currentSelection),
        );
        const workspace = selectedIsValid
          ? items.find(item => item.id === currentSelection) ?? items[0]
          : items[0];
        const workspaceId = workspace.id;
        if (!selectedIsValid) {
          setSelectedWorkspaceId(workspaceId);
        }
        setRootState({
          status: 'ready',
          workspaceId,
          accessRole: workspace.accessRole,
          allowedOperations: workspace.allowedOperations,
        });
      })
      .catch(() => {
        if (isActive) {
          setRootState({ status: 'error' });
        }
      });

    return () => {
      isActive = false;
    };
  }, [
    reloadToken,
    setSelectedWorkspaceId,
  ]);

  const retry = useCallback(() => {
    setReloadToken(current => current + 1);
  }, []);

  const rootProjection = projectWorkspaceEntry({
    identity: { status: 'authenticated' },
    workspace: rootState.status === 'loading'
      ? { status: 'checking' }
      : rootState.status === 'empty'
        ? { status: 'empty', canCreate: canCreateWorkspace }
        : {
            status: 'failed',
            allowedActions: ['refresh'],
            reasonCode: 'WORKSPACE_LIST_UNAVAILABLE',
          },
    execution: {
      status: 'checking',
      allowedActions: [],
    },
  });

  if (rootState.status === 'ready') {
    const permissions = resolveWorkspacePermissions(
      rootState.accessRole,
      rootState.allowedOperations,
    );
    const target = permissions.canUseChat
      ? ROUTES.workspace.home(rootState.workspaceId)
      : ROUTES.workspace.files(rootState.workspaceId);
    return <Navigate to={target} replace />;
  }

  return (
    <EntryFrame
      isPending
      transitionKey="workspace-root"
      projection={rootProjection}
      navigationSlot={navigationSlot}
      onAction={(action) => {
        if (action === 'refresh') {
          retry();
        } else if (action === 'create') {
          navigate(ROUTES.workspace.wizard);
        }
      }}
    >
      {null}
    </EntryFrame>
  );
};

interface WorkspaceExecutionModuleProps extends WorkspaceModuleProps {
  workspaceId: string;
}

const WorkspaceExecutionModule: React.FC<WorkspaceExecutionModuleProps> = ({
  navigationSlot,
  workspaceId,
}) => {
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();
  const { t } = useI18n();
  const { user } = useAuth();
  const userId = user?.sub ?? 'anonymous';

  useEffect(() => {
    if (workspaceId && selectedWorkspaceId !== workspaceId) {
      setSelectedWorkspaceId(workspaceId);
    }
  }, [selectedWorkspaceId, setSelectedWorkspaceId, workspaceId]);

  const workspaceContent = (
    <WorkspaceShell navigationSlot={navigationSlot} userId={userId}>
      <Routes>
          <Route path="home/*" element={
            <WorkspaceHomeRoute workspaceId={workspaceId} userId={userId} />
          } />

          <Route path="files/*" element={(
            <RequireWorkspaceOperation operation={OPERATION_IDS.workspaceDetailRead}>
              <WorkspaceFilesRoute />
            </RequireWorkspaceOperation>
          )} />

          <Route path="version-control/*" element={
            <RequireWorkspaceOperation operation={OPERATION_IDS.workspaceDetailRead}>
              <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.versionControl" />}>
                <VersionControlPage />
              </React.Suspense>
            </RequireWorkspaceOperation>
          } />

          <Route path="workspace-settings/*" element={
            <RequireWorkspaceOperation operation={OPERATION_IDS.workspaceDetailRead}>
              <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.workspaceSettings" />}>
                <WorkspaceSettingsPage />
              </React.Suspense>
            </RequireWorkspaceOperation>
          } />

          <Route path="container-management/*" element={
            <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.containerManagement" />}>
              <ContainerManagementPage />
            </React.Suspense>
          } />

          <Route path="workspace-automation/*" element={
            <RequireWorkspaceOperation operation={OPERATION_IDS.workspaceAutomationExecute}>
              <React.Suspense
                fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.automationTasks" />}
              >
                <WorkspaceAutomationRoute />
              </React.Suspense>
            </RequireWorkspaceOperation>
          } />

          <Route path="claude-code/*" element={<div />} />
          <Route path="opencode/*" element={<div />} />
          <Route path="codex/*" element={<div />} />

          <Route path="canvas" element={<div />} />
          <Route path="browser" element={<div />} />

          <Route path="*" element={<div>{t('workspace.layout.featureNotFound')}</div>} />
      </Routes>
    </WorkspaceShell>
  );

  return workspaceContent;
};

const WorkspaceScopedModule: React.FC<WorkspaceModuleProps> = ({ navigationSlot }) => {
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();

  return (
    <WorkspaceEntryGate
      workspaceId={workspaceId}
      navigationSlot={navigationSlot}
    >
      <WorkspaceExecutionModule
        workspaceId={workspaceId}
        navigationSlot={navigationSlot}
      />
    </WorkspaceEntryGate>
  );
};

export const WorkspaceModule: React.FC<WorkspaceModuleProps> = ({ navigationSlot }) => (
  <Routes>
    <Route
      index
      element={<WorkspaceRootResolver navigationSlot={navigationSlot} />}
    />
    <Route
      path=":workspaceId/*"
      element={<WorkspaceScopedModule navigationSlot={navigationSlot} />}
    />
  </Routes>
);
