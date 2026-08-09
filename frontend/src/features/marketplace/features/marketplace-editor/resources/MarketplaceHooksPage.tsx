import React from 'react';
import { Workflow } from 'lucide-react';
import type { MarketplacePackageDetail, MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import { MarketplaceEditorHookSection } from '../MarketplaceEditorHookSection';
import type { MarketplaceEditorResourceItem } from '../marketplaceEditorResourceItems';
import { getHooks, updateHooks } from '../../../api/marketplaceApi';
import type { MarketplaceHooksSource } from '../../../api/marketplaceApi';
import type { MarketplacePackageMutationResult } from '../../../model/marketplaceMutation';
import { MarketplaceResourceLoadError } from '../../../components/MarketplaceResourceLoadError';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';
import {
  MARKETPLACE_HOOK_SOURCE_EVENT,
  MARKETPLACE_HOOK_SOURCE_ID,
  MARKETPLACE_HOOK_SOURCE_PATH,
  MARKETPLACE_HOOK_SOURCE_POINTER,
  marketplaceHookDataFromValue,
  marketplaceHookNativeContent,
} from '../marketplaceHookModel';
import type { HookMatcher } from '@/shared/components/hook-workflow';

interface MarketplaceHooksPageProps {
  packageDetail: MarketplacePackageDetail;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
}

interface MarketplaceHookSourceState {
  source: MarketplaceHooksSource;
  document: Record<string, unknown>;
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const pointerTokens = (pointer: string): string[] => (
  pointer === ''
    ? []
    : pointer.split('/').slice(1).map(token => token.replace(/~1/g, '/').replace(/~0/g, '~'))
);

const valueAtPointer = (document: Record<string, unknown>, pointer: string): unknown => {
  let current: unknown = document;
  for (const token of pointerTokens(pointer)) {
    if (!isRecord(current)) return undefined;
    current = current[token];
  }
  return current;
};

const setValueAtPointer = (
  document: Record<string, unknown>,
  pointer: string,
  value: unknown,
): Record<string, unknown> => {
  if (!pointer) return isRecord(value) ? value : document;
  const next = JSON.parse(JSON.stringify(document)) as Record<string, unknown>;
  const tokens = pointerTokens(pointer);
  let current = next;
  tokens.forEach((token, index) => {
    if (index === tokens.length - 1) {
      current[token] = value;
      return;
    }
    if (!isRecord(current[token])) current[token] = {};
    current = current[token] as Record<string, unknown>;
  });
  return next;
};

const hookMapFromItem = (item: MarketplaceEditorResourceItem): Record<string, unknown[]> => {
  const parsed = JSON.parse(item.content) as unknown;
  const native = isRecord(parsed) && isRecord(parsed.hooks) ? parsed.hooks : parsed;
  if (!isRecord(native)) throw new Error('marketplace.hooks.invalid_json');
  return Object.fromEntries(
    Object.entries(native).filter(([, value]) => Array.isArray(value)) as Array<[string, unknown[]]>,
  );
};

const sourceIdOfItem = (item: MarketplaceEditorResourceItem): string | null => (
  typeof item.data?.[MARKETPLACE_HOOK_SOURCE_ID] === 'string'
    ? item.data[MARKETPLACE_HOOK_SOURCE_ID] as string
    : null
);

const eventOfItem = (item: MarketplaceEditorResourceItem): string => (
  typeof item.data?.[MARKETPLACE_HOOK_SOURCE_EVENT] === 'string'
    ? item.data[MARKETPLACE_HOOK_SOURCE_EVENT] as string
    : typeof item.data?.event === 'string' ? item.data.event as string : item.badge ?? item.id
);

const sourceStateFromResponse = (source: MarketplaceHooksSource): MarketplaceHookSourceState | null => {
  try {
    const document = JSON.parse(source.content) as unknown;
    return isRecord(document) ? { source, document } : null;
  } catch {
    return null;
  }
};

const hookItemsFromSource = (source: MarketplaceHooksSource): MarketplaceEditorResourceItem[] => {
  const native = source.nativeContent;
  if (!isRecord(native)) return [];
  return Object.entries(native)
    .filter(([, matchers]) => Array.isArray(matchers))
    .map(([event, matchers]) => {
      const value = {
        name: event,
        event,
        matchers: matchers as HookMatcher[],
      };
      return {
        id: `${source.sourceId}:${event}`,
        name: event,
        title: event,
        description: event,
        path: source.path,
        content: marketplaceHookNativeContent(value),
        data: {
          ...marketplaceHookDataFromValue(value, source),
          [MARKETPLACE_HOOK_SOURCE_EVENT]: event,
        },
        badge: event,
      };
    });
};

export const MarketplaceHooksPage: React.FC<MarketplaceHooksPageProps> = ({
  packageDetail,
  onMutation,
}) => {
  const [items, setItems] = React.useState<MarketplaceEditorResourceItem[]>([]);
  const [sources, setSources] = React.useState<MarketplaceHooksSource[]>([]);
  const sourceStatesRef = React.useRef<Map<string, MarketplaceHookSourceState>>(new Map());
  const [isLoading, setIsLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    provider: packageDetail.provider,
    packageId: packageDetail.packageId,
    resourceType: 'hooks',
  }, packageDetail.revision);

  React.useLayoutEffect(() => {
    setItems([]);
    setSources([]);
    sourceStatesRef.current = new Map();
    setIsLoading(true);
    setLoadError(false);
  }, [identityGeneration]);

  const loadItems = React.useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    await session.query(
      identityGeneration,
      'hooks-list',
      () => getHooks(packageDetail.provider, packageDetail.packageId),
      {
        onSuccess: (resource) => {
          setSources(resource.sources);
          const states = new Map<string, MarketplaceHookSourceState>();
          resource.sources.forEach((source) => {
            const state = sourceStateFromResponse(source);
            if (state) states.set(source.sourceId, state);
          });
          sourceStatesRef.current = states;
          if (resource.sources.some(source => source.diagnostics.length > 0 && !source.nativeContent)) {
            setItems([]);
            setLoadError(true);
            return;
          }
          setItems(resource.sources.flatMap(hookItemsFromSource));
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

  if (loadError) {
    return <MarketplaceResourceLoadError onRetry={() => { void loadItems(); }} />;
  }
  if (isLoading) {
    return <LoadingSpinner className="h-full" />;
  }

  const handleItemsChange = async (nextItems: MarketplaceEditorResourceItem[]) => {
    const previousItems = items;
    const states = sourceStatesRef.current;
    const sourceKeys = new Set<string>([
      ...states.keys(),
      ...previousItems.map(sourceIdOfItem).filter((value): value is string => Boolean(value)),
      ...nextItems.map(sourceIdOfItem).filter((value): value is string => Boolean(value)),
    ]);
    if (nextItems.some(item => sourceIdOfItem(item) === null)) sourceKeys.add('');

    const persistedItems = [...nextItems];
    for (const sourceKey of sourceKeys) {
      const sourceState = sourceKey ? states.get(sourceKey) : undefined;
      const previousSourceItems = previousItems.filter(item => sourceIdOfItem(item) === (sourceKey || null));
      const nextSourceItems = nextItems.filter(item => sourceIdOfItem(item) === (sourceKey || null));
      if (!sourceState && nextSourceItems.length === 0) continue;

      let document: Record<string, unknown>;
      let pointer: string;
      let native: Record<string, unknown[]>;
      if (sourceState) {
        document = JSON.parse(JSON.stringify(sourceState.document)) as Record<string, unknown>;
        pointer = sourceState.source.manifestPointer;
        const currentNative = valueAtPointer(document, pointer);
        native = isRecord(currentNative)
          ? Object.fromEntries(Object.entries(currentNative).filter(([, value]) => Array.isArray(value)) as Array<[string, unknown[]]>)
          : {};
      } else {
        document = JSON.parse(nextSourceItems[0].content) as Record<string, unknown>;
        pointer = '/hooks';
        native = {};
      }

      const nextEvents = new Set(nextSourceItems.map(eventOfItem));
      previousSourceItems.forEach((item) => {
        const event = eventOfItem(item);
        if (!nextEvents.has(event)) delete native[event];
      });
      nextSourceItems.forEach((item) => {
        const event = eventOfItem(item);
        const itemHooks = hookMapFromItem(item);
        native[event] = itemHooks[event] ?? [];
      });

      const updatedDocument = setValueAtPointer(document, pointer, native);
      if (sourceState && JSON.stringify(updatedDocument) === JSON.stringify(sourceState.document)) {
        continue;
      }
      const content = JSON.stringify(updatedDocument, null, 2);
      const result = await session.mutate(
        identityGeneration,
        `hooks-mutation:${sourceKey || 'create'}`,
        () => updateHooks(packageDetail.provider, packageDetail.packageId, {
          revision: session.revision,
          sourceId: sourceKey || null,
          content,
        }),
      );
      await onMutation(result);

      const persistedSourceId = sourceKey || `${result.path}#/hooks`;
      const persistedSource: MarketplaceHooksSource = sourceState?.source ?? {
        sourceId: persistedSourceId,
        sourceType: 'file',
        path: result.path,
        manifestPointer: '/hooks',
        content,
        nativeContent: native,
        writable: true,
        diagnostics: [],
      };
      sourceStatesRef.current.set(persistedSourceId, {
        source: { ...persistedSource, sourceId: persistedSourceId, content, nativeContent: native },
        document: updatedDocument,
      });
      if (!sourceKey) {
        for (let index = 0; index < persistedItems.length; index += 1) {
          if (sourceIdOfItem(persistedItems[index]) !== null) continue;
          persistedItems[index] = {
            ...persistedItems[index],
            data: {
              ...persistedItems[index].data,
              [MARKETPLACE_HOOK_SOURCE_ID]: persistedSource.sourceId,
              [MARKETPLACE_HOOK_SOURCE_PATH]: persistedSource.path,
              [MARKETPLACE_HOOK_SOURCE_POINTER]: persistedSource.manifestPointer,
            },
          };
        }
      }
    }
    setSources(Array.from(sourceStatesRef.current.values()).map(state => state.source));
    setItems(persistedItems);
  };

  const defaultSource = sources.find(source => source.writable) ?? null;

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1">
        <MarketplaceEditorHookSection
          provider={packageDetail.provider as MarketplaceProvider}
          icon={Workflow}
          items={items}
          defaultSource={defaultSource}
          onItemsChange={handleItemsChange}
          onRefresh={() => { void loadItems(); }}
        />
      </div>
    </div>
  );
};
