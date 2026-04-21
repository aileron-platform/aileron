import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { MountedKnowledgeBasesPanel } from './MountedKnowledgeBasesPanel';

const { restartRuntimeMock, toastMock, reloadMock, translateMock } = vi.hoisted(() => ({
  restartRuntimeMock: vi.fn(),
  toastMock: vi.fn(),
  reloadMock: vi.fn(),
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.knowledgeBases.mounted.title': 'Mounted knowledge bases',
      'workspace.workspaceSettings.knowledgeBases.mounted.description':
        'Shows the knowledge base mounts currently applied in the runtime.',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingBadge': 'Pending',
      'workspace.workspaceSettings.knowledgeBases.mounted.signatureLabel': 'Mounted signature',
      'workspace.workspaceSettings.knowledgeBases.mounted.signatureMissing': 'No mounted signature yet',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingHint':
        'The mounted state does not match the desired attachments yet.',
      'workspace.workspaceSettings.knowledgeBases.mounted.syncedHint':
        'The mounted state is in sync with the desired attachments.',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingTitle':
        'Mount changes are waiting to be applied',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingDescription':
        'Restart the runtime to apply the latest knowledge base attachments.',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingEmpty':
        'The API cannot reconstruct the previous mounted list directly; restart the runtime to apply the latest configuration.',
      'workspace.workspaceSettings.knowledgeBases.mounted.empty':
        'The runtime currently has no mounted knowledge bases.',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.label':
        'Restart runtime to apply',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.loading':
        'Restarting runtime...',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.successTitle':
        'Runtime restart started',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.successDescription':
        'Knowledge base mount changes will apply after the runtime restarts.',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.errorTitle':
        'Runtime restart failed',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.errorDescription':
        'Failed to restart the runtime to apply knowledge base changes.',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/features/workspace/services/workspaceLifecycleApi', () => ({
  workspaceLifecycleApi: {
    restartRuntime: restartRuntimeMock,
  },
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      reload: reloadMock,
    },
  }),
}));

describe('MountedKnowledgeBasesPanel', () => {
  beforeEach(() => {
    restartRuntimeMock.mockReset();
    toastMock.mockReset();
    reloadMock.mockReset();
    translateMock.mockClear();
  });

  it('在已同步時顯示 mounted attachments', () => {
    render(
      <MountedKnowledgeBasesPanel
        workspaceId="ws-1"
        attachments={[
          {
            id: 'att-1',
            kbId: 'kb-1',
            name: 'Product Docs',
            slug: 'product-docs',
            role: 'editor',
            mountAlias: 'docs',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-21T00:00:00Z',
          },
        ]}
        mountedKbSignature="sig-123456"
        hasPendingKbChanges={false}
      />,
    );

    expect(screen.getByText('Mounted knowledge bases')).toBeInTheDocument();
    expect(screen.getByText('Product Docs')).toBeInTheDocument();
    expect(screen.getByText('/knowledge/docs')).toBeInTheDocument();
    expect(screen.queryByText('Pending')).not.toBeInTheDocument();
  });

  it('pending 狀態會顯示 badge 並可重啟 runtime', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    restartRuntimeMock.mockResolvedValue({ status: 'accepted' });
    reloadMock.mockResolvedValue(undefined);
    onRefresh.mockResolvedValue(undefined);

    render(
      <MountedKnowledgeBasesPanel
        workspaceId="ws-1"
        attachments={[
          {
            id: 'att-1',
            kbId: 'kb-1',
            name: 'Product Docs',
            slug: 'product-docs',
            role: 'editor',
            mountAlias: 'docs',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-21T00:00:00Z',
          },
        ]}
        mountedKbSignature="sig-123456"
        hasPendingKbChanges
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Mount changes are waiting to be applied')).toBeInTheDocument();
    expect(screen.queryByText('Product Docs')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Restart runtime to apply' }));

    await waitFor(() => {
      expect(restartRuntimeMock).toHaveBeenCalledWith('ws-1');
    });
    expect(reloadMock).toHaveBeenCalled();
    expect(onRefresh).toHaveBeenCalled();
  });
});
