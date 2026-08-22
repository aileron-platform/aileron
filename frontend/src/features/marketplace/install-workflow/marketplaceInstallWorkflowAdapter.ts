import type { QueryClient } from '@tanstack/react-query';
import {
  fetchWorkspaceList,
  invalidateMarketplaceUserScopeSettingsQueries,
} from '@/features/workspace/public';
import { isAgenticTool } from '@/shared/types/agenticTool';
import {
  createMarketplaceUserCopy,
  getPackage,
  installMarketplacePlugin,
  preflightMarketplaceUserCopy,
  refreshMarketplacePackage,
} from '../api/marketplaceApi';
import type {
  MarketplacePackageSummary,
  MarketplaceTargetClient,
} from '../model/marketplaceTypes';
import {
  MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID,
  MARKETPLACE_STORAGE_USER_SCOPE,
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceInstallWorkspaceId,
} from '../storage/marketplaceStorage';
import type {
  MarketplaceInstallWorkflowAdapter,
  MarketplaceInstallWorkspaceOption,
} from './marketplaceInstallWorkflow';

export const createMarketplaceInstallWorkflowAdapter = (
  queryClient: QueryClient,
  publishRefreshedItem: (item: MarketplacePackageSummary) => void,
): MarketplaceInstallWorkflowAdapter => ({
  loadWorkspaceInventory: async () => {
    const result = await fetchWorkspaceList();
    const options: MarketplaceInstallWorkspaceOption[] = result.items.map(
      workspace => ({
        id: workspace.id,
        label: workspace.name || workspace.id,
        agenticTools: (workspace.agenticTools ?? [])
          .filter(isAgenticTool)
          .filter(
            (agenticTool): agenticTool is MarketplaceTargetClient =>
              agenticTool !== 'opencode',
          ),
      }),
    );
    return {
      options,
      selectedWorkspaceId: resolveMarketplaceInstallWorkspaceId(
        options,
        MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID,
        MARKETPLACE_STORAGE_USER_SCOPE,
      ),
    };
  },
  rememberWorkspace: workspaceId => {
    saveMarketplaceInstallWorkspaceId(
      MARKETPLACE_STORAGE_USER_SCOPE,
      workspaceId,
    );
  },
  preflightUserCopy: preflightMarketplaceUserCopy,
  installPlugin: installMarketplacePlugin,
  applyUserCopy: createMarketplaceUserCopy,
  refreshPackage: async (targetClient, packageId, packageFormat) => {
    await refreshMarketplacePackage(targetClient, packageId, packageFormat);
    return getPackage(targetClient, packageId, packageFormat);
  },
  invalidateUserScopeSettings: async (targetClient, workspaceId) => {
    await invalidateMarketplaceUserScopeSettingsQueries(
      queryClient,
      targetClient,
      workspaceId,
    );
  },
  publishRefreshedItem,
});
