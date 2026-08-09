import { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { parseWorkspaceOpenPath } from '@/shared/components/markdown/markdownLinkUtils';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../providers/WorkspaceProvider';

const logger = createLogger('useWorkspaceFileOpenQuery');

export const useWorkspaceFileOpenQuery = (): void => {
  const location = useLocation();
  const navigate = useNavigate();
  const routeWorkspaceId = useParams().workspaceId ?? null;
  const {
    dispatch,
    fileManagementTabsRestoreStatus,
    openFileInTab,
    state,
    workspaceRuntime,
  } = useWorkspace();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const open = params.get('open');
    const workspaceId = workspaceRuntime.workspaceId;
    const contextId = state.versionControl.selectedGitContextId;

    if (
      !open ||
      !workspaceId ||
      !routeWorkspaceId ||
      workspaceId !== routeWorkspaceId ||
      !fileManagementTabsRestoreStatus.ready ||
      fileManagementTabsRestoreStatus.workspaceId !== routeWorkspaceId ||
      fileManagementTabsRestoreStatus.contextId !== contextId
    ) {
      return;
    }

    const canonicalPath = ROUTES.workspace.files(workspaceId);
    const parsed = parseWorkspaceOpenPath(open);
    if (!parsed) {
      logger.warn('Workspace file open query ignored invalid path', { path: open });
      navigate(canonicalPath, { replace: true });
      return;
    }

    dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'file-management' });
    dispatch({ type: 'ENSURE_NAVIGATION_ITEM_EXPANDED', payload: 'file-management' });
    openFileInTab(parsed.filePath);
    navigate(canonicalPath, { replace: true });
  }, [
    dispatch,
    fileManagementTabsRestoreStatus,
    location.search,
    navigate,
    openFileInTab,
    routeWorkspaceId,
    state.versionControl.selectedGitContextId,
    workspaceRuntime.workspaceId,
  ]);
};
