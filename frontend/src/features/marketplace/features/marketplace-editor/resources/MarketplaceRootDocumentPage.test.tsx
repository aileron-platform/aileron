import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceRootDocumentPage } from './MarketplaceRootDocumentPage';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

const apiMock = vi.hoisted(() => ({
  getRootDocument: vi.fn(),
  saveRootDocument: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange, placeholder, statusMessage }: {
    value: string;
    onChange(value: string): void;
    placeholder?: string;
    statusMessage?: React.ReactNode;
  }) => (
    <div>
      {statusMessage}
      <textarea
        aria-label={placeholder ?? 'markdown-editor'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  ),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  getRootDocument: (...args: unknown[]) => apiMock.getRootDocument(...args),
  saveRootDocument: (...args: unknown[]) => apiMock.saveRootDocument(...args),
}));

const packageDetail = (): MarketplacePackageDetail => ({
  targetClient: 'codex',
  packageType: 'plugin',
  packageId: 'codex-toolkit',
  displayName: 'Codex Toolkit',
  version: '0.1.0',
  description: 'Package description',
  category: 'coding',
  tags: [],
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/codex-toolkit',
  revision: 'rev1',
  variants: [{
    targetClient: 'codex',
    packageFormat: 'codex-native',
    packageId: 'codex-toolkit',
    displayName: 'Codex Toolkit',
  }],
  updatedAt: '2026-06-26T00:00:00.000Z',
  catalogMetadata: {},
  manifestMetadata: {},
  validationResults: [],
});

const mutationResult = {
  success: true as const,
  path: 'AGENTS.md',
  revision: 'rev2',
  ownerFilePath: null,
  baseEntryFingerprint: null,
};

describe('MarketplaceRootDocumentPage', () => {
  it('retries after the root document fails to load', async () => {
    const user = userEvent.setup();
    apiMock.getRootDocument
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce({
        path: 'AGENTS.md',
        content: '# Retried instructions',
      });

    render(
      <MarketplaceRootDocumentPage
        packageDetail={packageDetail()}
        onMutation={vi.fn()}
      />,
    );

    expect(await screen.findByText('marketplace.common.resourceLoadError')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));

    expect(await screen.findByDisplayValue('# Retried instructions')).toBeInTheDocument();
    expect(apiMock.getRootDocument).toHaveBeenCalledTimes(2);
  }, 20_000);

  it('saves root document with current revision and forwards mutation result', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.getRootDocument.mockResolvedValue({
      path: 'AGENTS.md',
      content: '# Current instructions',
    });
    apiMock.saveRootDocument.mockResolvedValueOnce(mutationResult);

    const { container } = render(
      <MarketplaceRootDocumentPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    expect(container.firstElementChild).toHaveClass('flex-1');
    expect(screen.getByText('marketplace.editor.agentsMd.title')).toBeInTheDocument();
    expect(await screen.findByText('AGENTS.md')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.agentsMd.actions.copy' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.agentsMd.actions.download' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.common.actions.refresh' })).toBeInTheDocument();

    await user.clear(screen.getByLabelText('marketplace.editor.agentsMd.placeholder'));
    await user.type(screen.getByLabelText('marketplace.editor.agentsMd.placeholder'), '# Updated instructions');
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.save' }));

    expect(apiMock.saveRootDocument).toHaveBeenCalledWith('codex', 'codex-toolkit', {
      revision: 'rev1',
      content: '# Updated instructions',
    });
    expect(onMutation).toHaveBeenCalledWith(mutationResult);
  }, 20_000);
});
