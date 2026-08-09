import type {
  MarketplaceLifecycleStatus,
  MarketplaceValidationResult,
} from './marketplaceTypes';

export type MarketplaceDocumentResourceType =
  | 'commands'
  | 'subagents'
  | 'output-styles';

export interface MarketplacePackageMutationResult {
  success: true;
  path: string;
  revision: string;
  ownerFilePath: string | null;
  baseEntryFingerprint: string | null;
}

export interface MarketplaceDocumentSummary {
  id: string;
  title: string;
  path: string;
  resourceType: string;
  content?: string;
  ownerFilePath?: string | null;
  baseEntryFingerprint?: string | null;
}

export type MarketplaceDocumentMutationResult = MarketplacePackageMutationResult;

export interface MarketplaceDocumentMutationPayload {
  revision: string;
  path: string;
  content: string;
  ownerFilePath?: string;
  baseEntryFingerprint?: string;
}

export interface MarketplaceDocumentRenamePayload {
  revision: string;
  previousPath: string;
  nextPath: string;
  ownerFilePath?: string;
  baseEntryFingerprint?: string;
}

export interface MarketplaceDocumentRemovePayload {
  revision: string;
  ownerFilePath?: string;
  baseEntryFingerprint?: string;
}

export interface MarketplaceBasicResource {
  revision: string;
  displayName: string;
  description?: string;
  catalogMetadata: Record<string, unknown>;
  manifestMetadata: Record<string, unknown>;
  lifecycleStatus: MarketplaceLifecycleStatus;
  validationResults: MarketplaceValidationResult[];
}

export interface MarketplaceBasicUpdatePayload {
  revision: string;
  displayName?: string;
  description?: string;
  catalogMetadata?: Record<string, unknown>;
  manifestMetadata?: Record<string, unknown>;
}
