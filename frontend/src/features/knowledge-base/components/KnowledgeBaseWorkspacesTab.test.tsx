import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseWorkspacesTab } from './KnowledgeBaseWorkspacesTab';

const { loadUsageMock, providerState, translateMock } = vi.hoisted(() => ({
  loadUsageMock: vi.fn(),
  providerState: {
    workspaceUsageById: {} as Record<string, unknown>,
  },
  translateMock: vi.fn((key: string, values?: Record<string, unknown>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.attachments.description': 'View workspace usage',
      'knowledgeBase.attachments.loading': 'Loading workspace usage...',
      'knowledgeBase.attachments.loadFailed': 'Failed to load workspace usage.',
      'knowledgeBase.attachments.empty': 'No visible workspace usage.',
      'knowledgeBase.attachments.hiddenWorkspaces': `${values?.count} hidden workspace attachments`,
      'knowledgeBase.attachments.status.active': 'Active',
      'knowledgeBase.attachments.status.pending': 'Pending application',
      'knowledgeBase.attachments.status.pending_removal': 'Pending removal',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: translateMock }),
}));

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    workspaceUsageById: providerState.workspaceUsageById,
    loadKnowledgeBaseWorkspaceUsage: loadUsageMock,
  }),
}));

describe('KnowledgeBaseWorkspacesTab', () => {
  beforeEach(() => {
    providerState.workspaceUsageById = {};
    loadUsageMock.mockReset();
    translateMock.mockClear();
  });

  it('renders all canonical attachment states plus the masked count', () => {
    providerState.workspaceUsageById = {
      'kb-1': {
        visibleItems: [
          {
            attachmentId: 'att-1',
            workspaceId: 'ws-1',
            workspaceName: 'Workspace One',
            mountAlias: 'docs',
            attachmentStatus: 'active',
          },
          {
            attachmentId: 'att-2',
            workspaceId: 'ws-2',
            workspaceName: 'Workspace Two',
            mountAlias: 'runbooks',
            attachmentStatus: 'pending',
          },
          {
            attachmentId: 'att-3',
            workspaceId: 'ws-3',
            workspaceName: 'Workspace Three',
            mountAlias: 'handbook',
            attachmentStatus: 'pending_removal',
          },
        ],
        hiddenWorkspaceCount: 2,
        attachmentCount: 5,
      },
    };

    render(<KnowledgeBaseWorkspacesTab knowledgeBaseId="kb-1" />);

    expect(screen.getByText('Workspace One')).toBeInTheDocument();
    expect(screen.getByText('Workspace Two')).toBeInTheDocument();
    expect(screen.getByText('Workspace Three')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Pending application')).toBeInTheDocument();
    expect(screen.getByText('Pending removal')).toBeInTheDocument();
    expect(screen.getByText('2 hidden workspace attachments')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(loadUsageMock).not.toHaveBeenCalled();
  });

  it('shows a localized error without exposing an API message', async () => {
    loadUsageMock.mockRejectedValueOnce(new Error('sensitive backend message'));

    render(<KnowledgeBaseWorkspacesTab knowledgeBaseId="kb-1" />);

    await waitFor(() => {
      expect(loadUsageMock).toHaveBeenCalledWith('kb-1');
      expect(screen.getByText('Failed to load workspace usage.')).toBeInTheDocument();
    });
    expect(screen.queryByText('sensitive backend message')).not.toBeInTheDocument();
  });
});
