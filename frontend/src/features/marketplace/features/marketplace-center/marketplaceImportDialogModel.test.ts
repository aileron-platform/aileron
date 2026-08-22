import { describe, expect, it } from 'vitest';
import type { MarketplaceImportCandidate, MarketplaceImportResult } from '@/features/marketplace/model/marketplaceTypes';
import {
  buildGitImportSource,
  buildImportResultSummary,
  buildUploadedLocalImportSource,
  filterImportCandidates,
  getSelectableCandidateIds,
  getVisibleImportValidationResults,
  initializeImportCandidates,
  isImportCandidateReady,
  isImportScanBlocked,
  resolveLocalUploadTargetClient,
  toggleImportCandidateSelection,
  updateImportCandidateMetadata,
} from './marketplaceImportDialogModel';

const createCandidate = (
  id: string,
  overrides: Partial<MarketplaceImportCandidate> = {},
): MarketplaceImportCandidate => ({
  id,
  targetClient: 'claude-code',
  packageFormat: 'claude-native',
  packageId: id,
  version: '1.0.0',
  displayName: id,
  sourcePath: `plugins/${id}`,
  duplicate: false,
  variantStatus: 'new-family',
  variants: [],
  validationSeverity: 'none',
  validationResults: [],
  ...overrides,
});

describe('marketplaceImportDialogModel', () => {
  it('blocks scanning only when the selected source kind has no usable source', () => {
    expect(isImportScanBlocked({ sourceKind: 'git', source: '  ', localFile: null, uploadedLocalSource: '' })).toBe(true);
    expect(isImportScanBlocked({ sourceKind: 'git', source: ' git@github.com:demo/repo.git ', localFile: null, uploadedLocalSource: '' })).toBe(false);
    expect(isImportScanBlocked({ sourceKind: 'local', source: '', localFile: null, uploadedLocalSource: '' })).toBe(true);
    expect(isImportScanBlocked({ sourceKind: 'local', source: '', localFile: { name: 'pkg.zip' }, uploadedLocalSource: '' })).toBe(false);
    expect(isImportScanBlocked({ sourceKind: 'local', source: '', localFile: null, uploadedLocalSource: 'upload://pkg.zip' })).toBe(false);
  });

  it('builds normalized git and uploaded-local import sources', () => {
    expect(buildGitImportSource('codex', ' https://github.com/example/marketplace.git ')).toEqual({
      targetClient: 'codex',
      sourceKind: 'git',
      source: 'https://github.com/example/marketplace.git',
    });
    expect(buildUploadedLocalImportSource('all', 'upload://pkg.zip')).toEqual({
      targetClient: 'all',
      sourceKind: 'local',
      source: 'upload://pkg.zip',
    });
  });

  it('uses Claude Code as the local upload targetClient when scanning all target clients', () => {
    expect(resolveLocalUploadTargetClient('all')).toBe('claude-code');
    expect(resolveLocalUploadTargetClient('codex')).toBe('codex');
  });

  it('toggles selected candidate ids without mutating the original set', () => {
    const selectedIds = new Set(['one']);

    const removed = toggleImportCandidateSelection(selectedIds, 'one', false);
    const added = toggleImportCandidateSelection(selectedIds, 'two', true);

    expect(Array.from(selectedIds)).toEqual(['one']);
    expect(Array.from(removed)).toEqual([]);
    expect(Array.from(added)).toEqual(['one', 'two']);
  });

  it('initializes version choices and requires explicit replacement for duplicates', () => {
    const candidates = initializeImportCandidates([
      createCandidate('existing', { duplicate: true }),
    ]);
    expect(isImportCandidateReady(candidates[0])).toBe(false);
    const updated = updateImportCandidateMetadata(candidates, 'existing', {
      version: '1.0.0-internal.1',
      overwrite: true,
    });

    expect(isImportCandidateReady(updated[0])).toBe(true);
    expect(updated[0].import).toEqual({
      version: '1.0.0-internal.1',
      overwrite: true,
    });
    expect(candidates[0].import?.version).toBe('1.0.0');
  });

  it('filters hidden import validation codes from candidate display', () => {
    const visible = getVisibleImportValidationResults(createCandidate('pkg', {
      validationResults: [
        { severity: 'warning', code: 'marketplace.validation.metadata_conflict', messageKey: 'marketplace.validation.metadata_conflict' },
        { severity: 'warning', code: 'marketplace.import.duplicate', messageKey: 'marketplace.import.validation.duplicate' },
      ],
    }));

    expect(visible).toEqual([
      expect.objectContaining({ code: 'marketplace.import.duplicate' }),
    ]);
  });

  it('builds import summaries from result counts and selected duplicate candidates', () => {
    const result: MarketplaceImportResult = {
      imported: [],
      failed: [createCandidate('failed', {
        errorCode: 'marketplace.import.failed',
        stage: 'copy',
        category: 'filesystem',
      })],
      warnings: [{ severity: 'warning', code: 'marketplace.warning', messageKey: 'marketplace.warning' }],
    };

    expect(buildImportResultSummary(result, [
      createCandidate('new'),
      createCandidate('duplicate', { duplicate: true }),
    ])).toEqual({
      imported: 0,
      failed: 1,
      duplicates: 1,
      warnings: 1,
    });
  });

  it('returns all candidate ids for select-all actions', () => {
    expect(getSelectableCandidateIds([
      createCandidate('one'),
      createCandidate('two'),
    ])).toEqual(['one', 'two']);
  });

  it('filters candidates across identifying fields with case-insensitive keyword matching', () => {
    const candidates = [
      createCandidate('review-assistant', {
        displayName: 'Review Assistant',
        sourceIdentity: 'openai/plugins',
      }),
      createCandidate('security-audit', {
        displayName: 'Security Audit',
        targetClient: 'codex',
        packageFormat: 'codex-native',
        familyDisplayName: 'Engineering Tools',
      }),
    ];

    expect(filterImportCandidates(candidates, 'SECURITY codex')).toEqual([
      expect.objectContaining({ id: 'security-audit' }),
    ]);
    expect(filterImportCandidates(candidates, 'engineering native')).toEqual([
      expect.objectContaining({ id: 'security-audit' }),
    ]);
    expect(filterImportCandidates(candidates, 'openai/plugins')).toEqual([
      expect.objectContaining({ id: 'review-assistant' }),
    ]);
    expect(filterImportCandidates(candidates, '   ')).toBe(candidates);
  });
});
