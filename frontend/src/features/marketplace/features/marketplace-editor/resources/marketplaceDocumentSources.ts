import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import type {
  DocumentResourceItem,
  ResourceListResult,
} from '@/shared/components/document-resource';
import {
  createDocument,
  listDocuments,
  loadDocument,
  removeDocument,
  renameDocument,
  updateDocument,
} from '../../../api/marketplaceApi';
import type {
  MarketplaceDocumentMutationResult,
  MarketplaceDocumentRemovePayload,
  MarketplaceDocumentRenamePayload,
  MarketplaceDocumentResourceType,
  MarketplaceDocumentSummary,
} from '../../../model/marketplaceMutation';
import type { MarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

export interface MarketplaceDocumentMutation {
  document: DocumentResourceItem;
  result: MarketplaceDocumentMutationResult;
}

export interface MarketplaceDocumentSource {
  list(): Promise<ResourceListResult>;
  loadContent(document: DocumentResourceItem): Promise<DocumentResourceItem>;
  create(document: DocumentResourceItem): Promise<MarketplaceDocumentMutation>;
  update(document: DocumentResourceItem): Promise<MarketplaceDocumentMutation>;
  move(
    document: DocumentResourceItem,
    nextPath: string,
  ): Promise<MarketplaceDocumentMutation>;
  remove(document: DocumentResourceItem): Promise<MarketplaceDocumentMutationResult>;
}

const MARKETPLACE_DOCUMENT_RESOURCE_ROOT: Record<
  MarketplaceProvider,
  Record<MarketplaceDocumentResourceType, string>
> = {
  'claude-code': {
    commands: 'commands',
    subagents: 'agents',
    'output-styles': 'output-styles',
  },
  codex: {
    commands: 'prompts',
    subagents: 'agents',
    'output-styles': 'output-styles',
  },
};

export const marketplaceDocumentResourcePath = (
  rawPath: string,
  provider: MarketplaceProvider,
  resourceType: MarketplaceDocumentResourceType,
): string => {
  const root = MARKETPLACE_DOCUMENT_RESOURCE_ROOT[provider][resourceType];
  const segments = rawPath.trim().replace(/^\/+/, '').replace(/\/+$/, '').split('/').filter(Boolean);
  if (segments[0] === root) {
    segments.shift();
  }
  const lastIndex = segments.length - 1;
  if (lastIndex >= 0 && !/\.[^./]+$/.test(segments[lastIndex])) {
    segments[lastIndex] = `${segments[lastIndex]}.md`;
  }
  return [root, ...segments].join('/');
};

export const MARKETPLACE_TAB_TO_DOCUMENT_RESOURCE = {
  commands: 'commands',
  agents: 'subagents',
  outputStyle: 'output-styles',
} as const;

export function createMarketplaceDocumentSource(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  session: MarketplaceResourceSession,
  identityGeneration: number,
): MarketplaceDocumentSource {
  const tokenByPath = new Map<string, {
    ownerFilePath?: string;
    baseEntryFingerprint?: string;
  }>();
  const recordToken = (
    path: string,
    ownerFilePath: string | null | undefined,
    baseEntryFingerprint: string | null | undefined,
  ): void => {
    tokenByPath.set(path, {
      ...(ownerFilePath ? { ownerFilePath } : {}),
      ...(baseEntryFingerprint ? { baseEntryFingerprint } : {}),
    });
  };
  const stripDocument = (raw: MarketplaceDocumentSummary): DocumentResourceItem => {
    recordToken(raw.path, raw.ownerFilePath, raw.baseEntryFingerprint);
    return {
      id: raw.id,
      title: raw.title,
      description: raw.path,
      scope: 'project',
      content: raw.content ?? '',
      metadata: {
        fileName: raw.path,
      },
    };
  };
  const applyMutationResult = (
    document: DocumentResourceItem,
    result: MarketplaceDocumentMutationResult,
  ): DocumentResourceItem => {
    recordToken(
      result.path,
      result.ownerFilePath,
      result.baseEntryFingerprint,
    );
    return {
      ...document,
      id: result.path,
      description: result.path,
      metadata: {
        ...document.metadata,
        fileName: result.path,
        previousFileName: undefined,
      },
    };
  };
  const pathOf = (document: DocumentResourceItem): string =>
    (document.metadata?.fileName as string | undefined)
    ?? (document as DocumentResourceItem & { path?: string }).path
    ?? document.title;
  return {
    list: async () => {
      const raw = await session.run(
        identityGeneration,
        'document-list',
        () => listDocuments(provider, packageId, resourceType),
      );
      return { items: raw.map(stripDocument), availableScopes: [] };
    },
    loadContent: async (document) => stripDocument(await session.run(
      identityGeneration,
      `document-content:${pathOf(document)}`,
      () => loadDocument(provider, packageId, resourceType, pathOf(document)),
    )),
    create: async (document) => {
      const path = marketplaceDocumentResourcePath(pathOf(document), provider, resourceType);
      const result = await session.mutate(
        identityGeneration,
        'document-mutation',
        () => createDocument(provider, packageId, resourceType, {
          path,
          revision: session.revision,
          content: document.content,
        }),
      );
      return {
        document: applyMutationResult(document, result),
        result,
      };
    },
    update: async (document) => {
      const currentPath = pathOf(document);
      const token = tokenByPath.get(currentPath) ?? {};
      const result = await session.mutate(
        identityGeneration,
        'document-mutation',
        () => updateDocument(provider, packageId, resourceType, currentPath, {
          path: marketplaceDocumentResourcePath(currentPath, provider, resourceType),
          revision: session.revision,
          content: document.content,
          ...token,
        }),
      );
      return {
        document: applyMutationResult(document, result),
        result,
      };
    },
    move: async (document, nextPath) => {
      const previousPath = (document.metadata?.previousFileName as string | undefined) ?? pathOf(document);
      const token = tokenByPath.get(previousPath) ?? {};
      const payload: MarketplaceDocumentRenamePayload = {
        previousPath,
        nextPath: marketplaceDocumentResourcePath(nextPath, provider, resourceType),
        revision: session.revision,
        ...token,
      };
      const result = await session.mutate(
        identityGeneration,
        'document-mutation',
        () => renameDocument(provider, packageId, resourceType, payload),
      );
      tokenByPath.delete(previousPath);
      return {
        document: applyMutationResult(document, result),
        result,
      };
    },
    remove: async (document) => {
      const previousPath = pathOf(document);
      const token = tokenByPath.get(previousPath) ?? {};
      const payload: MarketplaceDocumentRemovePayload = {
        revision: session.revision,
        ...token,
      };
      const result = await session.mutate(
        identityGeneration,
        'document-mutation',
        () => removeDocument(provider, packageId, resourceType, previousPath, payload),
      );
      tokenByPath.delete(previousPath);
      return result;
    },
  };
}
