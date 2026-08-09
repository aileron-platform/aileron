import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { act, fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { WorkspaceKnowledgeBasesSettings } from './WorkspaceKnowledgeBasesSettings';

const {
  ApiErrorMock,
  getMock,
  postMock,
  patchMock,
  deleteMock,
  toastMock,
  translateMock,
  workspaceState,
  workspacePermissions,
} = vi.hoisted(() => ({
  ApiErrorMock: class ApiErrorMock extends Error {
    errorCode?: string;

    constructor(message: string, errorCode?: string) {
      super(message);
      this.errorCode = errorCode;
    }
  },
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  toastMock: vi.fn(),
  workspaceState: { workspaceId: 'ws-123' },
  workspacePermissions: {
    canWriteAttachments: true,
  },
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.knowledgeBases.header.title': 'Knowledge Bases',
      'workspace.workspaceSettings.knowledgeBases.status.loading': 'Loading workspace knowledge bases...',
      'workspace.workspaceSettings.knowledgeBases.desired.title': 'Desired attachments',
      'workspace.workspaceSettings.knowledgeBases.desired.attachAction': 'Attach knowledge base',
      'workspace.workspaceSettings.knowledgeBases.desired.detachAction': 'Detach',
      'workspace.workspaceSettings.knowledgeBases.desired.saveAlias': 'Save alias',
      'workspace.workspaceSettings.knowledgeBases.desired.savingAlias': 'Saving...',
      'workspace.workspaceSettings.knowledgeBases.desired.empty': 'No attachments',
      'workspace.workspaceSettings.knowledgeBases.dialog.title': 'Attach knowledge base',
      'workspace.workspaceSettings.knowledgeBases.dialog.placeholder': 'Select a knowledge base',
      'workspace.workspaceSettings.knowledgeBases.dialog.empty': 'No knowledge bases available',
      'workspace.workspaceSettings.knowledgeBases.dialog.cancel': 'Cancel',
      'workspace.workspaceSettings.knowledgeBases.dialog.confirm': 'Attach',
      'workspace.workspaceSettings.knowledgeBases.form.knowledgeBaseLabel': 'Knowledge Base',
      'workspace.workspaceSettings.knowledgeBases.form.aliasLabel': 'Mount alias',
      'workspace.workspaceSettings.knowledgeBases.attachmentStatus.active': 'Active',
      'workspace.workspaceSettings.knowledgeBases.attachmentStatus.pending': 'Pending application',
      'workspace.workspaceSettings.knowledgeBases.attachmentStatus.pending_removal': 'Pending removal',
      'workspace.workspaceSettings.knowledgeBases.attachmentStatusDescription.pending':
        'Waiting for mount verification.',
      'workspace.workspaceSettings.knowledgeBases.attachmentStatusDescription.pending_removal':
        'Waiting for removal verification.',
      'workspace.workspaceSettings.knowledgeBases.mounted.title': 'Runtime synchronization',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.title': 'Knowledge base mounts',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.title': 'Workspace access recycle',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.ready': 'Ready',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.syncing': 'Syncing',
      'workspace.workspaceSettings.knowledgeBases.mounted.mount.status.degraded': 'Degraded',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.status.ready': 'Access ready',
      'workspace.workspaceSettings.knowledgeBases.mounted.access.status.recycling': 'Recycling',
      'workspace.workspaceSettings.knowledgeBases.mounted.desiredRevision': 'Desired revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.observedRevision': 'Observed revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.lastKnownGoodRevision': 'Last-known-good revision',
      'workspace.workspaceSettings.knowledgeBases.mounted.degradedTitle': 'Mount synchronization is degraded',
      'workspace.workspaceSettings.knowledgeBases.mounted.compensating.title':
        'Restoring the last-known-good mounts',
      'workspace.workspaceSettings.knowledgeBases.mounted.compensating.description':
        'The failed candidate is being rolled back.',
      'workspace.workspaceSettings.knowledgeBases.mounted.retry': 'Retry synchronization',
      'workspace.workspaceSettings.knowledgeBases.errors.WORKSPACE_KB_MOUNT_RECONCILE_FAILED': 'Mount reconciliation failed',
      'workspace.workspaceSettings.knowledgeBases.notifications.loadFailed': 'Load failed',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiError: ApiErrorMock,
  apiClient: {
    get: getMock,
    post: postMock,
    patch: patchMock,
    delete: deleteMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: translateMock }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: { workspaceId: workspaceState.workspaceId },
    permissions: workspacePermissions,
  }),
}));

const detail = {
  id: 'ws-123',
  accessRole: 'manager',
  runtimeAccessRevision: 4,
  runtimeAccessObservedRevision: 4,
};

