import type {
  MarketplaceDeliveryMethod,
  MarketplacePackageSummary,
  MarketplacePluginCommandResult,
  MarketplacePluginInstallRequest,
  MarketplaceProvider,
  MarketplaceUserCopyApplyRequest,
  MarketplaceUserCopyApplyResult,
  MarketplaceUserCopyPreflightRequest,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import { getMarketplaceErrorCode } from '../model/marketplacePackageActionModel';
import { MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID } from '../storage/marketplaceStorage';

export type MarketplaceInstallWorkflowStatus =
  | 'idle'
  | 'checking'
  | 'confirmation-required'
  | 'running'
  | 'succeeded'
  | 'failed';

export type MarketplaceInstallFailureKind = 'preflight' | 'delivery' | null;

export interface MarketplaceInstallWorkspaceOption {
  id: string;
  label: string;
  agenticTools: MarketplaceProvider[];
}

export interface MarketplaceInstallWorkspaceInventory {
  options: MarketplaceInstallWorkspaceOption[];
  selectedWorkspaceId: string;
}

export interface MarketplaceInstallWorkflowAdapter {
  loadWorkspaceInventory: () => Promise<MarketplaceInstallWorkspaceInventory>;
  rememberWorkspace: (workspaceId: string) => void;
  preflightUserCopy: (
    request: MarketplaceUserCopyPreflightRequest,
    signal?: AbortSignal,
  ) => Promise<MarketplaceUserCopyPreflightResult>;
  installPlugin: (
    request: MarketplacePluginInstallRequest,
  ) => Promise<MarketplacePluginCommandResult>;
  applyUserCopy: (
    request: MarketplaceUserCopyApplyRequest,
  ) => Promise<MarketplaceUserCopyApplyResult>;
  refreshPackage: (
    provider: MarketplaceProvider,
    packageId: string,
  ) => Promise<MarketplacePackageSummary>;
  invalidateUserScopeSettings: (
    provider: MarketplaceProvider,
    workspaceId: string,
  ) => Promise<void>;
  publishRefreshedItem: (item: MarketplacePackageSummary) => void;
}

export interface MarketplaceInstallWorkflowState {
  isOpen: boolean;
  status: MarketplaceInstallWorkflowStatus;
  failureKind: MarketplaceInstallFailureKind;
  item: MarketplacePackageSummary | null;
  workspaceId: string;
  workspaceOptions: MarketplaceInstallWorkspaceOption[];
  workspaceLoading: boolean;
  workspaceLoadFailed: boolean;
  deliveryMethod: MarketplaceDeliveryMethod;
  preflight: MarketplaceUserCopyPreflightResult | null;
  preflightLoading: boolean;
  preflightErrorCode: string | null;
  pluginResult: MarketplacePluginCommandResult | null;
  userCopyResult: MarketplaceUserCopyApplyResult | null;
  overwriteConfirmed: boolean;
  installErrorCode: string | null;
  selectedWorkspace: MarketplaceInstallWorkspaceOption | null;
  isWorkspaceProviderEnabled: boolean;
  requiresOverwriteConfirmation: boolean;
  isPreflightEligible: boolean;
  canRun: boolean;
  workspaceSelectionDisabled: boolean;
  deliverySelectionDisabled: boolean;
  visibleErrorCode: string | null;
  succeeded: boolean;
}

export type MarketplaceInstallWorkflowCommand =
  | { type: 'open'; item: MarketplacePackageSummary }
  | { type: 'close' }
  | { type: 'update-item'; item: MarketplacePackageSummary }
  | { type: 'reload-workspaces' }
  | { type: 'select-workspace'; workspaceId: string }
  | { type: 'select-delivery'; deliveryMethod: MarketplaceDeliveryMethod }
  | { type: 'set-overwrite-confirmed'; confirmed: boolean }
  | { type: 'refresh-preflight' }
  | { type: 'run' };

export interface MarketplaceInstallWorkflow {
  getSnapshot: () => MarketplaceInstallWorkflowState;
  subscribe: (listener: () => void) => () => void;
  send: (command: MarketplaceInstallWorkflowCommand) => Promise<void>;
}

type InternalState = Omit<
  MarketplaceInstallWorkflowState,
  | 'selectedWorkspace'
  | 'isWorkspaceProviderEnabled'
  | 'requiresOverwriteConfirmation'
  | 'isPreflightEligible'
  | 'canRun'
  | 'workspaceSelectionDisabled'
  | 'deliverySelectionDisabled'
  | 'visibleErrorCode'
  | 'succeeded'
>;

const createInitialState = (
  workspaceId: string = MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID,
): InternalState => ({
  isOpen: false,
  status: 'idle',
  failureKind: null,
  item: null,
  workspaceId,
  workspaceOptions: [],
  workspaceLoading: false,
  workspaceLoadFailed: false,
  deliveryMethod: 'plugin',
  preflight: null,
  preflightLoading: false,
  preflightErrorCode: null,
  pluginResult: null,
  userCopyResult: null,
  overwriteConfirmed: false,
  installErrorCode: null,
});

const deriveState = (
  state: InternalState,
): MarketplaceInstallWorkflowState => {
  const selectedWorkspace = state.workspaceOptions.find(
    workspace => workspace.id === state.workspaceId,
  ) ?? null;
  const isWorkspaceProviderEnabled = Boolean(
    state.item
    && selectedWorkspace?.agenticTools.includes(state.item.provider),
  );
  const requiresOverwriteConfirmation =
    state.preflight?.status === 'confirmation-required';
  const userCopyCanProceed = Boolean(
    state.preflight
    && state.preflight.blockingIssues.length === 0
    && (
      state.preflight.status === 'ready'
      || (
        state.preflight.status === 'confirmation-required'
        && state.preflight.conflicts.length > 0
        && state.preflight.conflicts.every(conflict => conflict.overwritable)
      )
    ),
  );
  const isPreflightEligible = state.deliveryMethod === 'plugin'
    ? state.item?.lifecycleStatus === 'ready'
    : userCopyCanProceed;
  const canRun = Boolean(
    state.isOpen
    && isWorkspaceProviderEnabled
    && isPreflightEligible
    && (!requiresOverwriteConfirmation || state.overwriteConfirmed)
    && state.status !== 'checking'
    && state.status !== 'running'
    && state.status !== 'succeeded',
  );
  const workspaceSelectionDisabled = (
    state.workspaceLoading
    || state.status === 'running'
    || state.status === 'succeeded'
    || (
      state.status === 'failed'
      && state.failureKind === 'delivery'
    )
  );
  const deliverySelectionDisabled =
    state.status === 'running' || state.status === 'succeeded';
  const visibleErrorCode = (
    state.installErrorCode
    ?? state.preflightErrorCode
    ?? state.preflight?.blockingIssues[0]?.errorCode
    ?? null
  );
  const succeeded = state.status === 'succeeded'
    && Boolean(state.pluginResult || state.userCopyResult);

  return {
    ...state,
    selectedWorkspace,
    isWorkspaceProviderEnabled,
    requiresOverwriteConfirmation,
    isPreflightEligible,
    canRun,
    workspaceSelectionDisabled,
    deliverySelectionDisabled,
    visibleErrorCode,
    succeeded,
  };
};

const buildRequestIdentity = (
  item: MarketplacePackageSummary,
  workspaceId: string,
): MarketplacePluginInstallRequest & MarketplaceUserCopyPreflightRequest => ({
  provider: item.provider,
  packageId: item.packageId,
  revision: item.revision,
  workspaceId,
});

const isSamePackage = (
  left: MarketplacePackageSummary | null,
  right: MarketplacePackageSummary,
) => (
  left?.provider === right.provider
  && left.packageId === right.packageId
);

export const createMarketplaceInstallWorkflow = (
  adapter: MarketplaceInstallWorkflowAdapter,
): MarketplaceInstallWorkflow => {
  const listeners = new Set<() => void>();
  let internalState = createInitialState();
  let snapshot = deriveState(internalState);
  let sessionGeneration = 0;
  let workspaceGeneration = 0;
  let preflightGeneration = 0;
  let preflightController: AbortController | null = null;

  const replaceState = (nextState: InternalState) => {
    internalState = nextState;
    snapshot = deriveState(internalState);
    listeners.forEach(listener => listener());
  };

  const updateState = (patch: Partial<InternalState>) => {
    replaceState({
      ...internalState,
      ...patch,
    });
  };

  const cancelPreflight = () => {
    preflightGeneration += 1;
    preflightController?.abort();
    preflightController = null;
  };

  const isCurrentSession = (generation: number) => (
    internalState.isOpen && generation === sessionGeneration
  );

  const refreshCurrentItem = async (
    generation: number,
  ): Promise<MarketplacePackageSummary | null> => {
    const item = internalState.item;
    if (!item) return null;

    const latestItem = await adapter.refreshPackage(
      item.provider,
      item.packageId,
    );
    if (!isCurrentSession(generation)) return null;

    updateState({ item: latestItem });
    adapter.publishRefreshedItem(latestItem);
    return latestItem;
  };

  const runPreflight = async (
    generation: number,
    itemOverride?: MarketplacePackageSummary,
  ) => {
    const item = itemOverride ?? internalState.item;
    if (
      !isCurrentSession(generation)
      || !item
      || internalState.deliveryMethod !== 'user-copy'
      || internalState.workspaceLoading
      || !deriveState(internalState).isWorkspaceProviderEnabled
    ) {
      return;
    }

    cancelPreflight();
    const attempt = ++preflightGeneration;
    const controller = new AbortController();
    preflightController = controller;
    updateState({
      status: 'checking',
      failureKind: null,
      preflight: null,
      preflightLoading: true,
      preflightErrorCode: null,
      installErrorCode: null,
      pluginResult: null,
      userCopyResult: null,
      overwriteConfirmed: false,
    });

    try {
      const preflight = await adapter.preflightUserCopy(
        buildRequestIdentity(item, internalState.workspaceId),
        controller.signal,
      );
      if (
        !isCurrentSession(generation)
        || attempt !== preflightGeneration
      ) {
        return;
      }

      preflightController = null;
      updateState({
        status: preflight.status === 'confirmation-required'
          ? 'confirmation-required'
          : 'idle',
        failureKind: null,
        preflight,
        preflightLoading: false,
        preflightErrorCode: null,
        overwriteConfirmed: false,
      });
    } catch (error) {
      if (
        !isCurrentSession(generation)
        || attempt !== preflightGeneration
        || controller.signal.aborted
      ) {
        return;
      }

      preflightController = null;
      updateState({
        status: 'failed',
        failureKind: 'preflight',
        preflight: null,
        preflightLoading: false,
        preflightErrorCode: getMarketplaceErrorCode(
          error,
          'marketplace.user_copy.inventory_unavailable',
        ),
        overwriteConfirmed: false,
      });
    }
  };

  const loadWorkspaces = async (generation: number) => {
    const attempt = ++workspaceGeneration;
    updateState({
      status: 'checking',
      failureKind: null,
      workspaceLoading: true,
      workspaceLoadFailed: false,
    });

    try {
      const inventory = await adapter.loadWorkspaceInventory();
      if (
        !isCurrentSession(generation)
        || attempt !== workspaceGeneration
      ) {
        return;
      }

      updateState({
        status: 'idle',
        workspaceOptions: inventory.options,
        workspaceId: inventory.selectedWorkspaceId,
        workspaceLoading: false,
        workspaceLoadFailed: false,
      });
      if (internalState.deliveryMethod === 'user-copy') {
        await runPreflight(generation);
      }
    } catch {
      if (
        !isCurrentSession(generation)
        || attempt !== workspaceGeneration
      ) {
        return;
      }

      updateState({
        status: 'idle',
        workspaceOptions: [],
        workspaceId: MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID,
        workspaceLoading: false,
        workspaceLoadFailed: true,
      });
    }
  };

  const open = async (item: MarketplacePackageSummary) => {
    sessionGeneration += 1;
    workspaceGeneration += 1;
    cancelPreflight();
    const generation = sessionGeneration;
    const preservedWorkspaceId = internalState.workspaceId;
    replaceState({
      ...createInitialState(preservedWorkspaceId),
      isOpen: true,
      status: 'checking',
      item,
      workspaceLoading: true,
    });
    await loadWorkspaces(generation);
  };

  const close = () => {
    sessionGeneration += 1;
    workspaceGeneration += 1;
    cancelPreflight();
    replaceState(createInitialState(internalState.workspaceId));
  };

  const updateItem = async (item: MarketplacePackageSummary) => {
    if (!internalState.isOpen) return;
    if (!isSamePackage(internalState.item, item)) {
      await open(item);
      return;
    }

    const revisionChanged = internalState.item?.revision !== item.revision;
    updateState({ item });
    if (
      revisionChanged
      && internalState.deliveryMethod === 'user-copy'
      && internalState.status !== 'running'
      && internalState.status !== 'succeeded'
    ) {
      await runPreflight(sessionGeneration, item);
    }
  };

  const selectWorkspace = async (workspaceId: string) => {
    if (
      !internalState.isOpen
      || deriveState(internalState).workspaceSelectionDisabled
      || workspaceId === internalState.workspaceId
    ) {
      return;
    }

    cancelPreflight();
    adapter.rememberWorkspace(workspaceId);
    updateState({
      status: internalState.workspaceLoading ? 'checking' : 'idle',
      failureKind: null,
      workspaceId,
      preflight: null,
      preflightLoading: false,
      preflightErrorCode: null,
      pluginResult: null,
      userCopyResult: null,
      overwriteConfirmed: false,
      installErrorCode: null,
    });
    if (internalState.deliveryMethod === 'user-copy') {
      await runPreflight(sessionGeneration);
    }
  };

  const selectDelivery = async (
    deliveryMethod: MarketplaceDeliveryMethod,
  ) => {
    if (
      !internalState.isOpen
      || deriveState(internalState).deliverySelectionDisabled
      || deliveryMethod === internalState.deliveryMethod
    ) {
      return;
    }

    cancelPreflight();
    updateState({
      status: internalState.workspaceLoading ? 'checking' : 'idle',
      failureKind: null,
      deliveryMethod,
      preflight: null,
      preflightLoading: false,
      preflightErrorCode: null,
      pluginResult: null,
      userCopyResult: null,
      overwriteConfirmed: false,
      installErrorCode: null,
    });
    if (deliveryMethod === 'user-copy') {
      await runPreflight(sessionGeneration);
    }
  };

  const refreshPreflight = async () => {
    if (
      !internalState.isOpen
      || internalState.deliveryMethod !== 'user-copy'
      || internalState.preflightLoading
      || internalState.status === 'running'
      || internalState.status === 'succeeded'
    ) {
      return;
    }

    const generation = sessionGeneration;
    cancelPreflight();
    updateState({
      status: 'checking',
      failureKind: null,
      preflight: null,
      preflightLoading: true,
      preflightErrorCode: null,
      pluginResult: null,
      userCopyResult: null,
      overwriteConfirmed: false,
      installErrorCode: null,
    });
    try {
      const latestItem = await refreshCurrentItem(generation);
      if (!latestItem) return;
      await runPreflight(generation, latestItem);
    } catch (error) {
      if (!isCurrentSession(generation)) return;
      updateState({
        status: 'failed',
        failureKind: 'preflight',
        preflightLoading: false,
        preflightErrorCode: getMarketplaceErrorCode(
          error,
          'marketplace.user_copy.inventory_unavailable',
        ),
      });
    }
  };

  const run = async () => {
    const currentSnapshot = deriveState(internalState);
    const item = internalState.item;
    if (
      !item
      || !currentSnapshot.canRun
      || internalState.status === 'running'
    ) {
      return;
    }

    const generation = sessionGeneration;
    const isRetry = (
      internalState.status === 'failed'
      && internalState.failureKind === 'delivery'
    );
    const deliveryMethod = internalState.deliveryMethod;
    const workspaceId = internalState.workspaceId;
    let deliveryItem = item;
    let currentPreflight = internalState.preflight;

    updateState({
      status: 'running',
      failureKind: null,
      installErrorCode: null,
    });
    adapter.rememberWorkspace(workspaceId);

    try {
      if (isRetry) {
        const refreshedItem = await refreshCurrentItem(generation);
        if (!refreshedItem) return;
        deliveryItem = refreshedItem;
      }

      if (isRetry && deliveryMethod === 'user-copy') {
        currentPreflight = await adapter.preflightUserCopy(
          buildRequestIdentity(deliveryItem, workspaceId),
        );
        if (!isCurrentSession(generation)) return;

        updateState({
          preflight: currentPreflight,
          preflightErrorCode: null,
          overwriteConfirmed: false,
        });
        if (
          currentPreflight.status === 'blocked'
          || currentPreflight.blockingIssues.length > 0
        ) {
          updateState({
            status: 'idle',
            failureKind: null,
          });
          return;
        }
        if (currentPreflight.status === 'confirmation-required') {
          updateState({
            status: 'confirmation-required',
            failureKind: null,
          });
          return;
        }
      }

      if (deliveryMethod === 'plugin') {
        const result = await adapter.installPlugin(
          buildRequestIdentity(deliveryItem, workspaceId),
        );
        if (!isCurrentSession(generation)) return;

        const succeeded = result.status === 'installed';
        updateState({
          status: succeeded ? 'succeeded' : 'failed',
          failureKind: succeeded ? null : 'delivery',
          pluginResult: result,
          userCopyResult: null,
          installErrorCode: null,
        });
        if (succeeded) {
          await adapter.invalidateUserScopeSettings(
            result.provider,
            result.workspaceId,
          );
        }
        return;
      }

      if (!currentPreflight) {
        updateState({
          status: 'failed',
          failureKind: 'delivery',
        });
        return;
      }

      const result = await adapter.applyUserCopy({
        ...buildRequestIdentity(deliveryItem, workspaceId),
        expectedSourceDigest: currentPreflight.sourceDigest,
        expectedMaterializationDigest: currentPreflight.materializationDigest,
        overwriteApprovals:
          currentPreflight.status === 'confirmation-required'
            ? currentPreflight.conflicts.map(conflict => ({
              targetIdentity: conflict.targetIdentity,
              expectedRevision: conflict.baselineRevision,
            }))
            : [],
      });
      if (!isCurrentSession(generation)) return;

      await adapter.invalidateUserScopeSettings(
        result.provider,
        result.workspaceId,
      );
      if (!isCurrentSession(generation)) return;

      updateState({
        status: 'succeeded',
        failureKind: null,
        pluginResult: null,
        userCopyResult: result,
        installErrorCode: null,
      });
    } catch (error) {
      if (!isCurrentSession(generation)) return;

      let errorCode = getMarketplaceErrorCode(
        error,
        'marketplace.install.command_failed',
      );
      if (
        errorCode === 'marketplace.package.revision_conflict'
        || errorCode === 'marketplace.user_copy.revision_conflict'
      ) {
        try {
          const refreshedItem = await refreshCurrentItem(generation);
          if (!refreshedItem) return;
          errorCode =
            'marketplace.install.package_revision_conflict_refreshed';
        } catch {
          if (!isCurrentSession(generation)) return;
        }
      }

      updateState({
        status: 'failed',
        failureKind: 'delivery',
        pluginResult: null,
        userCopyResult: null,
        installErrorCode: errorCode,
      });
    }
  };

  const send = async (command: MarketplaceInstallWorkflowCommand) => {
    switch (command.type) {
      case 'open':
        await open(command.item);
        return;
      case 'close':
        close();
        return;
      case 'update-item':
        await updateItem(command.item);
        return;
      case 'reload-workspaces':
        if (internalState.isOpen) {
          await loadWorkspaces(sessionGeneration);
        }
        return;
      case 'select-workspace':
        await selectWorkspace(command.workspaceId);
        return;
      case 'select-delivery':
        await selectDelivery(command.deliveryMethod);
        return;
      case 'set-overwrite-confirmed':
        if (deriveState(internalState).requiresOverwriteConfirmation) {
          updateState({ overwriteConfirmed: command.confirmed });
        }
        return;
      case 'refresh-preflight':
        await refreshPreflight();
        return;
      case 'run':
        await run();
    }
  };

  return {
    getSnapshot: () => snapshot,
    subscribe: listener => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    send,
  };
};
