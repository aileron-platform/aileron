export interface VersionControlLfsPatterns {
  patterns: string[];
}

export interface VersionControlLfsSnapshotPreview {
  matchedTotal: number;
  totalSize: number;
  pathSample: string[];
}

export interface VersionControlLfsPatternsUpdatePayload {
  patterns: string[];
}

export interface VersionControlLfsSnapshotConvertPayload {
  paths: string[];
}

export const normalizeLfsPatterns = (patterns: readonly string[]): string[] => (
  [...new Set(patterns.map(pattern => pattern.trim()).filter(Boolean))]
);

export const isCompleteLfsSnapshotPreview = (
  preview: VersionControlLfsSnapshotPreview,
): boolean => preview.matchedTotal === preview.pathSample.length;

export const getLfsConversionProgress = (
  current: number,
  total: number,
): number => {
  if (total <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((current / total) * 100)));
};
