import type { Terminal } from '@xterm/xterm';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WebSocketConnectionRegistry } from '@/shared/realtime/webSocketConnectionRegistry';
import { TerminalRealtimeManager } from './terminalRealtimeManager';
import { TERMINAL_MAX_TABS } from './terminalPolicy';
import { executionGrantBroker } from '@/features/auth/public';

vi.mock('@/features/auth/public', () => ({
  executionGrantBroker: {
    registerTarget: vi.fn(),
    getGrant: vi.fn(() => 'signed-grant'),
  },
}));

const tabMetadata = {
  tab_id: 'tab-1',
  session_id: 'session-1',
  working_directory: '/workspace',
  cols: 80,
  rows: 24,
  created_at: 100,
  last_active_at: 100,
  status: 'running' as const,
  exit_code: null,
};

const createTerminal = () => ({
  write: vi.fn(),
  reset: vi.fn(),
});

const activeApis = new WeakMap<TerminalRealtimeManager, ReturnType<
  TerminalRealtimeManager['declareScope']
>['api']>();

const activateBinding = (
  manager: TerminalRealtimeManager,
  binding: ReturnType<TerminalRealtimeManager['declareScope']>,
) => {
  binding.activate();
  activeApis.set(manager, binding.api);
  return binding.api;
};

const activateScope = (
  manager: TerminalRealtimeManager,
  workspaceId = 'ws-1',
  terminalUrl?: string | null,
) => {
  const resolvedTerminalUrl = terminalUrl === undefined
    ? `/workspaces/${workspaceId}/runtime/ws/terminal`
    : terminalUrl;
  const binding = manager.declareScope(workspaceId, resolvedTerminalUrl);
  return activateBinding(manager, binding);
};

const apiFor = (manager: TerminalRealtimeManager) => {
  const api = activeApis.get(manager);
  if (!api) {
    throw new Error('Terminal scope is not active');
  }
  return api;
};

const flushPromiseChain = async () => {
  for (let index = 0; index < 10; index += 1) {
    await Promise.resolve();
  }
};

class FakeWebSocket extends EventTarget {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  protocols: string[];

