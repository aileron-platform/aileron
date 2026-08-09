export {
  WorkspaceSelectionProvider,
  useWorkspaceSelection,
} from './selection/WorkspaceSelectionContext';
export { readSelectedWorkspaceId } from './selection/workspaceSelectionStorage';
export { WorkspaceFileDeepLinkRoute } from './deep-link/WorkspaceFileDeepLinkRoute';
export { fetchWorkspaceList } from './api/workspaceListApi';
export type { WorkspaceDetailResponse } from './api/workspaceApiTypes';
export type { WorkspaceListItem, WorkspaceListResponse } from './model/workspaceTypes';
export { resolveWorkspacePermissions } from './model/workspacePermissions';
export { projectWorkspaceEntry } from './entry/workspaceEntryProjection';
export {
  buildPluginDetailHref,
  invalidateMarketplaceUserScopeSettingsQueries,
  invalidateProviderResourceQueries,
} from './features/agent-settings/model/pluginResources';

export const loadWorkspaceModule = () =>
  import('./WorkspaceModule').then(({ WorkspaceModule }) => ({
    default: WorkspaceModule,
  }));
