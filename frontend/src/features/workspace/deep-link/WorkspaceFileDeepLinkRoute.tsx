import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';
import {
  encodeWorkspaceOpenPath,
  parseWorkspaceLocationPathname,
} from '@/shared/components/markdown/markdownLinkUtils';
import { fetchDefaultWorkspaceId } from '../api/workspaceRuntimeApi';
import { useWorkspaceSelection } from '../selection/WorkspaceSelectionContext';

const logger = createLogger('WorkspaceFileDeepLinkRoute');

export const WorkspaceFileDeepLinkRoute = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedWorkspaceId } = useWorkspaceSelection();

  useEffect(() => {
    let cancelled = false;

    const redirect = async () => {
      let workspaceId = selectedWorkspaceId;
      if (!workspaceId) {
        try {
          workspaceId = await fetchDefaultWorkspaceId();
        } catch (error) {
          logger.warn('Workspace file deep link could not resolve a workspace', { error });
          if (!cancelled) {
            navigate(ROUTES.workspace.root, { replace: true });
          }
          return;
        }
      }

      const target = ROUTES.workspace.files(workspaceId);
      const parsed = parseWorkspaceLocationPathname(location.pathname);
      if (!parsed) {
        logger.warn('Workspace file deep link ignored invalid path', { pathname: location.pathname });
        if (!cancelled) {
          navigate(target, { replace: true });
        }
        return;
      }

      if (!cancelled) {
        navigate(`${target}?open=${encodeWorkspaceOpenPath(parsed.filePath)}`, { replace: true });
      }
    };

    void redirect();

    return () => {
      cancelled = true;
    };
  }, [location.pathname, navigate, selectedWorkspaceId]);

  return null;
};
