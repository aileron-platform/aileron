import React, { StrictMode, useEffect } from 'react';
import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceRealtimeProvider } from './WorkspaceRealtimeProvider';
import { useTerminalStream } from './useTerminalStream';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('./terminalInstanceRegistry', () => ({
  disposeAllTerminalInstances: vi.fn(),
  disposeTerminalInstance: vi.fn(),
}));

const executionGrantBrokerMock = vi.hoisted(() => ({
  registerTarget: vi.fn(),
  getGrant: vi.fn(),
}));

vi.mock('@/features/auth/public', () => ({
  executionGrantBroker: executionGrantBrokerMock,
}));

const tabMetadata = {
  tab_id: 'tab-1',
  session_id: 'session-1',
  working_directory: '/workspace',
  cols: 80,
  rows: 24,
  created_at: 100,
  last_active_at: 100,
  status: 'running',
  exit_code: null,
};

class FakeWebSocket extends EventTarget {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];

  constructor(public url: string) {
    super();
    FakeWebSocket.instances.push(this);
  }

  send = vi.fn((message: string) => {
    this.sent.push(message);
  });

  close = vi.fn(() => {
    this.readyState = FakeWebSocket.CLOSED;
    this.dispatchEvent(new CloseEvent('close', { code: 1000 }));
  });

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.dispatchEvent(new Event('open'));
  }

  message(payload: unknown) {
    this.dispatchEvent(new MessageEvent('message', {
      data: JSON.stringify(payload),
    }));
  }
}

const ScopedActionProbe: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const {
    ensureConnected,
    createTab,
    sendInput,
    sendResize,
  } = useTerminalStream();

  useEffect(() => {
    ensureConnected();
    if (workspaceId !== 'workspace-2') {
      return;
    }
    createTab({
      workingDirectory: '/workspace/new',
      size: { cols: 120, rows: 40 },
    });
    sendInput('tab-1', 'workspace-2-input');
    sendResize('tab-1', 120, 40);
  }, [
    createTab,
    ensureConnected,
    sendInput,
    sendResize,
    workspaceId,
  ]);

  return null;
};

describe('WorkspaceRealtimeProvider terminal scope integration', () => {
  beforeEach(() => {
    FakeWebSocket.instances.length = 0;
    vi.stubGlobal('WebSocket', FakeWebSocket);
    executionGrantBrokerMock.registerTarget.mockReset();
    executionGrantBrokerMock.getGrant.mockReset();
    executionGrantBrokerMock.getGrant.mockResolvedValue('signed-terminal-grant');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('routes child-effect actions only after the provider activates their workspace scope', async () => {
    const { rerender } = render(
      <StrictMode>
        <WorkspaceRealtimeProvider
          workspaceId="workspace-1"
          runtimeUrl="/workspaces/workspace-1/runtime"
        >
          <ScopedActionProbe workspaceId="workspace-1" />
        </WorkspaceRealtimeProvider>
      </StrictMode>,
    );

    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const oldSocket = FakeWebSocket.instances.at(-1)!;
    act(() => {
      oldSocket.open();
      oldSocket.message({
        type: 'tab_list',
        data: { tabs: [tabMetadata] },
      });
    });
    oldSocket.sent.length = 0;
    const socketCountBeforeWorkspaceChange = FakeWebSocket.instances.length;

    rerender(
      <StrictMode>
        <WorkspaceRealtimeProvider
          workspaceId="workspace-2"
          runtimeUrl="/workspaces/workspace-2/runtime"
        >
          <ScopedActionProbe workspaceId="workspace-2" />
        </WorkspaceRealtimeProvider>
      </StrictMode>,
    );

    expect(oldSocket.sent).toEqual([]);
    expect(oldSocket.close).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(FakeWebSocket.instances).toHaveLength(socketCountBeforeWorkspaceChange + 1);
    });

    const replacementSocket = FakeWebSocket.instances.at(-1)!;
    act(() => {
      replacementSocket.open();
      replacementSocket.message({
        type: 'tab_list',
        data: { tabs: [] },
      });
      replacementSocket.message({
        type: 'tab_list',
        data: { tabs: [] },
      });
    });

    const replacementMessages = replacementSocket.sent.map((message) => (
      JSON.parse(message)
    ));
    const createMessages = replacementMessages.filter(
      (message) => message.type === 'create_tab',
    );
    expect(createMessages).toHaveLength(1);
    expect(createMessages[0].data).toMatchObject({
      working_directory: '/workspace/new',
      cols: 120,
      rows: 40,
    });
    expect(
      replacementMessages.some((message) => message.type === 'input'),
    ).toBe(false);
    expect(
      replacementMessages.some((message) => message.type === 'resize'),
    ).toBe(false);
    expect(executionGrantBrokerMock.getGrant).toHaveBeenCalledWith(
      '/workspaces/workspace-2/runtime/ws/terminal',
      'workspace-terminal',
      'terminal',
      'workspace-2',
    );
  });
});
