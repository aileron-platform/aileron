import type {
  MarketplaceImportCandidate,
  MarketplaceImportTargetClient,
  MarketplaceImportResult,
  MarketplaceImportSource,
  MarketplaceImportMetadata,
  MarketplaceTargetClient,
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
  targetClient: MarketplaceImportTargetClient,
  source: string,
): MarketplaceImportSource => ({
  targetClient,
  sourceKind: 'git',
  source: source.trim(),
});

export const buildUploadedLocalImportSource = (
  targetClient: MarketplaceImportTargetClient,
  uploadedLocalSource: string,
): MarketplaceImportSource => ({
  targetClient,
  sourceKind: 'local',
  source: uploadedLocalSource,
});

export const resolveLocalUploadTargetClient = (
  targetClient: MarketplaceImportTargetClient,
): MarketplaceTargetClient => (targetClient === 'all' ? 'claude-code' : targetClient);

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

export const filterImportCandidates = (
  candidates: MarketplaceImportCandidate[],
  query: string,
): MarketplaceImportCandidate[] => {
  const keywords = query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (keywords.length === 0) {
    return candidates;
  }

  return candidates.filter(candidate => {
    const searchableText = [
      candidate.displayName,
      candidate.packageId,
      candidate.sourcePath,
      candidate.familyDisplayName,
      candidate.sourceIdentity,
      candidate.targetClient,
      candidate.packageFormat,
    ]
      .filter((value): value is string => Boolean(value))
      .join('\n')
      .toLowerCase();

    return keywords.every(keyword => searchableText.includes(keyword));
  });
};

export const createImportMetadata = (
  candidate: MarketplaceImportCandidate,
): MarketplaceImportMetadata => ({
  version: candidate.version || '1.0.0',
  overwrite: false,
});

export const initializeImportCandidates = (
  candidates: MarketplaceImportCandidate[],
) => candidates.map(candidate => ({
  ...candidate,
  import: createImportMetadata(candidate),
}));

export const updateImportCandidateMetadata = (
  candidates: MarketplaceImportCandidate[],
  candidateId: string,
  patch: Partial<MarketplaceImportMetadata>,
) => candidates.map(candidate => (
  candidate.id === candidateId && candidate.import
    ? { ...candidate, import: { ...candidate.import, ...patch } }
    : candidate
));

const SEMVER_PATTERN = /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;

export const isImportCandidateReady = (
  candidate: MarketplaceImportCandidate,
): boolean => Boolean(
  candidate.import
  && SEMVER_PATTERN.test(candidate.import.version)
  && (!candidate.duplicate || candidate.import.overwrite),
);

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
  failed: result.failed.length,
  duplicates: selectedCandidates.filter(candidate => candidate.duplicate).length,
  warnings: result.warnings.length,
});
