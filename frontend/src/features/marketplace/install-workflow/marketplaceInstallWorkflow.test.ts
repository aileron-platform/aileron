import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';
import type {
  MarketplacePackageSummary,
  MarketplacePluginCommandResult,
  MarketplaceUserCopyApplyResult,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import {
  createMarketplaceInstallWorkflow,
  type MarketplaceInstallWorkflowAdapter,
  type MarketplaceInstallWorkspaceInventory,
} from './marketplaceInstallWorkflow';

const packageSummary: MarketplacePackageSummary = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: ['skills', 'apps'],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'codex/plugins/review-tools',
  revision: 'revision-1',
  updatedAt: '2026-07-25T00:00:00Z',
  variants: [],
};

const workspaceInventory: MarketplaceInstallWorkspaceInventory = {
  options: [
    {
      id: 'workspace-1',
      label: 'Workspace One',
      agenticTools: ['codex'],
    },
    {
      id: 'workspace-2',
      label: 'Workspace Two',
      agenticTools: ['codex'],
    },
  ],
  selectedWorkspaceId: 'workspace-1',
};

const pluginResult: MarketplacePluginCommandResult = {
  status: 'installed',
  provider: 'codex',
  packageId: 'review-tools',
  marketplaceId: 'team-tools',
  workspaceId: 'workspace-1',
  operationId: 'a'.repeat(32),
  stage: 'completed',
  exitCode: 0,
  cliMessage: 'Installed',
  stdout: null,
  stderr: null,
  truncated: false,
};

const readyUserCopy: MarketplaceUserCopyPreflightResult = {
  status: 'ready',
  provider: 'codex',
  packageId: 'review-tools',
  workspaceId: 'workspace-1',
  sourceDigest: 'source-digest',
  profileDigest: 'profile-digest',
  materializationDigest: 'materialization-digest',
  resources: [{
    resourceType: 'skill',
    resourceId: 'review-skill',
    sourceLocator: 'skills/review-skill/SKILL.md',
    targetLocator: '.codex/skills/review-skill/SKILL.md',
    operation: 'create',
  }],
  conflicts: [],
  blockingIssues: [],
};

const confirmationRequired: MarketplaceUserCopyPreflightResult = {
  ...readyUserCopy,
  status: 'confirmation-required',
  resources: [],
  conflicts: [
    {
      resourceType: 'skill',
      resourceId: 'review-skill',
      sourceLocator: 'skills/review-skill/SKILL.md',
      targetLocator: '.codex/skills/review-skill/SKILL.md',
      targetIdentity: 'skill:review-skill',
      baselineRevision: 'target-r1',
      incomingDigest: 'incoming-1',
      overwritable: true,
    },
    {
      resourceType: 'mcp',
      resourceId: 'docs',
      sourceLocator: 'mcp/docs.json',
      targetLocator: '.codex/config.toml#mcp.docs',
      targetIdentity: 'mcp:docs',
      baselineRevision: 'target-r2',
      incomingDigest: 'incoming-2',
      overwritable: true,
    },
  ],
};

const blockedUserCopy: MarketplaceUserCopyPreflightResult = {
  ...readyUserCopy,
  status: 'blocked',
  blockingIssues: [{
    resourceType: 'skill',
    resourceId: 'review-skill',
    sourceLocator: 'skills/review-skill/SKILL.md',
    targetLocator: '.codex/skills/review-skill/SKILL.md',
    errorCode: 'marketplace.user_copy.target_not_writable',
  }],
};

const copyResult: MarketplaceUserCopyApplyResult = {
  status: 'completed',
  operationId: 'copy-1',
  provider: 'codex',
  packageId: 'review-tools',
  workspaceId: 'workspace-1',
  createdCount: 1,
  mergedCount: 2,
  unchangedCount: 3,
  overwrittenCount: 4,
};

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const createAdapter = (
  overrides: Partial<MarketplaceInstallWorkflowAdapter> = {},
): MarketplaceInstallWorkflowAdapter => ({
  loadWorkspaceInventory: vi.fn(async () => workspaceInventory),
  rememberWorkspace: vi.fn(),
  preflightUserCopy: vi.fn(async () => readyUserCopy),
  installPlugin: vi.fn(async () => pluginResult),
  applyUserCopy: vi.fn(async () => copyResult),
  refreshPackage: vi.fn(async () => packageSummary),
  invalidateUserScopeSettings: vi.fn(async () => undefined),
  publishRefreshedItem: vi.fn(),
  ...overrides,
});

