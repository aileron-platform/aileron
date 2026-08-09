import React from 'react';
import { Network } from 'lucide-react';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { MarketplaceEditorMCPSection } from '../MarketplaceEditorMCPSection';
import type { MarketplaceEditorResourceItem } from '../marketplaceEditorResourceItems';
import { marketplaceMCPServerValueFromItem } from '../marketplaceMCPServerDialogSchema';
import {
  createMCPServer,
  deleteMCPServer,
  getMCPServer,
  listMCPServers,
  saveMCPServer,
} from '../../../api/marketplaceApi';
import type { MarketplacePackageMutationResult } from '../../../model/marketplaceMutation';
import { MarketplaceResourceLoadError } from '../../../components/MarketplaceResourceLoadError';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

interface MarketplaceMCPPageProps {
  packageDetail: MarketplacePackageDetail;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
}

const itemName = (item: MarketplaceEditorResourceItem): string => marketplaceMCPServerValueFromItem(item, (key) => key).name;

const mcpItemIdentity = (name: string, ownerFilePath: string): string => (
  JSON.stringify([name, ownerFilePath])
);

const itemSourceToken = (item: MarketplaceEditorResourceItem): {
  ownerFilePath: string;
  baseEntryFingerprint: string;
} => {
  const ownerFilePath = item.ownerFilePath
    ?? (typeof item.data?.ownerFilePath === 'string' ? item.data.ownerFilePath : undefined);
  const baseEntryFingerprint = item.baseEntryFingerprint
    ?? (typeof item.data?.baseEntryFingerprint === 'string' ? item.data.baseEntryFingerprint : undefined);
  if (!ownerFilePath || !baseEntryFingerprint) {
    throw new Error('Marketplace MCP item is missing canonical source tokens');
  }
  return { ownerFilePath, baseEntryFingerprint };
};

const mutationSourceToken = (result: MarketplacePackageMutationResult): {
  ownerFilePath: string;
  baseEntryFingerprint: string;
} => {
  if (!result.ownerFilePath || !result.baseEntryFingerprint) {
    throw new Error('Marketplace MCP mutation did not return canonical source tokens');
  }
  return {
    ownerFilePath: result.ownerFilePath,
    baseEntryFingerprint: result.baseEntryFingerprint,
  };
};

export const MarketplaceMCPPage: React.FC<MarketplaceMCPPageProps> = ({
  packageDetail,
  onMutation,
}) => {
  const [items, setItems] = React.useState<MarketplaceEditorResourceItem[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    provider: packageDetail.provider,
    packageId: packageDetail.packageId,
    resourceType: 'mcp',
  }, packageDetail.revision);

  React.useLayoutEffect(() => {
    setItems([]);
    setIsLoading(true);
    setLoadError(false);
  }, [identityGeneration]);

  const loadItems = React.useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    await session.query(
      identityGeneration,
      'mcp-list',
      () => listMCPServers(packageDetail.provider, packageDetail.packageId),
      {
        onSuccess: (summaries) => {
          setItems(summaries.map(summary => ({
            id: mcpItemIdentity(summary.name, summary.ownerFilePath),
            name: summary.name,
            title: summary.name,
            path: summary.path,
            content: '',
            ownerFilePath: summary.ownerFilePath,
            baseEntryFingerprint: summary.baseEntryFingerprint,
          })));
        },
        onError: () => {
          setLoadError(true);
        },
        onSettled: () => {
          setIsLoading(false);
        },
      },
    );
  }, [
    identityGeneration,
    packageDetail.packageId,
    packageDetail.provider,
    session,
  ]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const loadItem = React.useCallback(async (item: MarketplaceEditorResourceItem) => {
    if (item.content) return item;
    const sourceToken = itemSourceToken(item);
    const detail = await session.run(
      identityGeneration,
      `mcp-content:${item.id}`,
      () => getMCPServer(
        packageDetail.provider,
        packageDetail.packageId,
        item.name ?? item.id,
        sourceToken.ownerFilePath,
      ),
    );
    return {
      ...item,
      content: JSON.stringify(detail.server, null, 2),
      ownerFilePath: detail.ownerFilePath,
      baseEntryFingerprint: detail.baseEntryFingerprint,
    };
  }, [
    identityGeneration,
    packageDetail.packageId,
    packageDetail.provider,
    session,
  ]);

  const handleItemsChange = async (nextItems: MarketplaceEditorResourceItem[]) => {
    const originalItems = items;
    const originalItemsById = new Map(originalItems.map(item => [item.id, item]));
    const nextIds = new Set(nextItems.map(item => item.id));
    const removed = originalItems.filter(original => !nextIds.has(original.id));
    const changed = nextItems.filter(item => {
      const original = originalItemsById.get(item.id);
      return !original || original.content !== item.content;
    });

    if (removed.length === 1 && changed.length === 0) {
      const name = itemName(removed[0]);
      const sourceToken = itemSourceToken(removed[0]);
      await session.mutate(
        identityGeneration,
        'mcp-mutation',
        () => deleteMCPServer(
          packageDetail.provider,
          packageDetail.packageId,
          name,
          {
            revision: session.revision,
            ...sourceToken,
          },
        ),
        async (result) => {
          await onMutation(result);
          setItems(nextItems);
        },
      );
      return;
    }

    if (removed.length === 0 && changed.length === 1) {
      const item = changed[0];
      const value = marketplaceMCPServerValueFromItem(item, (key) => key);
      const original = originalItemsById.get(item.id);
      const server = JSON.parse(item.content) as Record<string, unknown>;
      await session.mutate(
        identityGeneration,
        'mcp-mutation',
        () => (
          original
            ? saveMCPServer(packageDetail.provider, packageDetail.packageId, value.name, {
                revision: session.revision,
                server,
                ...itemSourceToken(original),
              })
            : createMCPServer(packageDetail.provider, packageDetail.packageId, {
                revision: session.revision,
                name: value.name,
                server,
              })
        ),
        async (result) => {
          const sourceToken = mutationSourceToken(result);
          await onMutation(result);
          setItems(nextItems.map((nextItem) => (
            nextItem.id === item.id
              ? {
                  ...nextItem,
                  id: mcpItemIdentity(value.name, sourceToken.ownerFilePath),
                  name: value.name,
                  path: result.path,
                  ...sourceToken,
                }
              : nextItem
          )));
        },
      );
    }
  };

  if (loadError) {
    return <MarketplaceResourceLoadError onRetry={() => { void loadItems(); }} />;
  }
  if (isLoading) {
    return <LoadingSpinner className="h-full" />;
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1">
        <MarketplaceEditorMCPSection
          icon={Network}
          items={items}
          onItemsChange={handleItemsChange}
          onRefresh={() => { void loadItems(); }}
          onLoadItem={loadItem}
        />
      </div>
    </div>
  );
};
