import type React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AiChatFileChooserProps, AiChatIntegrationValue } from '@/features/ai-chat/public';
import { I18nProvider } from '@/shared/contexts/I18nContext';
import { WorkspaceFileChooserDialog } from './WorkspaceFileChooserDialog';
import { WorkspaceAiChatIntegration } from './WorkspaceAiChatIntegration';
import { useWorkspaceAiChatSelection } from './WorkspaceAiChatSelectionContext';

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  navigate: vi.fn(),
  syncCanvas: vi.fn(),
  canUseAgentChat: true,
  canWriteWorkspace: true,
  integrationValue: null as AiChatIntegrationValue | null,
  workspaceRuntime: {
    workspaceId: 'ws-1' as string | null,
    runtimeBaseUrl: 'https://runtime.test' as string | null,
  },
  fileTreeState: {
    nodes: [{
      id: '/README.md',
      name: 'README.md',
      path: '/README.md',
      type: 'file',
      depth: 0,
    }],
  },
  fileTreeActions: {
    refreshFileTree: vi.fn(),
    expandNode: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock('@/features/ai-chat/public', () => ({
  AiChatIntegrationProvider: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: AiChatIntegrationValue;
  }) => {
    mocks.integrationValue = value;
    return <>{children}</>;
  },
}));

vi.mock('../../providers/WorkspaceContext', () => ({
  useWorkspace: () => ({
    dispatch: mocks.dispatch,
    permissions: {
      canUseChat: mocks.canUseAgentChat,
      canWrite: mocks.canWriteWorkspace,
    },
    workspaceRuntime: mocks.workspaceRuntime,
    fileTreeState: mocks.fileTreeState,
    fileTreeActions: mocks.fileTreeActions,
  }),
}));

vi.mock('../../api/workspaceRuntimeApi', () => ({
  syncCanvas: (...args: unknown[]) => mocks.syncCanvas(...args),
}));

