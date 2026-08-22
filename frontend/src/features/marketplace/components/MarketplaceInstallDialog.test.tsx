import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@/__tests__/utils/render';
import { fetchWorkspaceList } from '@/features/workspace/public';
import { ApiError } from '@/shared/api/apiClient';
import {
  createMarketplaceUserCopy,
  getPackage,
  installMarketplacePlugin,
  preflightMarketplaceUserCopy,
  refreshMarketplacePackage,
} from '../api/marketplaceApi';
import type {
  MarketplacePackageSummary,
  MarketplacePluginCommandResult,
  MarketplaceUserCopyApplyResult,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import { MarketplaceInstallDialog } from './MarketplaceInstallDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values ? `${key}:${Object.values(values).join(':')}` : key
    ),
  }),
}));

vi.mock('../api/marketplaceApi', () => ({
  preflightMarketplaceUserCopy: vi.fn(),
  installMarketplacePlugin: vi.fn(),
  createMarketplaceUserCopy: vi.fn(),
  getPackage: vi.fn(),
  refreshMarketplacePackage: vi.fn(),
}));

const workspaceMocks = vi.hoisted(() => ({
  invalidateMarketplaceUserScopeSettingsQueries: vi.fn(),
}));

vi.mock('@/features/workspace/public', async importOriginal => ({
  ...(await importOriginal<typeof import('@/features/workspace/public')>()),
  fetchWorkspaceList: vi.fn(async () => ({
    items: [{
      id: 'workspace-1',
      name: 'Workspace One',
      accessRole: 'manager',
      agenticTools: ['codex'],
    }],
  })),
  ...workspaceMocks,
}));

const packageSummary: MarketplacePackageSummary = {
  targetClient: 'codex',
  packageFormat: 'codex-native',
  catalogPluginId: 'codex/review-tools',
  userCopyTargetClient: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  tags: [],
  indexedResourceNames: ['hooks', 'mcp', 'agents', 'commands', 'skills'],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/review-tools',
  revision: 'revision-1',
  version: '1.2.3',
  updatedAt: '2026-07-25T00:00:00Z',
  variants: [],
};

