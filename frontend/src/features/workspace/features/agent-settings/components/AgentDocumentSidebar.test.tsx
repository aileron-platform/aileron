import { QueryClient } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@/__tests__/utils/render';
import { agentSettingsQueryKeys } from '../api/agentSettingsQueryKeys';
import AgentDocumentSidebar from './AgentDocumentSidebar';

const apiMocks = vi.hoisted(() => ({
  listSlashCommands: vi.fn(),
}));

vi.mock('../api/agentSettingsApi', () => ({
  createAgentSettingsApi: () => apiMocks,
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('AgentDocumentSidebar shared collection query', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reuses the workbench collection result without issuing another list request', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    queryClient.setQueryData(
      agentSettingsQueryKeys.documentCollection(
        'http://runtime.test',
        'workspace-1',
        'slash-commands',
        'claude-code',
      ),
      {
        items: [{
          id: 'project:review.md',
          title: 'Review command',
          scope: 'project',
          content: '',
          metadata: { fileName: 'review.md' },
        }],
        availableScopes: [{ scope: 'project', writable: true }],
      },
    );

    render(
      <AgentDocumentSidebar
        resource="slash-commands"
        selectedId={null}
        onSelect={vi.fn()}
        apiPrefix="claude-code"
      />,
      { queryClient },
    );

    expect(await screen.findByText('Review command')).toBeInTheDocument();
    expect(apiMocks.listSlashCommands).not.toHaveBeenCalled();
  });
});
