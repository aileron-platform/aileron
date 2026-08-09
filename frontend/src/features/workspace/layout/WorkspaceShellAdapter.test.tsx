import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { render } from '@/__tests__/utils/render';
import type { ProductShellProps } from '@/shared/components/shell';
import { initialState } from '../providers/workspaceStateConstants';
import type { WorkspaceState } from '../providers/workspaceStateTypes';
import { WorkspaceShellAdapter } from './WorkspaceShellAdapter';

const mocks = vi.hoisted(() => ({
  productShellMock: vi.fn(),
  dispatchMock: vi.fn(),
  refreshVersionControlMock: vi.fn(),
  queryClient: {},
  workspaceState: undefined as unknown as WorkspaceState,
  workspaceRuntime: {
    workspaceId: 'ws-1',
    runtimeBaseUrl: '/workspaces/ws-1/runtime',
    agenticTools: ['claude-code'],
  },
  permissions: {
    canRead: true,
    canUseChat: true,
    canUseTerminal: true,
  },
}));

vi.mock('@/shared/components/shell', () => ({
  ProductShell: (props: ProductShellProps) => {
    mocks.productShellMock(props);
    return <div data-testid="product-shell-adapter" />;
  },
}));

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: mocks.workspaceState,
    dispatch: mocks.dispatchMock,
    permissions: mocks.permissions,
    workspaceRuntime: mocks.workspaceRuntime,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...actual,
    useQueryClient: () => mocks.queryClient,
  };
});

vi.mock('../integrations/version-control/workspaceVersionControlSession', () => ({
  useWorkspaceVersionControlSession: () => ({
    refresh: mocks.refreshVersionControlMock,
  }),
}));

vi.mock('./WorkspaceSidebar', () => ({
  WorkspaceSidebar: () => <div data-testid="workspace-sidebar" />,
}));

vi.mock('./WorkspaceFeatureContent', () => ({
  WorkspaceFeatureContent: ({ column }: { column: string }) => (
    <div data-testid={`workspace-feature-${column}`} />
  ),
}));

vi.mock('./WorkspaceCompanionColumn', () => ({
  WorkspaceCompanionCollapsedContent: () => <div data-testid="companion-collapsed" />,
  WorkspaceCompanionColumn: () => <div data-testid="workspace-companion-column" />,
  WorkspaceCompanionHeader: () => <div data-testid="workspace-companion-header" />,
}));

vi.mock('./hooks/useWorkspaceDocumentSelection', () => ({
  useWorkspaceDocumentSelection: () => ({
    selectedId: null,
    handleSelect: vi.fn(),
    handleDirtyChange: vi.fn(),
    selectionBlocked: false,
  }),
}));

vi.mock('../integrations/ai-chat/WorkspaceAiChatSelectionContext', () => ({
  useOptionalWorkspaceAiChatSelection: () => ({ companionRevealRequestId: 0 }),
}));

