import type { FileConflictWorkflowTransport } from '@/shared/components/file-workbench';
import type { MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';
import {
  executeMarketplaceFileConflictOperation,
  executeMarketplaceSkillFileConflictOperation,
  preflightMarketplaceFileConflicts,
  preflightMarketplaceSkillFileConflicts,
  type MarketplaceFileConflictPayload,
  type MarketplaceSkillFileConflictPayload,
} from '../../../api/marketplaceApi';

export const createMarketplaceFileConflictTransport = (
  targetClient: MarketplaceTargetClient,
  packageId: string,
): FileConflictWorkflowTransport<MarketplaceFileConflictPayload> => ({
  preflight: (request, options) => preflightMarketplaceFileConflicts(
    targetClient,
    packageId,
    request,
    options,
  ),
  execute: (request, options) => executeMarketplaceFileConflictOperation(
    targetClient,
    packageId,
    request,
    options,
  ),
});

export const createMarketplaceSkillFileConflictTransport = (
  targetClient: MarketplaceTargetClient,
  packageId: string,
  revision: string,
): FileConflictWorkflowTransport<MarketplaceSkillFileConflictPayload> => ({
  preflight: (request, options) => preflightMarketplaceSkillFileConflicts(
    targetClient,
    packageId,
    revision,
    request,
    options,
  ),
  execute: (request, options) => executeMarketplaceSkillFileConflictOperation(
    targetClient,
    packageId,
    {
      ...request,
      payload: { ...request.payload, revision },
    },
    options,
  ),
});
