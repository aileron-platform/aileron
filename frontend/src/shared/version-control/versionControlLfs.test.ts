import { describe, expect, it } from 'vitest';
import {
  getLfsConversionProgress,
  isCompleteLfsSnapshotPreview,
  normalizeLfsPatterns,
} from './versionControlLfs';

describe('versionControlLfs', () => {
  it('trims patterns, removes blank values, and deduplicates without reordering', () => {
    expect(normalizeLfsPatterns([
      ' *.zip ',
      '',
      '*.pdf',
      '*.zip',
      '   ',
      '*.pdf',
    ])).toEqual(['*.zip', '*.pdf']);
  });

  it('only treats a preview as complete when every matched path is present', () => {
    expect(isCompleteLfsSnapshotPreview({
      matchedTotal: 2,
      totalSize: 1024,
      pathSample: ['assets/a.zip', 'assets/b.zip'],
    })).toBe(true);
    expect(isCompleteLfsSnapshotPreview({
      matchedTotal: 101,
      totalSize: 1024,
      pathSample: Array.from({ length: 100 }, (_, index) => `asset-${index}.zip`),
    })).toBe(false);
  });

  it('clamps conversion progress and handles an empty total', () => {
    expect(getLfsConversionProgress(3, 4)).toBe(75);
    expect(getLfsConversionProgress(12, 4)).toBe(100);
    expect(getLfsConversionProgress(1, 0)).toBe(0);
  });
});