vi.mock('../realtime/WorkspaceRealtimeProvider', () => ({
  WorkspaceRealtimeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../features/version-control/VersionControlPage', () => ({
  VersionControlProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const getProductShellProps = (): ProductShellProps => {
  const props = mocks.productShellMock.mock.calls.at(-1)?.[0] as ProductShellProps | undefined;
  if (!props) {
    throw new Error('ProductShell was not composed');
  }
  return props;
};

const getRegionsBody = (props: ProductShellProps) => {
  if (props.body.kind !== 'regions') {
    throw new Error('Expected a regions body');
  }
  return props.body;
};

describe('WorkspaceShellAdapter', () => {
  beforeEach(() => {
    mocks.productShellMock.mockReset();
    mocks.dispatchMock.mockReset();
    mocks.refreshVersionControlMock.mockReset();
    mocks.refreshVersionControlMock.mockResolvedValue(undefined);
    mocks.workspaceState = {
      ...initialState,
      currentFeature: 'file-management',
      companionActiveTab: 'ai-chat',
      companionTerminalPlacement: 'side',
      chatExpanded: false,
      mainContentExpanded: false,
      fileManagementEditorExpanded: false,
      agentToolSettings: { ...initialState.agentToolSettings, subView: '' },
      containerManagement: { ...initialState.containerManagement, subView: 'runtime' },
    };
    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.permissions.canRead = true;
    mocks.permissions.canUseChat = true;
    mocks.permissions.canUseTerminal = true;
  });

  it('composes route, auth, content and region state into one ProductShell body', () => {
    render(
      <WorkspaceShellAdapter navigationSlot={<div data-testid="navigation-slot" />}>
        <div data-testid="route-content" />
      </WorkspaceShellAdapter>,
    );

    const body = getRegionsBody(getProductShellProps());
    expect(body.navigation).toBeDefined();
    expect(body.navigator).toBeDefined();
    expect(body.main.accessibleLabel).toBe('workspace.layout.mainContent');
    expect(body.companion?.placement).toBe('side');
    expect(getProductShellProps().preferences?.identity).toBe('workspace:ws-1');
    expect(mocks.productShellMock).toHaveBeenCalledTimes(1);
  });

  it('declares the shared expanded width baseline for navigation regions', () => {
    render(
      <WorkspaceShellAdapter navigationSlot={<div />}>
        <div />
      </WorkspaceShellAdapter>,
    );

    const body = getRegionsBody(getProductShellProps());
    expect(body.navigation?.behavior).toEqual({
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 500,
    });
    expect(body.navigation?.presentation.responsive).toBe('always');
    expect(body.navigator?.behavior).toEqual({
      collapsible: true,
      resizable: true,
      defaultWidth: 270,
      minWidth: 270,
      maxWidth: 600,
    });
    expect(body.navigator?.presentation.responsive).toBe('always');
  });

  it('refreshes version-control data from the second-column header in changes and history views', async () => {
    mocks.workspaceState.currentFeature = 'version-control';
    mocks.workspaceState.versionControl = {
      ...mocks.workspaceState.versionControl,
      subView: 'changes',
    };
    const shellView = render(
      <WorkspaceShellAdapter navigationSlot={<div />}>
        <div />
      </WorkspaceShellAdapter>,
    );

    await waitFor(() => {
      expect(mocks.productShellMock).toHaveBeenCalled();
    });

    const changesHeader = getRegionsBody(getProductShellProps()).navigator?.presentation.header;
    const actionView = render(<>{changesHeader?.actions}</>);
    fireEvent.click(screen.getByRole('button', {
      name: 'shared.versionControl.actions.refresh.label',
    }));

    await waitFor(() => {
      expect(mocks.refreshVersionControlMock).toHaveBeenCalledWith(
        mocks.queryClient,
        ['changes', 'history', 'remote'],
      );
    });

    mocks.workspaceState.versionControl = {
      ...mocks.workspaceState.versionControl,
      subView: 'history',
    };
    shellView.rerender(
      <WorkspaceShellAdapter navigationSlot={<div />}>
        <div />
      </WorkspaceShellAdapter>,
    );
    await waitFor(() => {
      expect(getRegionsBody(getProductShellProps()).navigator?.presentation.header?.title)
        .toBe('workspace.versionControl.sidebar.title.history');
    });
    const historyHeader = getRegionsBody(getProductShellProps()).navigator?.presentation.header;
    actionView.rerender(<>{historyHeader?.actions}</>);
    fireEvent.click(screen.getByRole('button', {
      name: 'shared.versionControl.actions.refresh.label',
    }));

    await waitFor(() => {
      expect(mocks.refreshVersionControlMock).toHaveBeenCalledTimes(2);
    });
  });

  it('omits the companion presentation header for bottom Terminal without CSS hiding', () => {
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(
      <WorkspaceShellAdapter navigationSlot={<div />}>
        <div />
      </WorkspaceShellAdapter>,
    );

    const companion = getRegionsBody(getProductShellProps()).companion;
    expect(companion?.placement).toBe('bottom');
    expect(companion?.presentation.header).toBeUndefined();
  });

  it('keeps side Terminal and AI Chat headers while switching route state', () => {
    mocks.workspaceState.companionActiveTab = 'terminal';
    const view = render(<WorkspaceShellAdapter navigationSlot={<div />} />);
    expect(getRegionsBody(getProductShellProps()).companion?.presentation.header).toBeDefined();

    mocks.workspaceState.companionActiveTab = 'ai-chat';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';
    view.rerender(<WorkspaceShellAdapter navigationSlot={<div />} />);
    expect(getRegionsBody(getProductShellProps()).companion?.placement).toBe('side');
    expect(getRegionsBody(getProductShellProps()).companion?.presentation.header).toBeDefined();

    mocks.workspaceState.currentFeature = 'container-management';
    mocks.workspaceState.containerManagement = { subView: 'terminal' };
    view.rerender(<WorkspaceShellAdapter navigationSlot={<div />} />);
    expect(getRegionsBody(getProductShellProps()).companion).toBeUndefined();
  });

  it('keeps state, denied, loading and fullscreen surfaces on the intended paths', () => {
    const stateContent = <div data-testid="state-content" />;
    render(
      <WorkspaceShellAdapter navigationSlot={<div />} stateContent={stateContent}>
        <div />
      </WorkspaceShellAdapter>,
    );
    expect(getProductShellProps().body).toEqual({ kind: 'state', content: stateContent });

    mocks.workspaceState = { ...mocks.workspaceState, currentFeature: 'file-management' };
    mocks.workspaceRuntime.workspaceId = null;
    mocks.permissions.canRead = false;
    const view = render(<WorkspaceShellAdapter navigationSlot={<div />} />);
    const loadingBody = getRegionsBody(getProductShellProps());
    expect(loadingBody.navigator).toBeUndefined();
    expect(loadingBody.companion).toBeUndefined();

    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.permissions.canRead = true;
    mocks.workspaceState.chatExpanded = true;
    view.rerender(<WorkspaceShellAdapter navigationSlot={<div />} />);
    expect(getProductShellProps().display).toEqual({
      mode: 'companion-fullscreen',
      onExit: expect.any(Function),
    });
  });
});
