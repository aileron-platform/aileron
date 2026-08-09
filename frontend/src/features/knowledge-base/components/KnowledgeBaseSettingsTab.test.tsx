import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSettingsTab } from './KnowledgeBaseSettingsTab';

const {
  updateKnowledgeBaseMock,
  updateKnowledgeBaseVisibilityMock,
  deleteKnowledgeBaseMock,
  toastMock,
} = vi.hoisted(() => ({
  updateKnowledgeBaseMock: vi.fn(),
  updateKnowledgeBaseVisibilityMock: vi.fn(),
  deleteKnowledgeBaseMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const detail = {
  id: 'kb-1',
  slug: 'kb-one',
  name: 'KB One',
  description: 'Original description',
  ownerId: 'user-1',
  currentSizeBytes: 2048,
  quotaBytes: 4096,
  effectiveQuotaBytes: 4096,
  quotaSource: 'custom' as const,
  utilizationPercent: 50,
  ownerQuotaUsedBytes: 8192,
  ownerEffectiveQuotaBytes: 16384,
  accessRole: 'owner' as const,
  accessSource: 'owned' as const,
  accessSources: ['owned'] as const,
  visibility: 'private' as const,
  allowedOperations: [],
  createdAt: '2026-06-01T00:00:00Z',
  updatedAt: '2026-06-01T00:00:00Z',
};

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    detailById: { 'kb-1': detail },
    isMutating: false,
    updateKnowledgeBase: updateKnowledgeBaseMock,
    updateKnowledgeBaseVisibility: updateKnowledgeBaseVisibilityMock,
    deleteKnowledgeBase: deleteKnowledgeBaseMock,
  }),
}));

const LocationProbe: React.FC = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
};

const renderTab = (props: Partial<React.ComponentProps<typeof KnowledgeBaseSettingsTab>> = {}) => render(
  <MemoryRouter initialEntries={['/knowledge-bases/kb-1/settings']}>
    <KnowledgeBaseSettingsTab
      knowledgeBaseId="kb-1"
      canManage
      canManageVisibility
      canDelete
      {...props}
    />
    <LocationProbe />
  </MemoryRouter>,
);

