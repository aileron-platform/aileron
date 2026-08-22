import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketplaceActivityRecord } from '@/features/marketplace/model/marketplaceTypes';
import {
  getMarketplaceActivityDetail,
  listMarketplaceActivity,
} from '../../../api/marketplaceApi';
import { MarketplaceActivityTab } from './MarketplaceActivityTab';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  getMarketplaceActivityDetail: vi.fn(),
  listMarketplaceActivity: vi.fn(),
}));

const activity: MarketplaceActivityRecord = {
  id: 'activity-1',
  action: 'copy',
  status: 'failed',
  packageFormat: 'agent-plugin/1.0.0',
  targetClient: 'codex',
  packageId: 'review-tools',
  workspaceId: 'workspace-1',
  operationId: 'operation-1',
  errorCode: 'marketplace.user_copy.plan_stale',
  createdAt: '2026-07-25T00:00:00Z',
};

describe('MarketplaceActivityTab', () => {
  beforeEach(() => {
    vi.mocked(getMarketplaceActivityDetail).mockReset();
    vi.mocked(getMarketplaceActivityDetail).mockResolvedValue({
      ...activity,
      workspaceIdSnapshot: 'workspace-1',
      targetLocators: [],
      diagnosticCodes: [],
      commands: [{
        sequence: 1,
        stage: 'plugin-install',
        argvDisplay: 'codex plugin add review-tools',
        exitCode: 0,
        startedAt: '2026-07-25T00:00:00Z',
        endedAt: '2026-07-25T00:00:01Z',
        stdout: 'installed review-tools',
        stderr: null,
        stdoutOriginalByteCount: 22,
        stderrOriginalByteCount: 0,
        truncated: false,
      }],
    });
    vi.mocked(listMarketplaceActivity).mockReset();
    vi.mocked(listMarketplaceActivity).mockResolvedValue({
      items: [activity],
      total: 51,
      page: 1,
      pageSize: 50,
      totalPages: 2,
    });
  });

  it('loads raw per-command CLI output only when details are requested', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceActivityTab />
      </MemoryRouter>,
    );

    await screen.findByText('marketplace.activity.actions.copy');
    expect(getMarketplaceActivityDetail).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', {
      name: 'marketplace.settings.activity.showDetails',
    }));

    expect(await screen.findByText('installed review-tools')).toBeVisible();
    expect(screen.getByText('codex plugin add review-tools')).toBeVisible();
    expect(getMarketplaceActivityDetail).toHaveBeenCalledWith('activity-1');
  });

  it('renders a one-shot copy activity and keeps raw error codes in diagnostics', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceActivityTab />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('marketplace.activity.actions.copy'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('marketplace.install.errors.userCopyPlanStale'),
    ).toBeInTheDocument();
    expect(screen.getByText('operation-1')).toBeInTheDocument();
    expect(
      screen.queryByText('marketplace.user_copy.plan_stale'),
    ).not.toBeVisible();

    await user.click(
      screen.getByText('marketplace.settings.activity.errorDetails'),
    );
    expect(
      screen.getByText('marketplace.user_copy.plan_stale'),
    ).toBeVisible();
  });

  it('requests the next backend page', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceActivityTab />
      </MemoryRouter>,
    );

    await screen.findByText('marketplace.activity.actions.copy');
    await user.click(
      screen.getByRole('button', {
        name: 'marketplace.settings.activity.pagination.next',
      }),
    );

    await waitFor(() => {
      expect(listMarketplaceActivity).toHaveBeenLastCalledWith({
        page: 2,
        pageSize: 50,
        workspaceId: undefined,
        packageFormat: undefined,
        targetClient: undefined,
        packageId: undefined,
        action: undefined,
        status: undefined,
      });
    });
  });

  it('hydrates filters from the URL and sends the full backend query', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/?workspaceId=workspace-2&packageFormat=agent-plugin%2F1.0.0&targetClient=codex&packageId=tools&action=install&status=failed&page=2',
        ]}
      >
        <MarketplaceActivityTab />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(listMarketplaceActivity).toHaveBeenCalledWith({
        page: 2,
        pageSize: 50,
        workspaceId: 'workspace-2',
        packageFormat: 'agent-plugin/1.0.0',
        targetClient: 'codex',
        packageId: 'tools',
        action: 'install',
        status: 'failed',
      });
    });
  });
});