  constructor(public url: string, protocols?: string | string[]) {
    super();
    this.protocols = Array.isArray(protocols)
      ? protocols
      : protocols
        ? [protocols]
        : [];
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

describe('TerminalRealtimeManager', () => {
  beforeEach(() => {
    FakeWebSocket.instances.length = 0;
    vi.mocked(executionGrantBroker.getGrant).mockReset();
    vi.mocked(executionGrantBroker.getGrant).mockReturnValue('signed-grant');
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('writes output directly to the attached terminal without touching the store', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });

    apiFor(manager).attachXterm('tab-1', terminal);

    const listener = vi.fn();
    apiFor(manager).subscribe(listener);

    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'hello', seq: 1 } });

    expect(terminal.write).toHaveBeenCalledWith('hello');
    expect(listener).not.toHaveBeenCalled();
  });

  it('drops duplicate output chunks by sequence number', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    apiFor(manager).attachXterm('tab-1', terminal);

    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'hello', seq: 5 } });
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'hello', seq: 5 } });
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'stale', seq: 3 } });

    expect((terminal.write as unknown as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);
  });

  it('recovers output that arrived before the terminal was attached by replaying on attach', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });

    // No terminal registered yet: dropped without advancing lastSeq.
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'missed', seq: 1 } });
    expect(terminal.write).not.toHaveBeenCalled();

    apiFor(manager).attachXterm('tab-1', terminal);

    const replayMessages = socket.sent
      .map((message) => JSON.parse(message))
      .filter((message) => message.type === 'replay' && message.tab_id === 'tab-1');
    expect(replayMessages.at(-1)?.data).toEqual({ from_seq: 1 });
  });

  it('requests replay from lastSeq + 1 for attached tabs when the server resends tab_list', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    apiFor(manager).attachXterm('tab-1', terminal);
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'hello', seq: 5 } });

    socket.sent.length = 0;
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });

    const replayMessages = socket.sent
      .map((message) => JSON.parse(message))
      .filter((message) => message.type === 'replay' && message.tab_id === 'tab-1');
    expect(replayMessages.at(-1)?.data).toEqual({ from_seq: 6 });
  });

  it('resets the terminal and replays from the new floor on tab_replay_reset', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    apiFor(manager).attachXterm('tab-1', terminal);
    socket.sent.length = 0;

    socket.message({
      type: 'tab_replay_reset',
      tab_id: 'tab-1',
      data: { requested_seq: 1, floor_seq: 10 },
    });

    expect(terminal.reset).toHaveBeenCalledTimes(1);
    const replayMessages = socket.sent
      .map((message) => JSON.parse(message))
      .filter((message) => message.type === 'replay' && message.tab_id === 'tab-1');
    expect(replayMessages.at(-1)?.data).toEqual({ from_seq: 10 });
  });

  it('sends a clear request and resets local seq tracking once the server confirms it', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    apiFor(manager).attachXterm('tab-1', terminal);
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'before clear', seq: 5 } });
    socket.sent.length = 0;

    apiFor(manager).clearTerminal('tab-1');

    expect(socket.sent).toContainEqual(JSON.stringify({ type: 'clear', tab_id: 'tab-1' }));
    // The terminal must not reset until the server confirms the clear.
    expect(terminal.reset).not.toHaveBeenCalled();

    socket.message({ type: 'tab_cleared', tab_id: 'tab-1', data: { floor_seq: 6 } });

    expect(terminal.reset).toHaveBeenCalledTimes(1);

    // A late duplicate of the pre-clear output must still be dropped, and a
    // fresh chunk at the new floor must be written.
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'stale', seq: 5 } });
    expect(terminal.write).not.toHaveBeenCalledWith('stale');

    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'after clear', seq: 6 } });
    expect(terminal.write).toHaveBeenCalledWith('after clear');
  });

  it('stops writing to a terminal after the tab is closed locally', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);
    const terminal = createTerminal() as unknown as Terminal;

    apiFor(manager).ensureConnected();
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    apiFor(manager).attachXterm('tab-1', terminal);

    apiFor(manager).closeTab('tab-1');
    socket.message({ type: 'output', tab_id: 'tab-1', data: { data: 'after-close', seq: 1 } });

    expect(terminal.write).not.toHaveBeenCalledWith('after-close');
  });

  it('ensureConnected does not create a second socket while connecting', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureConnected();
    apiFor(manager).ensureConnected();

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('deduplicates connection attempts while an Execution Grant is pending', async () => {
    let resolveGrant: ((grant: string) => void) | undefined;
    vi.mocked(executionGrantBroker.getGrant).mockReturnValue(new Promise<string>((resolve) => {
      resolveGrant = resolve;
    }));
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureConnected();
    apiFor(manager).ensureConnected();

    expect(executionGrantBroker.getGrant).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(0);

    resolveGrant?.('grant-for-ws-1');
    await flushPromiseChain();

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('discards a delayed Execution Grant after the active workspace changes', async () => {
    const resolvers = new Map<string, (grant: string) => void>();
    vi.mocked(executionGrantBroker.getGrant).mockImplementation((
      _targetUrl,
      _audience,
      _action,
      workspaceId,
    ) => new Promise<string>((resolve) => {
      resolvers.set(workspaceId ?? '', resolve);
    }));
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', '/workspaces/ws-1/runtime/ws/terminal');
    apiFor(manager).ensureConnected();

    activateScope(manager, 'ws-2', '/workspaces/ws-2/runtime/ws/terminal');
    apiFor(manager).ensureConnected();

    resolvers.get('ws-1')?.('grant-for-ws-1');
    await flushPromiseChain();
    expect(FakeWebSocket.instances).toHaveLength(0);

    resolvers.get('ws-2')?.('grant-for-ws-2');
    await flushPromiseChain();

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain('workspace_id=ws-2');
  });

  it('keeps the bearer out of the URL and sends it through WebSocket protocols', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', '/workspaces/ws-1/runtime/ws/terminal');

    apiFor(manager).ensureConnected();

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe(
      `ws://${window.location.host}/workspaces/ws-1/runtime/ws/terminal?workspace_id=ws-1`,
    );
    expect(FakeWebSocket.instances[0].url).not.toContain('signed-grant');
    expect(FakeWebSocket.instances[0].protocols).toEqual([
      'aileron-terminal-v1',
      'bearer.c2lnbmVkLWdyYW50',
    ]);
  });

  it('fails closed without a bearer instead of opening an unauthenticated socket', () => {
    vi.mocked(executionGrantBroker.getGrant).mockImplementationOnce(() => {
      throw new Error('grant unavailable');
    });
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', '/workspaces/ws-1/runtime/ws/terminal');

    apiFor(manager).ensureConnected();

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(apiFor(manager).getSnapshot().status).toBe('error');
  });

  it('queues createTab until the terminal socket is open and synced', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).createTab({
      workingDirectory: '/workspace/app',
      size: { cols: 100, rows: 40 },
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].sent).toEqual([]);

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    expect(FakeWebSocket.instances[0].sent).toContainEqual(JSON.stringify({
      type: 'create_tab',
      data: {
        create_mode: 'always',
        working_directory: '/workspace/app',
        cols: 100,
        rows: 40,
      },
    }));
  });

  it('preserves a queued create when the same workspace receives its terminal URL', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', null);

    apiFor(manager).createTab({
      workingDirectory: '/workspace/app',
      size: { cols: 100, rows: 40 },
    });

    expect(FakeWebSocket.instances).toHaveLength(0);

    activateScope(manager);

    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.instances[0];
    socket.open();

    expect(socket.sent.some((message) => JSON.parse(message).type === 'create_tab')).toBe(false);

    socket.message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    expect(socket.sent).toContainEqual(JSON.stringify({
      type: 'create_tab',
      data: {
        create_mode: 'always',
        working_directory: '/workspace/app',
        cols: 100,
        rows: 40,
      },
    }));
  });

  it('fails closed when actions target a scope that does not own the open socket', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', '/workspaces/ws-1/runtime/ws/terminal');
    const oldApi = apiFor(manager);

    oldApi.ensureConnected();
    const oldSocket = FakeWebSocket.instances[0];
    oldSocket.open();
    oldSocket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    oldSocket.sent.length = 0;

    const nextBinding = manager.declareScope(
      'ws-2',
      '/workspaces/ws-2/runtime/ws/terminal',
    );
    const nextApi = nextBinding.api;
    nextApi.ensureConnected();
    nextApi.createTab({
      workingDirectory: '/workspace/new',
      size: { cols: 120, rows: 40 },
    });
    nextApi.sendInput('tab-1', 'new-workspace-input');
    nextApi.sendResize('tab-1', 120, 40);
    nextApi.switchTab('tab-1');
    nextApi.closeTab('tab-1');
    nextApi.clearTerminal('tab-1');

    expect(oldSocket.sent).toEqual([]);
    expect(oldApi.getSnapshot().tabs).toHaveLength(1);

    activateBinding(manager, nextBinding);
    const nextSocket = FakeWebSocket.instances[1];
    nextSocket.open();
    nextSocket.message({ type: 'tab_list', data: { tabs: [] } });

    const nextMessages = nextSocket.sent.map((message) => JSON.parse(message));
    expect(nextMessages.filter((message) => message.type === 'create_tab')).toHaveLength(1);
    expect(nextMessages.some((message) => message.type === 'input')).toBe(false);
    expect(nextMessages.some((message) => message.type === 'resize')).toBe(false);
  });

  it('does not revive delayed create requests from an old scope after returning to it', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    const oldApi = activateScope(manager, 'ws-1', '/workspaces/ws-1/runtime/ws/terminal');

    oldApi.ensureConnected();
    const oldSocket = FakeWebSocket.instances[0];
    oldSocket.open();
    oldSocket.message({ type: 'tab_list', data: { tabs: [tabMetadata] } });
    oldSocket.sent.length = 0;

    window.setTimeout(() => {
      oldApi.createTab({
        workingDirectory: '/workspace/old',
        size: { cols: 90, rows: 30 },
      });
      oldApi.ensureDefaultTab('/workspace/old', { cols: 90, rows: 30 });
    }, 120);

    const workspaceTwoApi = activateScope(
      manager,
      'ws-2',
      '/workspaces/ws-2/runtime/ws/terminal',
    );
    workspaceTwoApi.ensureConnected();
    vi.advanceTimersByTime(120);

    expect(oldSocket.sent).toEqual([]);

    const returnedWorkspaceApi = activateScope(
      manager,
      'ws-1',
      '/workspaces/ws-1/runtime/ws/terminal',
    );
    returnedWorkspaceApi.ensureConnected();

    const returnedSocket = FakeWebSocket.instances[2];
    returnedSocket.open();
    returnedSocket.message({ type: 'tab_list', data: { tabs: [] } });

    const returnedCreateMessages = returnedSocket.sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(returnedCreateMessages).toEqual([]);
  });

  it('discards a queued create when the workspace changes', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager, 'ws-1', null);

    apiFor(manager).createTab({
      workingDirectory: '/workspace/old',
      size: { cols: 90, rows: 30 },
    });
    activateScope(manager, 'ws-2');
    apiFor(manager).ensureConnected();

    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.instances[0];
    socket.open();
    socket.message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    expect(socket.sent.some((message) => JSON.parse(message).type === 'create_tab')).toBe(false);
  });

  it('ensureConnected does not close an already open terminal socket', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureConnected();
    FakeWebSocket.instances[0].open();
    apiFor(manager).ensureConnected();

    expect(FakeWebSocket.instances[0].close).not.toHaveBeenCalled();
  });

  it('ignores close events from stale sockets after a forced reconnect', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureConnected();
    const firstSocket = FakeWebSocket.instances[0];
    firstSocket.open();

    manager['connect']({ force: true });
    const secondSocket = FakeWebSocket.instances[1];
    secondSocket.open();

    firstSocket.dispatchEvent(new CloseEvent('close', { code: 1006 }));

    expect(apiFor(manager).getSnapshot().status).toBe('open');
  });

  it('deduplicates default tab creation while an empty tab list is syncing', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });
    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    const createMessages = FakeWebSocket.instances[0].sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(createMessages).toHaveLength(1);
    expect(JSON.parse(createMessages[0]).data.create_mode).toBe('default_if_empty');
  });

  it('does not create a duplicate default tab after the default create was sent but tab_created has not arrived', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });

    const createMessages = FakeWebSocket.instances[0].sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(createMessages).toHaveLength(1);
  });

  it('clears a pending default tab when the synced tab list already has tabs', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: {
        tabs: [{ ...tabMetadata, tab_id: 'server-tab' }],
      },
    });

    apiFor(manager).createTab({
      workingDirectory: '/workspace/app',
      size: { cols: 80, rows: 24 },
    });

    const createMessages = FakeWebSocket.instances[0].sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(createMessages).toHaveLength(1);
    expect(JSON.parse(createMessages[0]).data.working_directory).toBe('/workspace/app');
    expect(JSON.parse(createMessages[0]).data).not.toHaveProperty('name');
    expect(JSON.parse(createMessages[0]).data.create_mode).toBe('always');
  });

  it('flushes queued creates in the same sync cycle after creating a default tab', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    apiFor(manager).ensureDefaultTab('/workspace/app', { cols: 80, rows: 24 });
    apiFor(manager).createTab({
      workingDirectory: '/workspace/app',
      size: { cols: 80, rows: 24 },
    });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    const createMessages = FakeWebSocket.instances[0].sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(createMessages).toHaveLength(2);
    expect(createMessages.map((message) => JSON.parse(message).data.create_mode)).toEqual([
      'default_if_empty',
      'always',
    ]);
  });

  it('does not flush queued creates beyond the terminal tab limit', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    activateScope(manager);

    for (let index = 0; index < 12; index += 1) {
      apiFor(manager).createTab({
        workingDirectory: '/workspace',
        size: { cols: 80, rows: 24 },
      });
    }

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_list',
      data: { tabs: [] },
    });

    const createMessages = FakeWebSocket.instances[0].sent.filter((message) => (
      JSON.parse(message).type === 'create_tab'
    ));
    expect(createMessages.length).toBeLessThanOrEqual(TERMINAL_MAX_TABS);
  });

  it('notifies terminal instance disposal when a tab is closed by the server', () => {
    const onTabClosed = vi.fn();
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry(), undefined, {
      onTabClosed,
    });
    activateScope(manager);

    apiFor(manager).ensureConnected();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].message({
      type: 'tab_closed',
      tab_id: 'tab-1',
    });

    expect(onTabClosed).toHaveBeenCalledWith('tab-1');
  });

  it('notifies terminal instance disposal when a tab is closed locally', () => {
    const onTabClosed = vi.fn();
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry(), undefined, {
      onTabClosed,
    });
    activateScope(manager);

    apiFor(manager).closeTab('tab-1');

    expect(onTabClosed).toHaveBeenCalledWith('tab-1');
  });

  it('does not notify tab disposal twice when local close is followed by server tab_closed', () => {
    const onTabClosed = vi.fn();
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry(), undefined, {
      onTabClosed,
    });
    activateScope(manager);

    apiFor(manager).ensureConnected();
    FakeWebSocket.instances[0].open();
    apiFor(manager).closeTab('tab-1');
    FakeWebSocket.instances[0].message({
      type: 'tab_closed',
      tab_id: 'tab-1',
    });

    expect(onTabClosed).toHaveBeenCalledTimes(1);
    expect(onTabClosed).toHaveBeenCalledWith('tab-1');
  });
});