describe('WorkspaceAiChatIntegration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.integrationValue = null;
    mocks.canUseAgentChat = true;
    mocks.canWriteWorkspace = true;
    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.workspaceRuntime.runtimeBaseUrl = 'https://runtime.test';
    mocks.syncCanvas.mockResolvedValue({ rendererAction: 'reused' });
    mocks.fileTreeActions.refreshFileTree.mockResolvedValue(undefined);
    mocks.fileTreeActions.expandNode.mockResolvedValue(undefined);
  });

  it('refreshes the existing Workspace file tree each time the chooser opens', async () => {
    const t = ((key: string) => key) as AiChatFileChooserProps['t'];
    const onOpenChange = vi.fn();
    const onFileSelect = vi.fn();
    const { rerender } = render(
      <WorkspaceFileChooserDialog
        open
        onOpenChange={onOpenChange}
        onFileSelect={onFileSelect}
        t={t}
      />,
      { wrapper: I18nProvider },
    );

    await waitFor(() => {
      expect(mocks.fileTreeActions.refreshFileTree).toHaveBeenCalledTimes(1);
    });

    rerender(
      <WorkspaceFileChooserDialog
        open={false}
        onOpenChange={onOpenChange}
        onFileSelect={onFileSelect}
        t={t}
      />,
    );
    rerender(
      <WorkspaceFileChooserDialog
        open
        onOpenChange={onOpenChange}
        onFileSelect={onFileSelect}
        t={t}
      />,
    );

    await waitFor(() => {
      expect(mocks.fileTreeActions.refreshFileTree).toHaveBeenCalledTimes(2);
    });
  });

  it('provides Workspace identity and delegates Canvas opening to Workspace orchestration', () => {
    render(
      <WorkspaceAiChatIntegration>
        <div>integration-child</div>
      </WorkspaceAiChatIntegration>,
    );

    expect(screen.getByText('integration-child')).toBeInTheDocument();
    expect(mocks.integrationValue).toMatchObject({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'https://runtime.test',
      fileChooser: WorkspaceFileChooserDialog,
    });

    act(() => {
      mocks.integrationValue?.openCanvas?.();
    });

    expect(mocks.dispatch).toHaveBeenCalledTimes(1);
    expect(mocks.dispatch).toHaveBeenCalledWith({
      type: 'SET_CURRENT_FEATURE',
      payload: 'canvas',
    });
    expect(mocks.navigate).toHaveBeenCalledWith('/workspaces/ws-1/canvas');
    expect(mocks.syncCanvas).toHaveBeenCalledWith('https://runtime.test', 'ws-1');
  });

  it('opens Canvas without synchronizing when Workspace write access is unavailable', () => {
    mocks.canWriteWorkspace = false;

    render(
      <WorkspaceAiChatIntegration>
        <div>integration-child</div>
      </WorkspaceAiChatIntegration>,
    );

    act(() => {
      mocks.integrationValue?.openCanvas?.();
    });

    expect(mocks.navigate).toHaveBeenCalledWith('/workspaces/ws-1/canvas');
    expect(mocks.syncCanvas).not.toHaveBeenCalled();
  });

  it('keeps the latest editor selection available and activates the AI Chat companion', async () => {
    const SelectionTrigger = () => {
      const { selectCodeReference } = useWorkspaceAiChatSelection();
      return (
        <button
          type="button"
          onClick={() => selectCodeReference({
            filePath: '/src/App.tsx',
            fileName: 'App.tsx',
            startLine: 12,
            endLine: 18,
          })}
        >
          select-code
        </button>
      );
    };

    render(
      <WorkspaceAiChatIntegration>
        <SelectionTrigger />
      </WorkspaceAiChatIntegration>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-code' }));

    await waitFor(() => {
      expect(mocks.integrationValue?.codeReference).toEqual({
        filePath: '/src/App.tsx',
        fileName: 'App.tsx',
        startLine: 12,
        endLine: 18,
      });
    });
    expect(mocks.dispatch).toHaveBeenCalledWith({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'ai-chat',
    });

    act(() => {
      mocks.integrationValue?.clearCodeReference?.();
    });

    await waitFor(() => {
      expect(mocks.integrationValue?.codeReference).toBeNull();
    });
  });

  it('increments the companion reveal request only for an allowed code selection', async () => {
    const SelectionTrigger = () => {
      const { selectCodeReference, companionRevealRequestId } = useWorkspaceAiChatSelection();
      return (
        <>
          <output data-testid="reveal-request-id">{companionRevealRequestId}</output>
          <button
            type="button"
            onClick={() => selectCodeReference({
              filePath: '/src/App.tsx',
              fileName: 'App.tsx',
              startLine: 12,
              endLine: 18,
            })}
          >
            select-code
          </button>
        </>
      );
    };

    const { rerender } = render(
      <WorkspaceAiChatIntegration>
        <SelectionTrigger />
      </WorkspaceAiChatIntegration>,
    );

    expect(screen.getByTestId('reveal-request-id')).toHaveTextContent('0');
    fireEvent.click(screen.getByRole('button', { name: 'select-code' }));
    await waitFor(() => expect(screen.getByTestId('reveal-request-id')).toHaveTextContent('1'));

    mocks.canUseAgentChat = false;
    rerender(
      <WorkspaceAiChatIntegration>
        <SelectionTrigger />
      </WorkspaceAiChatIntegration>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'select-code' }));
    expect(screen.getByTestId('reveal-request-id')).toHaveTextContent('1');
  });

  it('retains a handoff while switching from Terminal to AI Chat and resolves it after consumption', async () => {
    render(
      <WorkspaceAiChatIntegration>
        <div>integration-child</div>
      </WorkspaceAiChatIntegration>,
    );

    let handoffPromise: Promise<void> | undefined;
    act(() => {
      handoffPromise = mocks.integrationValue?.handoffToAiChat?.({
        content: '#1 spacing',
        delivery: 'draft',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      });
    });

    await waitFor(() => {
      expect(mocks.integrationValue?.pendingHandoff).toMatchObject({
        workspaceId: 'ws-1',
        content: '#1 spacing',
        delivery: 'draft',
      });
    });
    expect(mocks.dispatch).toHaveBeenCalledWith({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'ai-chat',
    });

    const handoffId = mocks.integrationValue?.pendingHandoff?.id;
    expect(handoffId).toBeTruthy();
    act(() => {
      mocks.integrationValue?.completeHandoff?.(handoffId!);
    });

    await expect(handoffPromise).resolves.toBeUndefined();
    await waitFor(() => expect(mocks.integrationValue?.pendingHandoff).toBeNull());
  });

  it('ignores editor selections when AI Chat access is unavailable', () => {
    mocks.canUseAgentChat = false;

    const SelectionTrigger = () => {
      const {
        canSelectCodeReference,
        selectCodeReference,
      } = useWorkspaceAiChatSelection();
      return (
        <button
          type="button"
          data-selection-enabled={canSelectCodeReference}
          onClick={() => selectCodeReference({
            filePath: '/src/App.tsx',
            fileName: 'App.tsx',
            startLine: 12,
            endLine: 18,
          })}
        >
          select-code
        </button>
      );
    };

    render(
      <WorkspaceAiChatIntegration>
        <SelectionTrigger />
      </WorkspaceAiChatIntegration>,
    );

    const selectionButton = screen.getByRole('button', { name: 'select-code' });
    expect(selectionButton).toHaveAttribute('data-selection-enabled', 'false');
    fireEvent.click(selectionButton);
    expect(mocks.integrationValue?.codeReference).toBeNull();
    expect(mocks.dispatch).not.toHaveBeenCalledWith({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'ai-chat',
    });
  });
});
