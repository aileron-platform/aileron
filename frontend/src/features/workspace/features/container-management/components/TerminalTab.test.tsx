import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TerminalTab, disposeAllTerminalInstances } from './TerminalTab';

const terminalInstances = vi.hoisted(() => [] as Array<{
  dispose: ReturnType<typeof vi.fn>;
  element?: HTMLDivElement;
  keyHandler?: (event: KeyboardEvent) => boolean;
  open: ReturnType<typeof vi.fn>;
  options?: Record<string, unknown>;
}>);

vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 80;
    rows = 24;
    element?: HTMLDivElement;
    keyHandler?: (event: KeyboardEvent) => boolean;

    constructor(options?: Record<string, unknown>) {
      this.options = options;
      terminalInstances.push(this);
    }

    loadAddon = vi.fn();
    open = vi.fn((host: HTMLElement) => {
      this.element = document.createElement('div');
      host.appendChild(this.element);
    });
    refresh = vi.fn();
    dispose = vi.fn();
    getSelection = vi.fn(() => '');
    onData = vi.fn(() => ({ dispose: vi.fn() }));
    onSelectionChange = vi.fn(() => ({ dispose: vi.fn() }));
    attachCustomKeyEventHandler = vi.fn((handler: (event: KeyboardEvent) => boolean) => {
      this.keyHandler = handler;
    });
  },
}));

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class {
    fit = vi.fn();
  },
}));

vi.mock('@xterm/addon-web-links', () => ({
  WebLinksAddon: class {},
}));

vi.mock('@xterm/addon-search', () => ({
  SearchAddon: class {},
}));

describe('TerminalTab', () => {
  beforeEach(() => {
    terminalInstances.length = 0;
    disposeAllTerminalInstances();
  });

  it('maps Shift+Enter to LF so terminal TUIs can insert a newline', async () => {
    const onInput = vi.fn();

    render(
      <TerminalTab
        tabId="tab-1"
        isActive
        onInput={onInput}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );

    await waitFor(() => {
      expect(terminalInstances[0]?.keyHandler).toBeTypeOf('function');
    });

    const event = new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true });
    const preventDefault = vi.spyOn(event, 'preventDefault');

    const shouldContinue = terminalInstances[0].keyHandler?.(event);

    expect(shouldContinue).toBe(false);
    expect(preventDefault).toHaveBeenCalled();
    expect(onInput).toHaveBeenCalledWith('tab-1', '\n');
  });

  it('enables bracketed paste mode in xterm', async () => {
    render(
      <TerminalTab
        tabId="tab-1"
        isActive
        onInput={vi.fn()}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );

    await waitFor(() => {
      expect(terminalInstances[0]?.options).toMatchObject({
        bracketedPasteMode: true,
      });
    });
  });

  it('does not intercept regular Enter', async () => {
    const onInput = vi.fn();

    render(
      <TerminalTab
        tabId="tab-1"
        isActive
        onInput={onInput}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );

    await waitFor(() => {
      expect(terminalInstances[0]?.keyHandler).toBeTypeOf('function');
    });

    const event = new KeyboardEvent('keydown', { key: 'Enter' });
    const shouldContinue = terminalInstances[0].keyHandler?.(event);

    expect(shouldContinue).toBe(true);
    expect(onInput).not.toHaveBeenCalled();
  });

  it('reattaches the existing xterm instance for the same tab id after remount', async () => {
    const props = {
      tabId: 'tab-1',
      isActive: true,
      onInput: vi.fn(),
      onResize: vi.fn(),
      attachXterm: vi.fn(() => vi.fn()),
    };

    const { unmount } = render(<TerminalTab {...props} />);

    await waitFor(() => {
      expect(terminalInstances).toHaveLength(1);
    });

    unmount();
    render(<TerminalTab {...props} />);

    await waitFor(() => {
      expect(terminalInstances).toHaveLength(1);
      expect(terminalInstances[0].open).toHaveBeenCalledTimes(1);
      expect(terminalInstances[0].dispose).not.toHaveBeenCalled();
    });
  });
});
