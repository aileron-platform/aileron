import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSharingTab } from './KnowledgeBaseSharingTab';

const {
  createShareMock,
  updateShareMock,
  deleteShareMock,
  loadSharesMock,
  searchCandidatesMock,
  toastMock,
  translateMock,
} = vi.hoisted(() => ({
  createShareMock: vi.fn(),
  updateShareMock: vi.fn(),
  deleteShareMock: vi.fn(),
  loadSharesMock: vi.fn(),
  searchCandidatesMock: vi.fn(),
  toastMock: vi.fn(),
  translateMock: vi.fn((key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.sharing.description': 'Manage knowledge base sharing.',
      'knowledgeBase.sharing.addAction': 'Add share',
      'knowledgeBase.sharing.candidate.targetTypeLabel': 'Share with',
      'knowledgeBase.sharing.candidate.targetTypes.user': 'User',
      'knowledgeBase.sharing.candidate.targetTypes.group': 'User group',
      'knowledgeBase.sharing.candidate.userLabel': 'User',
      'knowledgeBase.sharing.candidate.groupLabel': 'User group',
      'knowledgeBase.sharing.candidate.userPlaceholder': 'Search for a user...',
      'knowledgeBase.sharing.candidate.groupPlaceholder': 'Search for a group...',
      'knowledgeBase.sharing.candidate.userEmpty': 'No matching users.',
      'knowledgeBase.sharing.candidate.groupEmpty': 'No matching groups.',
      'knowledgeBase.sharing.candidate.searching': 'Searching...',
      'knowledgeBase.sharing.candidate.startTyping': 'Start typing.',
      'knowledgeBase.sharing.candidate.results': 'Search results',
      'knowledgeBase.sharing.candidate.confirm': 'Add share',
      'knowledgeBase.sharing.table.removeLabel': 'Remove share',
      'knowledgeBase.sharing.createSuccessTitle': 'Share added',
      'knowledgeBase.sharing.createSuccessDescription': '{{name}} now has {{role}} access.',
      'knowledgeBase.sharing.deleteSuccessTitle': 'Share removed',
      'knowledgeBase.sharing.roles.reader.label': 'Reader',
    };
    const template = translations[key] ?? key;
    return Object.entries(params ?? {}).reduce(
      (value, [paramKey, paramValue]) => value.replaceAll(`{{${paramKey}}}`, String(paramValue)),
      template,
    );
  }),
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  searchKnowledgeBaseShareCandidates: searchCandidatesMock,
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    state: { currentLanguage: 'en' },
    t: translateMock,
  }),
}));

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    sharesById: {
      'kb-1': [
        {
          id: 'share-1',
          kbId: 'kb-1',
          targetType: 'user',
          targetId: 'user-2',
          targetLabel: 'Existing User',
          role: 'reader',
          grantedById: 'user-1',
          createdAt: '2026-04-21T00:00:00Z',
        },
      ],
    },
    isMutating: false,
    loadKnowledgeBaseShares: loadSharesMock,
    createKnowledgeBaseShare: createShareMock,
    updateKnowledgeBaseShare: updateShareMock,
    deleteKnowledgeBaseShare: deleteShareMock,
  }),
}));

const openAddDialog = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: 'Add share' }));
  return screen.getByRole('dialog');
};

const renderSharingTab = () => render(
  <KnowledgeBaseSharingTab knowledgeBaseId="kb-1" canManage />,
);

