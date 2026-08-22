import type { MarketplacePackageDetail, MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';

export interface MarketplaceRequiredDraft {
  marketplaceName: string;
  ownerName: string;
  packageName: string;
  sourcePath: string;
  codexInstallationPolicy: string;
  codexAuthenticationPolicy: string;
  category: string;
  manifestName: string;
  manifestVersion: string;
  manifestDescription: string;
  listingJson: string;
  manifestJson: string;
  listingJsonError: string | null;
  manifestJsonError: string | null;
}

export interface MarketplaceRequiredDraftFallbacks {
  packageName: string;
  codexMarketplaceName: string;
  claudeMarketplaceName: string;
  ownerName: string;
  description: string;
}

const marketplaceJsonIndent = 2;

export const stringifyMarketplaceJson = (value: Record<string, unknown>): string => (
  JSON.stringify(value, null, marketplaceJsonIndent)
);

export const isJsonObject = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

export const getStringField = (value: unknown, fallback = ''): string => (
  typeof value === 'string' ? value : fallback
);

export const parseMarketplaceJsonObject = (value: string): Record<string, unknown> | null => {
  try {
    const parsed: unknown = JSON.parse(value);
    return isJsonObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
};

const createMarketplaceSourceValue = (targetClient: MarketplaceTargetClient, sourcePath: string): string | Record<string, string> => (
  targetClient === 'codex'
    ? { source: 'local', path: sourcePath }
    : sourcePath
);

const createMarketplaceListingJson = (
  targetClient: MarketplaceTargetClient,
  draft: Pick<MarketplaceRequiredDraft, 'packageName' | 'sourcePath' | 'codexInstallationPolicy' | 'codexAuthenticationPolicy' | 'category'>,
): Record<string, unknown> => {
  const entry: Record<string, unknown> = {
    name: draft.packageName,
    source: createMarketplaceSourceValue(targetClient, draft.sourcePath),
  };

  if (targetClient === 'codex') {
    entry.policy = {
      installation: draft.codexInstallationPolicy,
      authentication: draft.codexAuthenticationPolicy,
    };
    entry.category = draft.category;
  }

  return entry;
};

const createMarketplaceManifestJson = (
  targetClient: MarketplaceTargetClient,
  draft: Pick<MarketplaceRequiredDraft, 'manifestName' | 'manifestVersion' | 'manifestDescription'>,
): Record<string, unknown> => ({
  name: draft.manifestName,
  ...(targetClient === 'claude-code' ? {} : { version: draft.manifestVersion }),
  ...(targetClient === 'codex' ? { description: draft.manifestDescription } : {}),
});

export const createInitialMarketplaceRequiredDraft = (
  targetClient: MarketplaceTargetClient,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const fallbackPackageName = packageId || displayName;
  const fallbackDescription = description || fallbacks.description;
  const draft = {
    marketplaceName: targetClient === 'codex' ? fallbacks.codexMarketplaceName : fallbacks.claudeMarketplaceName,
    ownerName: fallbacks.ownerName,
    packageName: fallbackPackageName,
    sourcePath: `./plugins/${fallbackPackageName}`,
    codexInstallationPolicy: 'AVAILABLE',
    codexAuthenticationPolicy: 'ON_INSTALL',
    category: 'Productivity',
    manifestName: fallbackPackageName,
    manifestVersion: '0.1.0',
    manifestDescription: fallbackDescription,
    listingJson: '',
    manifestJson: '',
    listingJsonError: null,
    manifestJsonError: null,
  };

  return {
    ...draft,
    listingJson: stringifyMarketplaceJson(createMarketplaceListingJson(targetClient, draft)),
    manifestJson: stringifyMarketplaceJson(createMarketplaceManifestJson(targetClient, draft)),
  };
};

export const createMarketplaceRequiredDraftFromDetail = (
  targetClient: MarketplaceTargetClient,
  detail: MarketplacePackageDetail | null,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const draft = createInitialMarketplaceRequiredDraft(targetClient, packageId, displayName, description, fallbacks);
  if (!detail) return draft;
  const manifest = isJsonObject(detail.manifestMetadata) ? detail.manifestMetadata : {};
  const manifestName = getStringField(manifest.name, detail.packageId);
  const manifestDescription = getStringField(manifest.description, detail.description ?? draft.manifestDescription);
  const next = {
    ...draft,
    packageName: detail.packageId,
    manifestName,
    manifestVersion: getStringField(manifest.version, detail.version ?? draft.manifestVersion),
    manifestDescription,
    manifestJson: stringifyMarketplaceJson({
      ...manifest,
      name: manifestName,
      ...(targetClient !== 'claude-code' ? { version: getStringField(manifest.version, detail.version ?? draft.manifestVersion) } : {}),
      ...(targetClient === 'codex' ? { description: manifestDescription } : {}),
    }),
  };
  return {
    ...next,
    listingJson: mergeMarketplaceListingJson(targetClient, draft.listingJson, next),
  };
};

export const mergeMarketplaceListingJson = (
  targetClient: MarketplaceTargetClient,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};

  const nextEntry: Record<string, unknown> = {
    ...current,
    name: draft.packageName,
    source: createMarketplaceSourceValue(targetClient, draft.sourcePath),
  };

  if (targetClient === 'codex') {
    const policy = isJsonObject(current.policy) ? current.policy : {};
    nextEntry.policy = {
      ...policy,
      installation: draft.codexInstallationPolicy,
      authentication: draft.codexAuthenticationPolicy,
    };
    nextEntry.category = draft.category;
  }

  return stringifyMarketplaceJson(nextEntry);
};

export const mergeMarketplaceManifestJson = (
  targetClient: MarketplaceTargetClient,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};
  const next: Record<string, unknown> = {
    ...current,
    name: draft.manifestName,
  };

  if (targetClient !== 'claude-code') {
    next.version = draft.manifestVersion;
  }
  if (targetClient === 'codex') {
    next.description = draft.manifestDescription;
  }

  return stringifyMarketplaceJson(next);
};
