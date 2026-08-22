import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  DocumentResourceWorkbench,
  createDocumentMetadataAdapter,
  type DocumentResourceItem,
} from '@/shared/components/document-resource';
import type {
  DocumentMetadataValue,
  DocumentWorkbenchRenderSurface,
} from '@/shared/components/document-workflow';
import type {
  MarketplaceDocumentResourceType,
  MarketplacePackageMutationResult,
} from '../../../model/marketplaceMutation';
import type { MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';
import {
  createMarketplaceDocumentSource,
  marketplaceDocumentResourcePath,
  type MarketplaceDocumentSource,
} from './marketplaceDocumentSources';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

export interface MarketplaceDocumentResourcePageProps {
  targetClient: MarketplaceTargetClient;
  packageId: string;
  resourceType: MarketplaceDocumentResourceType;
  initialRevision: string;
  sourceAdapter?: MarketplaceDocumentSource;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
  renderSurface?: (surface: DocumentWorkbenchRenderSurface) => React.ReactNode;
}

const configByResourceType = {
  commands: {
    metaKey: 'slash-commands',
    templateResourceType: 'slashCommand',
    dialogTitleKey: 'marketplace.resources.commands',
  },
  subagents: {
    metaKey: 'subagents',
    templateResourceType: 'subagent',
    dialogTitleKey: 'marketplace.resources.subagents',
  },
  'output-styles': {
    metaKey: 'output-styles',
    templateResourceType: 'outputStyle',
    dialogTitleKey: 'marketplace.resources.outputStyles',
  },
} as const satisfies Record<MarketplaceDocumentResourceType, {
  metaKey: 'slash-commands' | 'subagents' | 'output-styles';
  templateResourceType?: 'slashCommand' | 'subagent' | 'outputStyle';
  dialogTitleKey: string;
}>;

const buildRenamedDocumentPath = (currentPath: string, nextFileName: string): string => {
  const parts = currentPath.split('/').filter(Boolean);
  parts[parts.length - 1] = nextFileName;
  return parts.join('/');
};

const pathOf = (
  document: DocumentResourceItem,
): string => (
  (document.metadata?.fileName as string | undefined)
  ?? (document.metadata?.relativePath as string | undefined)
  ?? document.id
);

export const marketplaceDocumentResourceQueryKey = (
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
) => ['marketplace', targetClient, packageId, resourceType] as const;

export const MarketplaceDocumentResourcePage: React.FC<MarketplaceDocumentResourcePageProps> = ({
  targetClient,
  packageId,
  resourceType,
  initialRevision,
  sourceAdapter,
  onMutation,
  renderSurface,
}) => {
  const queryClient = useQueryClient();
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType,
  }, initialRevision);
  const defaultSource: MarketplaceDocumentSource = React.useMemo(
    () => createMarketplaceDocumentSource(
      targetClient,
      packageId,
      resourceType,
      session,
      identityGeneration,
    ),
    [identityGeneration, packageId, targetClient, resourceType, session],
  );
  const source = sourceAdapter ?? defaultSource;
  const config = configByResourceType[resourceType];
  const metadataAdapter = React.useMemo(() => (
    config.templateResourceType
      ? (() => {
          const adapter = createDocumentMetadataAdapter(config.templateResourceType, { scope: false });
          const canonicalizeDocumentPath = (document: DocumentResourceItem): DocumentResourceItem => {
            const nextPath = marketplaceDocumentResourcePath(
              pathOf(document),
              targetClient,
              resourceType,
            );
            return {
              ...document,
              id: nextPath,
              metadata: {
                ...document.metadata,
                fileName: nextPath,
              },
            };
          };
          return {
            ...adapter,
            buildCreate(input: DocumentMetadataValue, templateContent: string): DocumentResourceItem {
              return canonicalizeDocumentPath(adapter.buildCreate(input, templateContent));
            },
            applyRename(document: DocumentResourceItem, fileName: string): DocumentResourceItem {
              return canonicalizeDocumentPath(adapter.applyRename(document, fileName));
            },
          };
        })()
      : undefined
  ), [config.templateResourceType, targetClient, resourceType]);

  const queryKey = React.useMemo(
    () => marketplaceDocumentResourceQueryKey(targetClient, packageId, resourceType),
    [packageId, targetClient, resourceType],
  );
  const refresh = React.useCallback(async () => {
    await queryClient.invalidateQueries({
      queryKey: ['document-resource', ...queryKey],
      exact: true,
    });
  }, [queryClient, queryKey]);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
      <DocumentResourceWorkbench
        queryKey={queryKey}
        i18nNamespace="marketplace.editor"
        source={{
          list: () => source.list(),
          loadContent: source.loadContent,
          create: async (document) => {
            const mutation = await source.create(document);
            await onMutation(mutation.result);
            await refresh();
            return mutation.document;
          },
          update: async (document) => {
            const mutation = await source.update(document);
            await onMutation(mutation.result);
            await refresh();
            return mutation.document;
          },
          move: async (document, nextFileName) => {
            const currentPath = (document.metadata?.previousFileName as string | undefined) ?? pathOf(document);
            const nextPath = nextFileName.includes('/')
              ? nextFileName
              : buildRenamedDocumentPath(currentPath, nextFileName);
            const mutation = await source.move(document, nextPath);
            await onMutation(mutation.result);
            await refresh();
            return mutation.document;
          },
          remove: async (document) => {
            const result = await source.remove(document);
            await onMutation(result);
            await refresh();
          },
        }}
        config={{
          metaKey: config.metaKey,
          contentFormat: 'markdown',
          createButtonLabel: 'marketplace.editor.documents.actions.create',
          emptyStateTitle: 'marketplace.editor.documents.empty.title',
          emptyStateDescription: 'marketplace.editor.documents.empty.description',
          dialogTitle: config.dialogTitleKey,
          scopeMode: 'hidden',
        }}
        metadataAdapter={metadataAdapter}
        templateResourceType={config.templateResourceType}
        showSidebar
        showSidebarSearch
        useShellSidebarHeader
        renderSurface={renderSurface}
      />
    </div>
  );
};