describe('KnowledgeBaseSettingsTab', () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(HTMLElement.prototype, 'setPointerCapture', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, 'releasePointerCapture', {
      configurable: true,
      value: vi.fn(),
    });
    updateKnowledgeBaseMock.mockReset();
    updateKnowledgeBaseVisibilityMock.mockReset();
    deleteKnowledgeBaseMock.mockReset();
    toastMock.mockReset();
    updateKnowledgeBaseMock.mockResolvedValue({ ...detail, name: 'KB Two' });
    updateKnowledgeBaseVisibilityMock.mockResolvedValue({ ...detail, visibility: 'public' });
    deleteKnowledgeBaseMock.mockResolvedValue(undefined);
  });

  it('renders form fields populated from the knowledge base detail', () => {
    renderTab();
    expect(screen.getByLabelText('knowledgeBase.detail.settings.nameLabel')).toHaveValue('KB One');
    expect(screen.getByLabelText('knowledgeBase.detail.settings.slugLabel')).toHaveValue('kb-one');
    expect(screen.getByLabelText('knowledgeBase.detail.settings.slugLabel')).toBeDisabled();
    expect(screen.getByLabelText('knowledgeBase.detail.settings.descriptionLabel')).toHaveValue('Original description');
    expect(screen.queryByLabelText('knowledgeBase.detail.settings.quotaLabel')).not.toBeInTheDocument();
    expect(screen.getByText('2 KB')).toBeInTheDocument();
    expect(screen.getByText('4 KB')).toBeInTheDocument();
    expect(screen.getByText('knowledgeBase.detail.settings.capacity.quotaSources.custom'))
      .toBeInTheDocument();
  });

  it('saves trimmed values through the provider', async () => {
    const user = userEvent.setup();
    renderTab();
    const nameInput = screen.getByLabelText('knowledgeBase.detail.settings.nameLabel');
    await user.clear(nameInput);
    await user.type(nameInput, '  KB Two  ');
    fireEvent.click(screen.getByRole('button', { name: 'knowledgeBase.common.actions.save' }));
    await waitFor(() => {
      expect(updateKnowledgeBaseMock).toHaveBeenCalledWith('kb-1', {
        name: 'KB Two',
        description: 'Original description',
      });
    });
  });

  it('updates public visibility through the dedicated provider operation', async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByLabelText('knowledgeBase.detail.settings.visibility.label'));
    await user.click(await screen.findByRole('option', {
      name: 'knowledgeBase.detail.settings.visibility.options.public',
    }));

    await waitFor(() => {
      expect(updateKnowledgeBaseVisibilityMock).toHaveBeenCalledWith('kb-1', {
        visibility: 'public',
      });
    });
  });

  it('shows owner aggregate quota pressure as read-only information', () => {
    renderTab();
    expect(screen.getByText('8 KB')).toBeInTheDocument();
    expect(screen.getByText('16 KB')).toBeInTheDocument();
  });

  it('deletes the knowledge base after confirmation and navigates to the list', async () => {
    const user = userEvent.setup();
    renderTab();
    await user.click(screen.getByRole('button', { name: 'knowledgeBase.detail.deleteAction' }));
    await user.type(
      screen.getByLabelText('knowledgeBase.detail.delete.confirmationLabel'),
      'KB One',
    );
    await user.click(screen.getByRole('button', { name: 'knowledgeBase.detail.delete.confirm' }));
    await waitFor(() => {
      expect(deleteKnowledgeBaseMock).toHaveBeenCalledWith('kb-1', 'KB One');
    });
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases');
    });
  });

  it('localizes update failures instead of exposing machine error codes', async () => {
    updateKnowledgeBaseMock.mockRejectedValueOnce(new Error('KB_ACCESS_DENIED'));
    renderTab();
    fireEvent.click(screen.getByRole('button', { name: 'knowledgeBase.common.actions.save' }));
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        variant: 'destructive',
        title: 'knowledgeBase.detail.settings.toasts.saveFailed.title',
        description: 'knowledgeBase.detail.settings.toasts.saveFailed.description',
      }));
    });
    expect(toastMock).not.toHaveBeenCalledWith(
      expect.objectContaining({ description: 'KB_ACCESS_DENIED' }),
    );
  });

  it('shows an error toast and stays on the page when delete fails', async () => {
    const user = userEvent.setup();
    deleteKnowledgeBaseMock.mockRejectedValueOnce(new Error('delete blocked'));
    renderTab();
    await user.click(screen.getByRole('button', { name: 'knowledgeBase.detail.deleteAction' }));
    await user.type(
      screen.getByLabelText('knowledgeBase.detail.delete.confirmationLabel'),
      'KB One',
    );
    await user.click(screen.getByRole('button', { name: 'knowledgeBase.detail.delete.confirm' }));
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        variant: 'destructive',
        title: 'knowledgeBase.detail.delete.toasts.failed.title',
        description: 'knowledgeBase.detail.delete.toasts.failed.description',
      }));
    });
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/settings');
  });

  it('keeps primary controls visible but disabled when the user cannot manage', () => {
    renderTab({ canManage: false, canManageVisibility: false, canDelete: false });
    expect(screen.getByLabelText('knowledgeBase.detail.settings.nameLabel')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'knowledgeBase.common.actions.save' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'knowledgeBase.detail.deleteAction' })).toBeDisabled();
    expect(screen.getByLabelText('knowledgeBase.detail.settings.visibility.label')).toBeDisabled();
  });

  it('keeps metadata management but disables deletion for a manager', () => {
    renderTab({ canManage: true, canManageVisibility: false, canDelete: false });

    expect(screen.getByRole('button', { name: 'knowledgeBase.common.actions.save' })).toBeInTheDocument();
    expect(screen.getByLabelText('knowledgeBase.detail.settings.nameLabel')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'knowledgeBase.detail.deleteAction' })).toBeDisabled();
  });
});
