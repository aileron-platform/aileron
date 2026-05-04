import type { Terminal } from '@xterm/xterm';
import { describe, expect, it, vi } from 'vitest';
import { WebSocketConnectionRegistry } from './core/websocketRegistry';
import { TerminalRealtimeManager } from './terminalRealtimeManager';

const tabMetadata = {
  tab_id: 'tab-1',
  session_id: 'session-1',
  name: 'Terminal 1',
  workspace_path: '/workspace',
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

describe('TerminalRealtimeManager', () => {
  it('does not replay existing history when reattaching the same xterm instance', () => {
    const manager = new TerminalRealtimeManager(new WebSocketConnectionRegistry());
    const store = manager.api.getSnapshot;
    const terminal = createTerminal() as unknown as Terminal;

    manager['store'].applyTabList([tabMetadata]);
    manager['store'].appendOutput('tab-1', '\x1b[c', 1);
    manager['store'].appendOutput('tab-1', 'ready', 2);

    const firstDetach = manager.api.attachXterm('tab-1', terminal);
    expect((terminal.write as unknown as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(2);
    firstDetach();

    const secondDetach = manager.api.attachXterm('tab-1', terminal);
    expect((terminal.write as unknown as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(2);

    manager['store'].appendOutput('tab-1', ' after-reattach', 3);

    expect((terminal.write as unknown as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(3);
    expect(store().tabs[0].history).toHaveLength(3);
    secondDetach();
  });
});
