import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { MarketplacePackageSummary } from '../model/marketplaceTypes';
import {
  createMarketplaceInstallWorkflow,
  type MarketplaceInstallWorkflow,
} from './marketplaceInstallWorkflow';
import { createMarketplaceInstallWorkflowAdapter } from './marketplaceInstallWorkflowAdapter';

interface UseMarketplaceInstallWorkflowOptions {
  open: boolean;
  item: MarketplacePackageSummary;
  onItemRefresh?: (item: MarketplacePackageSummary) => void;
}

export const useMarketplaceInstallWorkflow = ({
  open,
  item,
  onItemRefresh,
}: UseMarketplaceInstallWorkflowOptions) => {
  const queryClient = useQueryClient();
  const onItemRefreshRef = React.useRef(onItemRefresh);
  const itemRef = React.useRef(item);
  onItemRefreshRef.current = onItemRefresh;
  itemRef.current = item;

  const workflow = React.useMemo<MarketplaceInstallWorkflow>(
    () => createMarketplaceInstallWorkflow(
      createMarketplaceInstallWorkflowAdapter(
        queryClient,
        refreshedItem => onItemRefreshRef.current?.(refreshedItem),
      ),
    ),
    [queryClient],
  );
  const state = React.useSyncExternalStore(
    workflow.subscribe,
    workflow.getSnapshot,
    workflow.getSnapshot,
  );

  React.useEffect(() => {
    if (open) {
      void workflow.send({ type: 'open', item: itemRef.current });
      return;
    }
    void workflow.send({ type: 'close' });
  }, [item.packageId, item.targetClient, open, workflow]);

  React.useEffect(() => {
    if (open) {
      void workflow.send({ type: 'update-item', item });
    }
  }, [item, open, workflow]);

  React.useEffect(
    () => () => {
      void workflow.send({ type: 'close' });
    },
    [workflow],
  );

  return {
    state,
    send: workflow.send,
  };
};
