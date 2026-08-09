import { useEffect, useMemo, useRef, type Dispatch } from 'react';
import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';
import { buildWorkspaceLayoutPreferences } from '../workspaceProviderModel';
import {
  loadWorkspaceLayoutPreferences,
  saveWorkspaceLayoutPreferences,
} from '../../storage/workspaceLayoutStorage';

interface UseWorkspaceLayoutPersistenceOptions {
  workspaceId: string | null;
  state: WorkspaceState;
  dispatch: Dispatch<WorkspaceAction>;
}

export const useWorkspaceLayoutPersistence = ({
  workspaceId,
  state,
  dispatch,
}: UseWorkspaceLayoutPersistenceOptions) => {
  const stateRef = useRef(state);
  stateRef.current = state;
  const previousRestoredWorkspaceIdRef = useRef<string | null>(null);
  const {
    companionActiveTab,
    companionTerminalPlacement,
    expandedNavigationItems,
    fileTreeShowHiddenEntries,
  } = state;
  const layoutPreferences = useMemo(
    () => buildWorkspaceLayoutPreferences({
      companionActiveTab,
      companionTerminalPlacement,
      expandedNavigationItems,
      fileTreeShowHiddenEntries,
    }),
    [
      companionActiveTab,
      companionTerminalPlacement,
      expandedNavigationItems,
      fileTreeShowHiddenEntries,
    ],
  );

  useEffect(() => {
    if (!workspaceId) return;

    const previousId = previousRestoredWorkspaceIdRef.current;
    if (previousId && previousId !== workspaceId) {
      saveWorkspaceLayoutPreferences(previousId, buildWorkspaceLayoutPreferences(stateRef.current));
    }

    const saved = loadWorkspaceLayoutPreferences(workspaceId);
    if (saved) {
      dispatch({ type: 'RESTORE_LAYOUT_PREFERENCES', payload: saved });
    }
    previousRestoredWorkspaceIdRef.current = workspaceId;
  }, [dispatch, workspaceId]);

  useEffect(() => {
    if (!workspaceId || previousRestoredWorkspaceIdRef.current !== workspaceId) return;

    const timeoutId = setTimeout(() => {
      saveWorkspaceLayoutPreferences(workspaceId, layoutPreferences);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [layoutPreferences, workspaceId]);
};