describe('createMarketplaceInstallWorkflow', () => {
  it('publishes checking then idle while opening a transient session', async () => {
    const inventory = createDeferred<MarketplaceInstallWorkspaceInventory>();
    const adapter = createAdapter({
      loadWorkspaceInventory: vi.fn(() => inventory.promise),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    const states: string[] = [];
    workflow.subscribe(() => states.push(workflow.getSnapshot().status));

    const opening = workflow.send({ type: 'open', item: packageSummary });

    expect(workflow.getSnapshot()).toMatchObject({
      isOpen: true,
      status: 'checking',
      workspaceLoading: true,
      deliveryMethod: 'plugin',
      pluginResult: null,
      userCopyResult: null,
    });

    inventory.resolve(workspaceInventory);
    await opening;

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'idle',
      workspaceLoading: false,
      workspaceId: 'workspace-1',
      isWorkspaceProviderEnabled: true,
      canRun: true,
    });
    expect(states).toContain('checking');
    expect(states.at(-1)).toBe('idle');
  });

  it('runs the plugin branch through running and succeeded', async () => {
    const install = createDeferred<MarketplacePluginCommandResult>();
    const adapter = createAdapter({
      installPlugin: vi.fn(() => install.promise),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    const running = workflow.send({ type: 'run' });

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'running',
      canRun: false,
      pluginResult: null,
    });
    expect(adapter.rememberWorkspace).toHaveBeenCalledWith('workspace-1');
    expect(adapter.installPlugin).toHaveBeenCalledWith({
      provider: 'codex',
      packageId: 'review-tools',
      revision: 'revision-1',
      workspaceId: 'workspace-1',
    });

    install.resolve(pluginResult);
    await running;

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'succeeded',
      succeeded: true,
      pluginResult,
      userCopyResult: null,
    });
    expect(adapter.invalidateUserScopeSettings).toHaveBeenCalledWith(
      'codex',
      'workspace-1',
    );
  });

  it('refreshes the package before retrying a typed plugin failure', async () => {
    const failedResult: MarketplacePluginCommandResult = {
      ...pluginResult,
      status: 'failed',
      stage: 'plugin-install',
      exitCode: 1,
      cliMessage: 'Install failed',
    };
    const latestItem = {
      ...packageSummary,
      revision: 'revision-2',
    };
    const adapter = createAdapter({
      installPlugin: vi.fn()
        .mockResolvedValueOnce(failedResult)
        .mockResolvedValueOnce(pluginResult),
      refreshPackage: vi.fn(async () => latestItem),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    await workflow.send({ type: 'run' });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'failed',
      failureKind: 'delivery',
      pluginResult: failedResult,
      canRun: true,
      workspaceSelectionDisabled: true,
      deliverySelectionDisabled: false,
    });

    await workflow.send({ type: 'run' });

    expect(adapter.refreshPackage).toHaveBeenCalledWith(
      'codex',
      'review-tools',
    );
    expect(adapter.publishRefreshedItem).toHaveBeenCalledWith(latestItem);
    expect(adapter.installPlugin).toHaveBeenNthCalledWith(2, {
      provider: 'codex',
      packageId: 'review-tools',
      revision: 'revision-2',
      workspaceId: 'workspace-1',
    });
    expect(workflow.getSnapshot().status).toBe('succeeded');
  });

  it('refreshes canonical package state after a revision conflict', async () => {
    const latestItem = {
      ...packageSummary,
      revision: 'revision-2',
    };
    const adapter = createAdapter({
      installPlugin: vi.fn(async () => {
        throw new ApiError(
          'revision conflict',
          409,
          'marketplace.package.revision_conflict',
        );
      }),
      refreshPackage: vi.fn(async () => latestItem),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    await workflow.send({ type: 'run' });

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'failed',
      failureKind: 'delivery',
      item: latestItem,
      installErrorCode:
        'marketplace.install.package_revision_conflict_refreshed',
    });
    expect(adapter.publishRefreshedItem).toHaveBeenCalledWith(latestItem);
  });

  it('runs a ready user-copy branch without overwrite approvals', async () => {
    const adapter = createAdapter();
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    await workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'idle',
      deliveryMethod: 'user-copy',
      preflight: readyUserCopy,
      canRun: true,
    });

    await workflow.send({ type: 'run' });

    expect(adapter.applyUserCopy).toHaveBeenCalledWith({
      provider: 'codex',
      packageId: 'review-tools',
      revision: 'revision-1',
      workspaceId: 'workspace-1',
      expectedSourceDigest: 'source-digest',
      expectedMaterializationDigest: 'materialization-digest',
      overwriteApprovals: [],
    });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'succeeded',
      pluginResult: null,
      userCopyResult: copyResult,
    });
  });

  it('requires explicit confirmation and derives exact overwrite approvals', async () => {
    const preflight = createDeferred<MarketplaceUserCopyPreflightResult>();
    const apply = createDeferred<MarketplaceUserCopyApplyResult>();
    const adapter = createAdapter({
      preflightUserCopy: vi.fn(() => preflight.promise),
      applyUserCopy: vi.fn(() => apply.promise),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    const checking = workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'checking',
      preflightLoading: true,
      canRun: false,
    });

    preflight.resolve(confirmationRequired);
    await checking;
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'confirmation-required',
      requiresOverwriteConfirmation: true,
      overwriteConfirmed: false,
      canRun: false,
    });

    await workflow.send({
      type: 'set-overwrite-confirmed',
      confirmed: true,
    });
    expect(workflow.getSnapshot().canRun).toBe(true);

    const running = workflow.send({ type: 'run' });
    expect(workflow.getSnapshot().status).toBe('running');
    expect(adapter.applyUserCopy).toHaveBeenCalledWith(
      expect.objectContaining({
        overwriteApprovals: [
          {
            targetIdentity: 'skill:review-skill',
            expectedRevision: 'target-r1',
          },
          {
            targetIdentity: 'mcp:docs',
            expectedRevision: 'target-r2',
          },
        ],
      }),
    );

    apply.resolve(copyResult);
    await running;
    expect(workflow.getSnapshot().status).toBe('succeeded');
  });

  it('stops a failed user-copy retry when the fresh plan needs confirmation', async () => {
    const latestItem = {
      ...packageSummary,
      revision: 'revision-2',
    };
    const adapter = createAdapter({
      preflightUserCopy: vi.fn()
        .mockResolvedValueOnce(readyUserCopy)
        .mockResolvedValueOnce({
          ...confirmationRequired,
          materializationDigest: 'materialization-digest-2',
        }),
      applyUserCopy: vi.fn()
        .mockRejectedValueOnce(new Error('copy failed')),
      refreshPackage: vi.fn(async () => latestItem),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });
    await workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });
    await workflow.send({ type: 'run' });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'failed',
      failureKind: 'delivery',
    });

    await workflow.send({ type: 'run' });

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'confirmation-required',
      overwriteConfirmed: false,
      canRun: false,
      item: latestItem,
    });
    expect(adapter.applyUserCopy).toHaveBeenCalledTimes(1);
  });

  it('fails closed when preflight is blocked', async () => {
    const adapter = createAdapter({
      preflightUserCopy: vi.fn(async () => blockedUserCopy),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    await workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });

    expect(workflow.getSnapshot()).toMatchObject({
      status: 'idle',
      preflight: blockedUserCopy,
      visibleErrorCode: 'marketplace.user_copy.target_not_writable',
      canRun: false,
    });
    await workflow.send({ type: 'run' });
    expect(adapter.applyUserCopy).not.toHaveBeenCalled();
  });

  it('exposes preflight failure and refreshes it through the same interface', async () => {
    const latestItem = {
      ...packageSummary,
      revision: 'revision-2',
    };
    const adapter = createAdapter({
      preflightUserCopy: vi.fn()
        .mockRejectedValueOnce(new Error('inventory unavailable'))
        .mockResolvedValueOnce(readyUserCopy),
      refreshPackage: vi.fn(async () => latestItem),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);
    await workflow.send({ type: 'open', item: packageSummary });

    await workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'failed',
      failureKind: 'preflight',
      preflightErrorCode: 'marketplace.user_copy.inventory_unavailable',
      workspaceSelectionDisabled: false,
      deliverySelectionDisabled: false,
    });

    await workflow.send({ type: 'refresh-preflight' });

    expect(adapter.refreshPackage).toHaveBeenCalledWith(
      'codex',
      'review-tools',
    );
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'idle',
      failureKind: null,
      item: latestItem,
      preflight: readyUserCopy,
      preflightErrorCode: null,
      canRun: true,
    });
  });

  it('retries workspace loading and preserves only the selected workspace', async () => {
    const adapter = createAdapter({
      loadWorkspaceInventory: vi.fn()
        .mockRejectedValueOnce(new Error('unavailable'))
        .mockResolvedValueOnce(workspaceInventory)
        .mockResolvedValueOnce({
          ...workspaceInventory,
          selectedWorkspaceId: 'workspace-2',
        }),
    });
    const workflow = createMarketplaceInstallWorkflow(adapter);

    await workflow.send({ type: 'open', item: packageSummary });
    expect(workflow.getSnapshot()).toMatchObject({
      status: 'idle',
      workspaceLoadFailed: true,
      workspaceOptions: [],
      canRun: false,
    });

    await workflow.send({ type: 'reload-workspaces' });
    await workflow.send({
      type: 'select-workspace',
      workspaceId: 'workspace-2',
    });
    await workflow.send({
      type: 'select-delivery',
      deliveryMethod: 'user-copy',
    });
    expect(adapter.rememberWorkspace).toHaveBeenCalledWith('workspace-2');

    await workflow.send({ type: 'close' });
    expect(workflow.getSnapshot()).toMatchObject({
      isOpen: false,
      status: 'idle',
      workspaceId: 'workspace-2',
      workspaceOptions: [],
      deliveryMethod: 'plugin',
      preflight: null,
      pluginResult: null,
      userCopyResult: null,
      overwriteConfirmed: false,
    });

    await workflow.send({ type: 'open', item: packageSummary });
    expect(workflow.getSnapshot()).toMatchObject({
      isOpen: true,
      status: 'idle',
      workspaceId: 'workspace-2',
      deliveryMethod: 'plugin',
      preflight: null,
    });
  });
});
