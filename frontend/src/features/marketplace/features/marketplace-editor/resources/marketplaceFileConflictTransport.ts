import type { FileConflictWorkflowTransport } from '@/shared/components/file-workbench';
import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import {
  executeMarketplaceFileConflictOperation,
  executeMarketplaceSkillFileConflictOperation,
  preflightMarketplaceFileConflicts,
  preflightMarketplaceSkillFileConflicts,
  type MarketplaceFileConflictPayload,
  type MarketplaceSkillFileConflictPayload,
} from '../../../api/marketplaceApi';

export const createMarketplaceFileConflictTransport = (
  provider: MarketplaceProvider,
  packageId: string,
): FileConflictWorkflowTransport<MarketplaceFileConflictPayload> => ({
  preflight: (request, options) => preflightMarketplaceFileConflicts(
    provider,
    packageId,
    request,
    options,
  ),
  execute: (request, options) => executeMarketplaceFileConflictOperation(
    provider,
    packageId,
    request,
    options,
  ),
});

export const createMarketplaceSkillFileConflictTransport = (
  provider: MarketplaceProvider,
  packageId: string,
  revision: string,
): FileConflictWorkflowTransport<MarketplaceSkillFileConflictPayload> => ({
  preflight: (request, options) => preflightMarketplaceSkillFileConflicts(
    provider,
    packageId,
    revision,
    request,
    options,
  ),
  execute: (request, options) => executeMarketplaceSkillFileConflictOperation(
    provider,
    packageId,
    {
      ...request,
      payload: { ...request.payload, revision },
    },
    options,
  ),
});
