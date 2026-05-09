import type { MarketplacePackageDetail, MarketplaceProvider } from '@/shared/types/marketplace';

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

const createMarketplaceSourceValue = (provider: MarketplaceProvider, sourcePath: string): string | Record<string, string> => (
  provider === 'codex'
    ? { source: 'local', path: sourcePath }
    : sourcePath
);

const createMarketplaceListingJson = (
  provider: MarketplaceProvider,
  draft: Pick<MarketplaceRequiredDraft, 'packageName' | 'sourcePath' | 'codexInstallationPolicy' | 'codexAuthenticationPolicy' | 'category'>,
): Record<string, unknown> => {
  if (provider === 'gemini') {
    return {};
  }

  const entry: Record<string, unknown> = {
    name: draft.packageName,
    source: createMarketplaceSourceValue(provider, draft.sourcePath),
  };

  if (provider === 'codex') {
    entry.policy = {
      installation: draft.codexInstallationPolicy,
      authentication: draft.codexAuthenticationPolicy,
    };
    entry.category = draft.category;
  }

  return entry;
};

const createMarketplaceManifestJson = (
  provider: MarketplaceProvider,
  draft: Pick<MarketplaceRequiredDraft, 'manifestName' | 'manifestVersion' | 'manifestDescription'>,
): Record<string, unknown> => ({
  name: draft.manifestName,
  ...(provider === 'claude-code' ? {} : { version: draft.manifestVersion }),
  ...(provider === 'codex' ? { description: draft.manifestDescription } : {}),
});

export const createInitialMarketplaceRequiredDraft = (
  provider: MarketplaceProvider,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const fallbackPackageName = packageId || displayName;
  const fallbackDescription = description || fallbacks.description;
  const draft = {
    marketplaceName: provider === 'codex' ? fallbacks.codexMarketplaceName : fallbacks.claudeMarketplaceName,
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
    listingJson: provider === 'gemini'
      ? ''
      : stringifyMarketplaceJson(createMarketplaceListingJson(provider, draft)),
    manifestJson: stringifyMarketplaceJson(createMarketplaceManifestJson(provider, draft)),
  };
};

export const createMarketplaceRequiredDraftFromDetail = (
  provider: MarketplaceProvider,
  detail: MarketplacePackageDetail | null,
  packageId: string,
  displayName: string,
  description: string,
  fallbacks: MarketplaceRequiredDraftFallbacks,
): MarketplaceRequiredDraft => {
  const draft = createInitialMarketplaceRequiredDraft(provider, packageId, displayName, description, fallbacks);
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
      ...(provider !== 'claude-code' ? { version: getStringField(manifest.version, detail.version ?? draft.manifestVersion) } : {}),
      ...(provider === 'codex' ? { description: manifestDescription } : {}),
    }),
  };
  return {
    ...next,
    listingJson: provider === 'gemini'
      ? ''
      : mergeMarketplaceListingJson(provider, draft.listingJson, next),
  };
};

export const mergeMarketplaceListingJson = (
  provider: MarketplaceProvider,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};

  const nextEntry: Record<string, unknown> = {
    ...current,
    name: draft.packageName,
    source: createMarketplaceSourceValue(provider, draft.sourcePath),
  };

  if (provider === 'codex') {
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
  provider: MarketplaceProvider,
  currentJson: string,
  draft: MarketplaceRequiredDraft,
): string => {
  const current = parseMarketplaceJsonObject(currentJson) ?? {};
  const next: Record<string, unknown> = {
    ...current,
    name: draft.manifestName,
  };

  if (provider !== 'claude-code') {
    next.version = draft.manifestVersion;
  }
  if (provider === 'codex') {
    next.description = draft.manifestDescription;
  }

  return stringifyMarketplaceJson(next);
};