const sync = (
  status: 'ready' | 'syncing' | 'degraded' = 'ready',
  overrides: Record<string, unknown> = {},
) => ({
  status,
  desiredRevision: status === 'ready' ? 3 : 4,
  observedRevision: 3,
  lastKnownGoodRevision: 3,
  errorCode: status === 'degraded' ? 'WORKSPACE_KB_MOUNT_RECONCILE_FAILED' : null,
  compensating: false,
  ...overrides,
});

const attachment = (overrides: Record<string, unknown> = {}) => ({
  id: 'att-1',
  kbId: 'kb-1',
  name: 'Product Docs',
  slug: 'product-docs',
  mountAlias: 'docs',
  status: 'active',
  attachedById: 'user-1',
  createdAt: '2026-07-20T00:00:00Z',
  updatedAt: null,
  ...overrides,
});

const mockInitialLoad = (items = [attachment()], mountSync = sync()) => {
  getMock
    .mockResolvedValueOnce(detail)
    .mockResolvedValueOnce({ items, knowledgeBaseMountSync: mountSync });
};

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

describe('WorkspaceKnowledgeBasesSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
    toastMock.mockReset();
    translateMock.mockClear();
    workspaceState.workspaceId = 'ws-123';
    workspacePermissions.canWriteAttachments = true;
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('loads the canonical attachment and sync endpoints without mode or direct role UI', async () => {
    mockInitialLoad([
      attachment(),
      attachment({ id: 'att-2', kbId: 'kb-2', name: 'Runbooks', status: 'pending' }),
      attachment({
        id: 'att-3',
        kbId: 'kb-3',
        name: 'Handbook',
        status: 'pending_removal',
      }),
    ], sync('syncing'));

    render(<WorkspaceKnowledgeBasesSettings />);

    expect(await screen.findByText('Product Docs')).toBeInTheDocument();
    expect(screen.getByText('Runbooks')).toBeInTheDocument();
    expect(screen.getByText('Handbook')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Pending application')).toBeInTheDocument();
    expect(screen.getByText('Pending removal')).toBeInTheDocument();
    expect(screen.getByText('Waiting for mount verification.')).toBeInTheDocument();
    expect(screen.getByText('Waiting for removal verification.')).toBeInTheDocument();
    expect(screen.getByText('Syncing')).toBeInTheDocument();
    const aliasInputs = screen.getAllByLabelText('Mount alias');
    expect(aliasInputs[0]).toBeEnabled();
    expect(aliasInputs[1]).toBeDisabled();
    expect(aliasInputs[2]).toBeDisabled();
    const detachButtons = screen.getAllByRole('button', { name: 'Detach' });
    expect(detachButtons[0]).toBeEnabled();
    expect(detachButtons[1]).toBeDisabled();
    expect(detachButtons[2]).toBeDisabled();
    expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws-123',
      expect.objectContaining({ signal: expect.anything() }),
    );
    expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws-123/knowledge-bases',
      expect.objectContaining({ signal: expect.anything() }),
    );
    expect(screen.queryByRole('combobox', { name: 'Mode' })).not.toBeInTheDocument();
    expect(screen.queryByText('editor')).not.toBeInTheDocument();
  });

  it('attaches with only kbId and required mountAlias, then consumes the 202 payload', async () => {
    const user = userEvent.setup();
    mockInitialLoad([]);
    getMock.mockResolvedValueOnce({
      items: [{ id: 'kb-2', slug: 'api-guides', name: 'API Guides', description: null }],
    });
    postMock.mockResolvedValueOnce({
      attachment: attachment({
        id: 'att-2',
        kbId: 'kb-2',
        name: 'API Guides',
        slug: 'api-guides',
        mountAlias: 'guides',
        status: 'pending',
      }),
      knowledgeBaseMountSync: sync('syncing'),
    });

    render(<WorkspaceKnowledgeBasesSettings />);

    await screen.findByText('No attachments');
    await user.click(screen.getByRole('button', { name: 'Attach knowledge base' }));
    await user.click(screen.getByRole('combobox', { name: 'Knowledge Base' }));
    await user.click(await screen.findByText('API Guides'));
    await user.clear(screen.getByLabelText('Mount alias'));
    await user.type(screen.getByLabelText('Mount alias'), 'guides');
    await user.click(screen.getByRole('button', { name: 'Attach' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/workspaces/ws-123/knowledge-bases', {
        kbId: 'kb-2',
        mountAlias: 'guides',
      });
    });
    expect(await screen.findByText('API Guides')).toBeInTheDocument();
    expect(screen.getByText('Pending application')).toBeInTheDocument();
    expect(screen.getByLabelText('Mount alias')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Detach' })).toBeDisabled();
    expect(getMock).toHaveBeenCalledTimes(3);
  });

  it('polls a syncing mount in place until the degraded state is visible', async () => {
    vi.useFakeTimers();
    try {
      mockInitialLoad(
        [attachment({ status: 'pending' })],
        sync('syncing'),
      );
      getMock.mockResolvedValueOnce({
        items: [attachment()],
        knowledgeBaseMountSync: sync('degraded'),
      });

      render(<WorkspaceKnowledgeBasesSettings />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText('Syncing')).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });

      expect(screen.getByText('Degraded')).toBeInTheDocument();
      expect(screen.getByText('Mount synchronization is degraded')).toBeVisible();
      expect(screen.getByRole('button', { name: 'Retry synchronization' })).toBeEnabled();
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(getMock).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it('preserves an unsaved alias draft while polling refreshes server state', async () => {
    vi.useFakeTimers();
    try {
      mockInitialLoad([attachment()], sync('syncing'));
      getMock.mockResolvedValueOnce({
        items: [attachment()],
        knowledgeBaseMountSync: sync('ready'),
      });

      render(<WorkspaceKnowledgeBasesSettings />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      const aliasInput = screen.getByLabelText('Mount alias');
      fireEvent.change(aliasInput, { target: { value: 'local-draft' } });
      expect(aliasInput).toHaveValue('local-draft');

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });

      expect(screen.getByLabelText('Mount alias')).toHaveValue('local-draft');
      expect(screen.getByRole('button', { name: 'Save alias' })).toBeEnabled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('backs off after a polling error and clears it after recovery', async () => {
    vi.useFakeTimers();
    try {
      mockInitialLoad([attachment()], sync('syncing'));
      getMock
        .mockRejectedValueOnce(new Error('temporary failure'))
        .mockResolvedValueOnce({
          items: [attachment()],
          knowledgeBaseMountSync: sync('ready'),
        });

      render(<WorkspaceKnowledgeBasesSettings />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });
      expect(screen.getByText('Load failed')).toBeVisible();
      expect(getMock).toHaveBeenCalledTimes(3);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(3_999);
      });
      expect(getMock).toHaveBeenCalledTimes(3);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(getMock).toHaveBeenCalledTimes(4);
      expect(screen.queryByText('Load failed')).not.toBeInTheDocument();
      expect(screen.getByText('Ready')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('stops polling after synchronization is complete', async () => {
    vi.useFakeTimers();
    try {
      mockInitialLoad([attachment()], sync('syncing'));
      getMock.mockResolvedValueOnce({
        items: [attachment()],
        knowledgeBaseMountSync: sync('ready'),
      });

      render(<WorkspaceKnowledgeBasesSettings />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });

      expect(screen.getByText('Ready')).toBeInTheDocument();
      expect(getMock).toHaveBeenCalledTimes(3);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect(getMock).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it('bounds consecutive polling failures', async () => {
    vi.useFakeTimers();
    try {
      mockInitialLoad([attachment()], sync('syncing'));
      getMock.mockRejectedValue(new Error('persistent failure'));

      render(<WorkspaceKnowledgeBasesSettings />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(120_000);
      });

      expect(getMock).toHaveBeenCalledTimes(6);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(120_000);
      });
      expect(getMock).toHaveBeenCalledTimes(6);
    } finally {
      vi.useRealTimers();
    }
  });

  it('ignores an old workspace response after switching workspaces', async () => {
    const oldDetailResponse = deferred<typeof detail>();
    const oldAttachmentResponse = deferred<{
      items: ReturnType<typeof attachment>[];
      knowledgeBaseMountSync: ReturnType<typeof sync>;
    }>();
    const oldSignals: AbortSignal[] = [];
    workspaceState.workspaceId = 'ws-old';
    getMock.mockImplementation((
      path: string,
      options?: { signal?: AbortSignal },
    ) => {
      if (path === '/workspaces/ws-old') {
        if (options?.signal) oldSignals.push(options.signal);
        return oldDetailResponse.promise;
      }
      if (path === '/workspaces/ws-old/knowledge-bases') {
        if (options?.signal) oldSignals.push(options.signal);
        return oldAttachmentResponse.promise;
      }
      if (path === '/workspaces/ws-new') {
        return Promise.resolve({ ...detail, id: 'ws-new' });
      }
      if (path === '/workspaces/ws-new/knowledge-bases') {
        return Promise.resolve({
          items: [attachment({ name: 'New Workspace Docs', mountAlias: 'new-docs' })],
          knowledgeBaseMountSync: sync('ready'),
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    const { rerender } = render(<WorkspaceKnowledgeBasesSettings />);
    await act(async () => {
      await Promise.resolve();
    });

    workspaceState.workspaceId = 'ws-new';
    rerender(<WorkspaceKnowledgeBasesSettings />);

    expect(await screen.findByText('New Workspace Docs')).toBeInTheDocument();
    expect(oldSignals).toHaveLength(2);
    expect(oldSignals.every((signal) => signal.aborted)).toBe(true);

    await act(async () => {
      oldDetailResponse.resolve({ ...detail, id: 'ws-old' });
      oldAttachmentResponse.resolve({
        items: [attachment({ name: 'Old Workspace Docs', mountAlias: 'old-docs' })],
        knowledgeBaseMountSync: sync('ready'),
      });
      await Promise.all([oldDetailResponse.promise, oldAttachmentResponse.promise]);
    });

    expect(screen.queryByText('Old Workspace Docs')).not.toBeInTheDocument();
    expect(screen.getByText('New Workspace Docs')).toBeInTheDocument();
    expect(screen.getByLabelText('Mount alias')).toHaveValue('new-docs');
  });

  it('updates only the mount alias and applies the returned revision', async () => {
    const user = userEvent.setup();
    mockInitialLoad();
    patchMock.mockResolvedValueOnce({
      attachment: attachment({ mountAlias: 'handbook', status: 'pending' }),
      knowledgeBaseMountSync: sync('syncing'),
    });

    render(<WorkspaceKnowledgeBasesSettings />);

    const aliasInput = await screen.findByLabelText('Mount alias');
    await user.clear(aliasInput);
    await user.type(aliasInput, 'handbook');
    await user.click(screen.getByRole('button', { name: 'Save alias' }));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith('/workspaces/ws-123/knowledge-bases/att-1', {
        mountAlias: 'handbook',
      });
    });
    expect(screen.getByText('Syncing')).toBeInTheDocument();
    expect(screen.getByText('Pending application')).toBeInTheDocument();
    expect(screen.getByLabelText('Mount alias')).toBeDisabled();
  });

  it('does not normalize the mount alias before sending the mutation', async () => {
    const user = userEvent.setup();
    mockInitialLoad();
    patchMock.mockRejectedValueOnce(new ApiErrorMock('Invalid alias', 'KB_MOUNT_ALIAS_INVALID'));

    render(<WorkspaceKnowledgeBasesSettings />);

    const aliasInput = await screen.findByLabelText('Mount alias');
    await user.clear(aliasInput);
    await user.type(aliasInput, ' handbook ');
    await user.click(screen.getByRole('button', { name: 'Save alias' }));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith('/workspaces/ws-123/knowledge-bases/att-1', {
        mountAlias: ' handbook ',
      });
    });
  });

  it('keeps the returned pending-removal row after DELETE 202', async () => {
    const user = userEvent.setup();
    mockInitialLoad();
    deleteMock.mockResolvedValueOnce({
      attachment: attachment({ status: 'pending_removal' }),
      knowledgeBaseMountSync: sync('syncing'),
    });

    render(<WorkspaceKnowledgeBasesSettings />);

    await user.click(await screen.findByRole('button', { name: 'Detach' }));

    await waitFor(() => {
      expect(deleteMock).toHaveBeenCalledWith('/workspaces/ws-123/knowledge-bases/att-1');
      expect(screen.getByText('Pending removal')).toBeInTheDocument();
    });
    expect(screen.getByText('Product Docs')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Detach' })).toBeDisabled();
    expect(screen.getByLabelText('Mount alias')).toBeDisabled();
  });

  it('retries only a degraded sync through the dedicated endpoint', async () => {
    const user = userEvent.setup();
    mockInitialLoad([attachment()], sync('degraded'));
    postMock.mockResolvedValueOnce({ knowledgeBaseMountSync: sync('syncing') });

    render(<WorkspaceKnowledgeBasesSettings />);

    await user.click(await screen.findByRole('button', { name: 'Retry synchronization' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        '/workspaces/ws-123/knowledge-base-mount-sync/retry',
      );
      expect(screen.getByText('Syncing')).toBeInTheDocument();
    });
  });

  it('does not apply a retry-ready refresh after unmount', async () => {
    const user = userEvent.setup();
    const retryRefresh = deferred<{
      items: ReturnType<typeof attachment>[];
      knowledgeBaseMountSync: ReturnType<typeof sync>;
    }>();
    mockInitialLoad([attachment()], sync('degraded'));
    getMock.mockReturnValueOnce(retryRefresh.promise);
    postMock.mockResolvedValueOnce({ knowledgeBaseMountSync: sync('ready') });

    const { unmount } = render(<WorkspaceKnowledgeBasesSettings />);

    await user.click(await screen.findByRole('button', { name: 'Retry synchronization' }));
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(3);
    });
    expect(toastMock).not.toHaveBeenCalled();

    unmount();
    await act(async () => {
      retryRefresh.resolve({
        items: [attachment({ mountAlias: 'refreshed-docs' })],
        knowledgeBaseMountSync: sync('ready'),
      });
      await retryRefresh.promise;
      await Promise.resolve();
    });

    expect(toastMock).not.toHaveBeenCalled();
  });
});