const pluginResult: MarketplacePluginCommandResult = {
  status: 'installed',
  targetClient: 'codex',
  packageFormat: 'codex-native',
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

const confirmationRequired: MarketplaceUserCopyPreflightResult = {
  status: 'confirmation-required',
  packageFormat: 'codex-native',
  targetClient: 'codex',
  catalogPluginId: 'codex/review-tools',
  releaseRevision: 'revision-1',
  workspaceId: 'workspace-1',
  sourceDigest: 'source-digest',
  profileDigest: 'profile-digest',
  materializationDigest: 'materialization-digest',
  projectionDigest: 'projection-digest',
  resources: [],
  skippedResources: [],
  conflicts: [{
    resourceType: 'skill',
    resourceId: 'review-skill',
    sourceLocator: 'skills/review-skill/SKILL.md',
    targetLocator: '.codex/skills/review-skill/SKILL.md',
    targetIdentity: 'skill:review-skill',
    baselineRevision: 'target-r1',
    incomingDigest: 'incoming-1',
    overwritable: true,
  }],
  blockingIssues: [],
};

const blockedByEffectiveIdentityConflict: MarketplaceUserCopyPreflightResult = {
  ...confirmationRequired,
  status: 'blocked',
  conflicts: [],
  blockingIssues: [{
    resourceType: 'skill',
    resourceId: 'review-skill',
    sourceLocator: 'skills/review-skill/SKILL.md',
    targetLocator: '.codex/skills/review-skill/SKILL.md',
    errorCode: 'marketplace.user_copy.effective_identity_conflict',
  }],
};

const copyResult: MarketplaceUserCopyApplyResult = {
  status: 'completed',
  operationId: 'copy-1',
  packageFormat: 'codex-native',
  targetClient: 'codex',
  catalogPluginId: 'codex/review-tools',
  releaseRevision: 'revision-1',
  workspaceId: 'workspace-1',
  createdCount: 1,
  mergedCount: 2,
  unchangedCount: 3,
  overwrittenCount: 4,
  skippedCount: 0,
};

const waitForWorkspaceReady = async () => {
  await waitFor(() => {
    expect(screen.getByText('marketplace.install.plugin.publishReady'))
      .toBeInTheDocument();
  }, { timeout: 10_000 });
};

describe('MarketplaceInstallDialog', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(fetchWorkspaceList).mockResolvedValue({
      items: [{
        id: 'workspace-1',
        name: 'Workspace One',
        accessRole: 'manager',
        agenticTools: ['codex'],
      }],
    });
    vi.mocked(preflightMarketplaceUserCopy)
      .mockResolvedValue(confirmationRequired);
    vi.mocked(installMarketplacePlugin).mockResolvedValue(pluginResult);
    vi.mocked(createMarketplaceUserCopy).mockResolvedValue(copyResult);
    vi.mocked(refreshMarketplacePackage)
      .mockResolvedValue({ refreshed: true });
    vi.mocked(getPackage).mockResolvedValue(packageSummary);
  });

  it('uses the same English feature tags as the package card', async () => {
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    for (const key of [
      'marketplace.features.hooks',
      'marketplace.features.mcp',
      'marketplace.features.subagents',
      'marketplace.features.slashCommands',
      'marketplace.features.skills',
    ]) {
      expect(screen.getByText(key)).toBeInTheDocument();
    }
  });

  it('keeps the title and actions outside the scrollable body', async () => {
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    const body = screen.getByTestId('marketplace-install-scroll-body');
    const dialog = screen.getByRole('dialog');
    const title = screen.getByText('marketplace.install.title');
    const install = screen.getByRole('button', {
      name: 'marketplace.install.actions.install',
    });

    expect(dialog).toHaveClass('flex', 'overflow-hidden');
    expect(body).toHaveClass('min-h-0', 'flex-1', 'overflow-y-auto');
    expect(body).not.toContainElement(title);
    expect(body).not.toContainElement(install);
  });

  it('binds the production plugin adapter and renders its result', async () => {
    const user = userEvent.setup();
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('button', {
      name: 'marketplace.install.actions.install',
    }));

    await screen.findByText('marketplace.install.result.success.plugin');
    expect(installMarketplacePlugin).toHaveBeenCalledWith({
      targetClient: 'codex',
      packageFormat: 'codex-native',
      packageId: 'review-tools',
      version: '1.2.3',
      workspaceId: 'workspace-1',
    });
    expect(screen.getByText('marketplace.install.stages.completed'))
      .toBeInTheDocument();
    expect(workspaceMocks.invalidateMarketplaceUserScopeSettingsQueries)
      .toHaveBeenCalledWith(
        expect.anything(),
        'codex',
        'workspace-1',
      );
  });

  it('selects an older immutable release for rollback', async () => {
    const user = userEvent.setup();
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    const versionInput = screen.getByLabelText(
      'marketplace.install.fields.releaseVersion',
    );
    await user.clear(versionInput);
    await user.type(versionInput, '1.0.0');
    await user.click(screen.getByRole('button', {
      name: 'marketplace.install.actions.install',
    }));

    await screen.findByText('marketplace.install.result.success.plugin');
    expect(installMarketplacePlugin).toHaveBeenCalledWith(
      expect.objectContaining({ version: '1.0.0' }),
    );
  });

  it('renders structured install failure diagnostics', async () => {
    const user = userEvent.setup();
    vi.mocked(installMarketplacePlugin).mockRejectedValue(new ApiError(
      'access denied',
      403,
      'marketplace.workspace.access_denied',
      undefined,
      undefined,
      {
        detail: {
          errorCode: 'marketplace.workspace.access_denied',
          message: 'access denied',
          stage: 'authorize',
          source: 'plugins/codex/review-tools/v1.2.3',
          destination: 'workspace-1',
          category: 'authorization',
        },
      },
    ));
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('button', {
      name: 'marketplace.install.actions.install',
    }));

    expect(await screen.findByText('authorize')).toBeInTheDocument();
    expect(screen.getByText('authorization')).toBeInTheDocument();
    expect(screen.getByText('plugins/codex/review-tools/v1.2.3'))
      .toBeInTheDocument();
    expect(screen.getByText('workspace-1')).toBeInTheDocument();
  });

  it('binds workspace reload after an inventory failure', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchWorkspaceList)
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce({
        items: [{
          id: 'workspace-1',
          name: 'Workspace One',
          accessRole: 'manager',
          agenticTools: ['codex'],
        }],
      });
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await screen.findByText('marketplace.install.workspaceSelect.loadFailed');
    await user.click(screen.getByRole('button', {
      name: 'marketplace.install.actions.refresh',
    }));

    await waitForWorkspaceReady();
    expect(fetchWorkspaceList).toHaveBeenCalledTimes(2);
  });

  it('binds overwrite confirmation to the user-copy workflow branch', async () => {
    const user = userEvent.setup();
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('radio', {
      name: /marketplace\.install\.deliveryMethods\.user-copy\.title/,
    }));
    const applyButton = await screen.findByRole('button', {
      name: 'marketplace.install.actions.overwriteAndCopy',
    });
    expect(applyButton).toBeDisabled();
    await user.click(screen.getByLabelText(
      'marketplace.install.conflicts.confirmOverwrite',
    ));
    await user.click(applyButton);

    await screen.findByText('marketplace.install.result.success.user-copy');
    expect(createMarketplaceUserCopy).toHaveBeenCalledWith({
      packageFormat: 'codex-native',
      targetClient: 'codex',
      catalogPluginId: 'codex/review-tools',
      releaseRevision: 'revision-1',
      workspaceId: 'workspace-1',
      expectedProfileDigest: 'profile-digest',
      expectedSourceDigest: 'source-digest',
      expectedProjectionDigest: 'projection-digest',
      expectedMaterializationDigest: 'materialization-digest',
      acceptPartialCopy: false,
      overwriteApprovals: [{
        targetIdentity: 'skill:review-skill',
        expectedRevision: 'target-r1',
      }],
    });
  });

  it('renders a blocking resource identity conflict only once', async () => {
    const user = userEvent.setup();
    vi.mocked(preflightMarketplaceUserCopy)
      .mockResolvedValue(blockedByEffectiveIdentityConflict);
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('radio', {
      name: /marketplace\.install\.deliveryMethods\.user-copy\.title/,
    }));

    await waitFor(() => {
      expect(screen.getAllByText(
        'marketplace.install.errors.userCopyEffectiveIdentityConflict',
      )).toHaveLength(1);
    });
  });

  it('groups repeated blocking reasons into one localized summary', async () => {
    const user = userEvent.setup();
    vi.mocked(preflightMarketplaceUserCopy).mockResolvedValue({
      ...blockedByEffectiveIdentityConflict,
      blockingIssues: [
        {
          resourceType: 'skill',
          resourceId: 'first-skill',
          sourceLocator: 'skills/first-skill/SKILL.md',
          targetLocator: '.codex/skills/first-skill/SKILL.md',
          errorCode: 'marketplace.user_copy.target_not_writable',
        },
        {
          resourceType: 'skill',
          resourceId: 'second-skill',
          sourceLocator: 'skills/second-skill/SKILL.md',
          targetLocator: '.codex/skills/second-skill/SKILL.md',
          errorCode: 'marketplace.user_copy.target_not_writable',
        },
      ],
    });
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('radio', {
      name: /marketplace\.install\.deliveryMethods\.user-copy\.title/,
    }));

    await waitFor(() => {
      expect(screen.getAllByText(
        'marketplace.install.errors.userCopyTargetNotWritable',
      )).toHaveLength(1);
    });
    expect(screen.getByText(
      'marketplace.install.blockingIssues.affectedResources:2',
    )).toBeInTheDocument();
  });

  it('labels skipped-only confirmation as partial copy', async () => {
    const user = userEvent.setup();
    vi.mocked(preflightMarketplaceUserCopy).mockResolvedValue({
      ...confirmationRequired,
      conflicts: [],
      skippedResources: [{
        code: 'format-unsupported',
        resourceType: 'subagent',
        resourceId: 'reviewer',
        sourceLocator: 'agents/reviewer.md',
      }],
    });
    render(
      <MarketplaceInstallDialog
        open
        item={packageSummary}
        onOpenChange={vi.fn()}
      />,
    );

    await waitForWorkspaceReady();
    await user.click(screen.getByRole('radio', {
      name: /marketplace\.install\.deliveryMethods\.user-copy\.title/,
    }));

    expect(await screen.findByRole('button', {
      name: 'marketplace.install.actions.acceptPartialAndCopy',
    })).toBeDisabled();
    expect(screen.getByLabelText('marketplace.install.skipped.confirmPartial'))
      .toBeInTheDocument();
    expect(screen.getByText('reviewer').closest('li')).toHaveTextContent(
      'marketplace.install.skipped.reasons.formatUnsupported',
    );
  });
});
