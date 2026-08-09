import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceBasicPage } from './MarketplaceBasicPage';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

const apiMock = vi.hoisted(() => ({
  updateBasic: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  updateBasic: (...args: unknown[]) => apiMock.updateBasic(...args),
}));

const packageDetail = (): MarketplacePackageDetail => ({
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'codex-toolkit',
  displayName: 'Codex Toolkit',
  version: '0.1.0',
  description: 'Initial description',
  category: 'coding',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  lifecycleStatus: 'draft',
  registryPath: 'codex/plugins/codex-toolkit',
  revision: 'rev1',
  variants: [{
    provider: 'codex',
    packageId: 'codex-toolkit',
    displayName: 'Codex Toolkit',
  }],
  updatedAt: '2026-06-26T00:00:00.000Z',
  catalogMetadata: { name: 'Codex Toolkit' },
  manifestMetadata: { name: 'codex-toolkit' },
  validationResults: [],
});

const mutationResult = {
  success: true as const,
  path: '.codex/plugin.json',
  revision: 'rev2',
  ownerFilePath: null,
  baseEntryFingerprint: null,
};

describe('MarketplaceBasicPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders packageId as read-only and saves through updateBasic', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.updateBasic.mockResolvedValueOnce(mutationResult);

    const { container } = render(
      <MarketplaceBasicPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    expect(container.firstElementChild).toHaveClass('flex-1');
    expect(screen.getByRole('heading', { name: 'marketplace.editor.tabs.basic' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'marketplace.common.actions.save' })).toHaveLength(1);
    expect(screen.getAllByDisplayValue('codex-toolkit')[0]).toHaveAttribute('readonly');
    expect(screen.getByText('marketplace.editor.fields.provider')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.fields.registryPath')).toBeInTheDocument();
    expect(screen.getByDisplayValue('codex/plugins/codex-toolkit')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.requiredFields.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.requiredTabs.form')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.requiredTabs.json')).toBeInTheDocument();

    const displayNameInput = screen.getByDisplayValue('Codex Toolkit');
    const descriptionInput = screen.getByDisplayValue('Initial description');
    await user.clear(displayNameInput);
    await user.type(displayNameInput, 'Toolkit Updated');
    await user.clear(descriptionInput);
    await user.type(descriptionInput, 'Updated description');
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.save' }));

    expect(apiMock.updateBasic).toHaveBeenCalledWith('codex', 'codex-toolkit', expect.objectContaining({
      revision: 'rev1',
      displayName: 'Toolkit Updated',
      description: 'Updated description',
    }));
    expect(onMutation).toHaveBeenCalledWith(mutationResult);
  });

  it('disables save while the mutation is pending to prevent duplicate submissions', async () => {
    let resolveUpdate!: (value: typeof mutationResult) => void;
    apiMock.updateBasic.mockImplementationOnce(
      () => new Promise(resolve => { resolveUpdate = resolve; }),
    );
    const onMutation = vi.fn().mockResolvedValue(undefined);
    render(
      <MarketplaceBasicPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    const save = screen.getByRole('button', { name: 'marketplace.common.actions.save' });
    fireEvent.click(save);
    fireEvent.click(save);

    expect(save).toBeDisabled();
    expect(apiMock.updateBasic).toHaveBeenCalledTimes(1);
    resolveUpdate(mutationResult);
    await waitFor(() => expect(save).toBeEnabled());
  });
});