describe('KnowledgeBaseSharingTab', () => {
  beforeEach(() => {
    createShareMock.mockReset();
    updateShareMock.mockReset();
    deleteShareMock.mockReset();
    loadSharesMock.mockReset();
    searchCandidatesMock.mockReset();
    toastMock.mockReset();
    translateMock.mockClear();
  });

  it('shows target labels instead of internal target ids', () => {
    renderSharingTab();

    expect(screen.getByText('Manage knowledge base sharing.')).toBeInTheDocument();
    expect(screen.getByText('Existing User')).toBeInTheDocument();
    expect(screen.queryByText('user-2')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add share' })).toBeInTheDocument();
    expect(loadSharesMock).not.toHaveBeenCalled();
  });

  it('searches a user and creates a user share', async () => {
    createShareMock.mockResolvedValue({
      id: 'share-2',
      kbId: 'kb-1',
      targetType: 'user',
      targetId: 'user-3',
      targetLabel: 'Candidate User',
      role: 'reader',
      grantedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
    });
    searchCandidatesMock.mockResolvedValue([
      { id: 'user-3', label: 'Candidate User', description: 'candidate@example.com' },
    ]);

    renderSharingTab();
    fireEvent.click(screen.getByRole('button', { name: 'Add share' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('combobox', { name: 'User' }));

    fireEvent.change(await screen.findByPlaceholderText('Search for a user...'), {
      target: { value: 'candidate@example.com' },
    });
    await waitFor(() => {
      expect(searchCandidatesMock).toHaveBeenCalledWith('kb-1', 'user', 'candidate@example.com');
    });

    fireEvent.click(await screen.findByText('Candidate User'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add share' }));

    await waitFor(() => {
      expect(createShareMock).toHaveBeenCalledWith('kb-1', {
        targetType: 'user',
        targetId: 'user-3',
        role: 'reader',
      });
    });
  });

  it('switches to groups, searches, selects, and creates a group share', async () => {
    const user = userEvent.setup();
    createShareMock.mockResolvedValue({
      id: 'share-group-1',
      kbId: 'kb-1',
      targetType: 'user_group',
      targetId: 'group-1',
      targetLabel: 'Platform Operations',
      role: 'reader',
      grantedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
    });
    searchCandidatesMock.mockResolvedValue([
      { id: 'group-1', label: 'Platform Operations' },
    ]);

    renderSharingTab();
    const dialog = await openAddDialog(user);
    await user.click(within(dialog).getByRole('radio', { name: 'User group' }));
    await user.click(within(dialog).getByRole('combobox', { name: 'User group' }));
    fireEvent.change(await screen.findByPlaceholderText('Search for a group...'), {
      target: { value: 'platform operations' },
    });

    await waitFor(() => {
      expect(searchCandidatesMock).toHaveBeenCalledWith('kb-1', 'user_group', 'platform operations');
    });
    await user.click(await screen.findByText('Platform Operations'));
    await user.click(within(dialog).getByRole('button', { name: 'Add share' }));

    await waitFor(() => {
      expect(createShareMock).toHaveBeenCalledWith('kb-1', {
        targetType: 'user_group',
        targetId: 'group-1',
        role: 'reader',
      });
      expect(toastMock).toHaveBeenCalledWith({
        title: 'Share added',
        description: 'Platform Operations now has Reader access.',
      });
    });
  });

  it('clears query, results, and selection when changing the target type', async () => {
    const user = userEvent.setup();
    searchCandidatesMock.mockResolvedValue([
      { id: 'user-3', label: 'Candidate User', description: 'candidate@example.com' },
    ]);

    renderSharingTab();
    const dialog = await openAddDialog(user);
    await user.click(within(dialog).getByRole('combobox', { name: 'User' }));
    fireEvent.change(await screen.findByPlaceholderText('Search for a user...'), {
      target: { value: 'candidate' },
    });
    await user.click(await screen.findByText('Candidate User'));
    expect(within(dialog).getByRole('combobox', { name: 'User' })).toHaveTextContent('Candidate User');

    await user.click(within(dialog).getByRole('radio', { name: 'User group' }));

    expect(within(dialog).getByRole('combobox', { name: 'User group' })).toHaveTextContent('Search for a group...');
    expect(within(dialog).getByRole('button', { name: 'Add share' })).toBeDisabled();
    expect(screen.queryByText('Candidate User')).not.toBeInTheDocument();
  });

  it('ignores a stale user search response after switching to groups', async () => {
    const user = userEvent.setup();
    let resolveUserSearch: ((candidates: Array<{ id: string; label: string }>) => void) | undefined;
    let resolveGroupSearch: ((candidates: Array<{ id: string; label: string }>) => void) | undefined;
    searchCandidatesMock
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveUserSearch = resolve;
      }))
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveGroupSearch = resolve;
      }));

    renderSharingTab();
    const dialog = await openAddDialog(user);
    await user.click(within(dialog).getByRole('combobox', { name: 'User' }));
    fireEvent.change(await screen.findByPlaceholderText('Search for a user...'), {
      target: { value: 'candidate' },
    });
    await waitFor(() => {
      expect(searchCandidatesMock).toHaveBeenCalledWith('kb-1', 'user', 'candidate');
    });

    await user.click(within(dialog).getByRole('radio', { name: 'User group' }));
    await user.click(within(dialog).getByRole('combobox', { name: 'User group' }));
    fireEvent.change(await screen.findByPlaceholderText('Search for a group...'), {
      target: { value: 'platform' },
    });
    await waitFor(() => {
      expect(searchCandidatesMock).toHaveBeenCalledWith('kb-1', 'user_group', 'platform');
    });

    await act(async () => {
      resolveGroupSearch?.([{ id: 'group-1', label: 'Platform Operations' }]);
    });
    expect(await screen.findByText('Platform Operations')).toBeInTheDocument();

    await act(async () => {
      resolveUserSearch?.([{ id: 'user-3', label: 'Candidate User' }]);
    });
    expect(screen.getByText('Platform Operations')).toBeInTheDocument();
    expect(screen.queryByText('Candidate User')).not.toBeInTheDocument();
  });

  it('uses the target label in the delete success toast', async () => {
    const user = userEvent.setup();
    deleteShareMock.mockResolvedValue(undefined);
    renderSharingTab();

    await user.click(screen.getByRole('button', { name: 'Remove share' }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'Share removed',
        description: 'Existing User',
      });
    });
  });
});
