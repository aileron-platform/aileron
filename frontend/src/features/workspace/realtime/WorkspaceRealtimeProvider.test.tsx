import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceRealtimeProvider } from './WorkspaceRealtimeProvider';
import { disposeAllTerminalInstances } from './terminalInstanceRegistry';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('./terminalInstanceRegistry', () => ({
  disposeAllTerminalInstances: vi.fn(),
  disposeTerminalInstance: vi.fn(),
}));

vi.mock('./terminalRealtimeManager', () => ({
  TerminalRealtimeManager: class {
    declareScope = vi.fn(() => ({
      api: {},
      activate: vi.fn(),
    }));
    dispose = vi.fn();
  },
}));

vi.mock('@/shared/realtime/webSocketConnectionRegistry', () => ({
  WebSocketConnectionRegistry: class {
    dispose = vi.fn();
  },
}));

describe('WorkspaceRealtimeProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not wipe terminals that already exist for the workspace it mounts with', () => {
    // A child TerminalTab can create its xterm instance in the same commit
    // before this provider's own effect runs (React fires child effects
    // before parent effects). If mounting with an already-known workspaceId
    // is treated as a scope change, it would destroy that instance.
    render(
      <WorkspaceRealtimeProvider workspaceId="workspace-1" runtimeUrl={null}>
        <div />
      </WorkspaceRealtimeProvider>,
    );

    expect(disposeAllTerminalInstances).not.toHaveBeenCalled();
  });

  it('still disposes terminals when the workspace scope actually changes', () => {
    const { rerender } = render(
      <WorkspaceRealtimeProvider workspaceId="workspace-1" runtimeUrl={null}>
        <div />
      </WorkspaceRealtimeProvider>,
    );

    rerender(
      <WorkspaceRealtimeProvider workspaceId="workspace-2" runtimeUrl={null}>
        <div />
      </WorkspaceRealtimeProvider>,
    );

    expect(disposeAllTerminalInstances).toHaveBeenCalledTimes(1);
  });

  it('still disposes terminals on unmount', () => {
    const { unmount } = render(
      <WorkspaceRealtimeProvider workspaceId="workspace-1" runtimeUrl={null}>
        <div />
      </WorkspaceRealtimeProvider>,
    );

    unmount();

    expect(disposeAllTerminalInstances).toHaveBeenCalledTimes(1);
  });
});
