import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketplaceActivityRecord } from '@/features/marketplace/model/marketplaceTypes';
import { listMarketplaceActivity } from '../../../api/marketplaceApi';
import { MarketplaceActivityTab } from './MarketplaceActivityTab';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  listMarketplaceActivity: vi.fn(),
}));

const activity: MarketplaceActivityRecord = {
  id: 'activity-1',
  action: 'copy',
  status: 'failed',
  provider: 'codex',
  packageId: 'review-tools',
  workspaceId: 'workspace-1',
  operationId: 'operation-1',
  errorCode: 'marketplace.user_copy.plan_stale',
  createdAt: '2026-07-25T00:00:00Z',
};

describe('MarketplaceActivityTab', () => {
  beforeEach(() => {
    vi.mocked(listMarketplaceActivity).mockReset();
    vi.mocked(listMarketplaceActivity).mockResolvedValue({
      items: [activity],
      total: 51,
      page: 1,
      pageSize: 50,
      totalPages: 2,
    });
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
        provider: undefined,
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
          '/?workspaceId=workspace-2&provider=codex&packageId=tools&action=install&status=failed&page=2',
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
        provider: 'codex',
        packageId: 'tools',
        action: 'install',
        status: 'failed',
      });
    });
  });
});
