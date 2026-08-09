import type {
  MarketplaceImportCandidate,
  MarketplaceImportProvider,
  MarketplaceImportResult,
  MarketplaceImportSource,
  MarketplaceProvider,
  MarketplaceValidationResult,
} from '@/features/marketplace/model/marketplaceTypes';
import { IMPORT_SCAN_HIDDEN_VALIDATION_CODES } from './marketplaceCenterModel';

export interface ImportScanBlockState {
  sourceKind: MarketplaceImportSource['sourceKind'];
  source: string;
  localFile: Pick<File, 'name'> | null;
  uploadedLocalSource: string;
}

export interface ImportResultSummary {
  imported: number;
  skipped: number;
  failed: number;
  duplicates: number;
  warnings: number;
}

export const isImportScanBlocked = ({
  sourceKind,
  source,
  localFile,
  uploadedLocalSource,
}: ImportScanBlockState) => (
  sourceKind === 'git'
    ? !source.trim()
    : !localFile && !uploadedLocalSource
);

export const buildGitImportSource = (
  provider: MarketplaceImportProvider,
  source: string,
): MarketplaceImportSource => ({
  provider,
  sourceKind: 'git',
  source: source.trim(),
});

export const buildUploadedLocalImportSource = (
  provider: MarketplaceImportProvider,
  uploadedLocalSource: string,
): MarketplaceImportSource => ({
  provider,
  sourceKind: 'local',
  source: uploadedLocalSource,
});

export const resolveLocalUploadProvider = (
  provider: MarketplaceImportProvider,
): MarketplaceProvider => (provider === 'all' ? 'claude-code' : provider);

export const toggleImportCandidateSelection = (
  selectedIds: Set<string>,
  candidateId: string,
  checked: boolean,
) => {
  const next = new Set(selectedIds);
  if (checked) {
    next.add(candidateId);
  } else {
    next.delete(candidateId);
  }
  return next;
};

export const getSelectableCandidateIds = (
  candidates: MarketplaceImportCandidate[],
) => candidates.map(candidate => candidate.id);

export const updateImportCandidateDuplicateAction = (
  candidates: MarketplaceImportCandidate[],
  candidateId: string,
  duplicateAction: MarketplaceImportCandidate['duplicateAction'],
) => candidates.map(candidate => (
  candidate.id === candidateId ? { ...candidate, duplicateAction } : candidate
));

export const updateImportCandidateNewPackageId = (
  candidates: MarketplaceImportCandidate[],
  candidateId: string,
  newPackageId: string,
) => candidates.map(candidate => (
  candidate.id === candidateId ? { ...candidate, newPackageId } : candidate
));

export const getVisibleImportValidationResults = (
  candidate: MarketplaceImportCandidate,
): MarketplaceValidationResult[] => candidate.validationResults.filter(
  result => !IMPORT_SCAN_HIDDEN_VALIDATION_CODES.has(result.code),
);

export const buildImportResultSummary = (
  result: MarketplaceImportResult,
  selectedCandidates: MarketplaceImportCandidate[],
): ImportResultSummary => ({
  imported: result.imported.length,
  skipped: result.skipped.length,
  failed: result.failed.length,
  duplicates: selectedCandidates.filter(candidate => candidate.duplicate).length,
  warnings: result.warnings.length,
});
