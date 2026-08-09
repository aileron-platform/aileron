import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TerminalTab } from './TerminalTab';
import {
  disposeAllTerminalInstances,
  disposeTerminalInstance,
} from '../../../realtime/terminalInstanceRegistry';

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
    unicode = { activeVersion: '6' };

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

vi.mock('@xterm/addon-unicode11', () => ({
  Unicode11Addon: class {},
}));

vi.mock('@xterm/addon-webgl', () => ({
  WebglAddon: class {
    onContextLoss = vi.fn();
    dispose = vi.fn();
  },
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

  it('uses the requested light terminal theme when creating xterm', async () => {
    render(
      <TerminalTab
        tabId="tab-1"
        isActive
        terminalTheme="light"
        onInput={vi.fn()}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );

    await waitFor(() => {
      expect(terminalInstances[0]?.options).toMatchObject({
        theme: {
          background: '#ffffff',
          foreground: '#111827',
        },
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

  it('keeps the realtime attachment registered on unmount so output keeps flowing while unmounted', async () => {
    const detach = vi.fn();
    const attachXterm = vi.fn(() => detach);
    const { unmount } = render(
      <TerminalTab
        tabId="tab-1"
        isActive
        onInput={vi.fn()}
        onResize={vi.fn()}
        attachXterm={attachXterm}
      />,
    );

    await waitFor(() => {
      expect(attachXterm).toHaveBeenCalledTimes(1);
    });

    unmount();

    // Attachment lifetime is the tab's lifetime, not the component's: the
    // manager keeps writing to the persisted xterm instance while
    // unmounted, so cleanup must not call the (now vestigial) detach
    // function or dispose the xterm instance.
    expect(detach).not.toHaveBeenCalled();
    expect(terminalInstances[0].dispose).not.toHaveBeenCalled();
  });

  it('disposes only the requested terminal tab instance', async () => {
    render(
      <TerminalTab
        tabId="tab-1"
        isActive
        onInput={vi.fn()}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );
    render(
      <TerminalTab
        tabId="tab-2"
        isActive
        onInput={vi.fn()}
        onResize={vi.fn()}
        attachXterm={vi.fn(() => vi.fn())}
      />,
    );

    await waitFor(() => {
      expect(terminalInstances).toHaveLength(2);
    });

    disposeTerminalInstance('tab-1');

    expect(terminalInstances[0].dispose).toHaveBeenCalledTimes(1);
    expect(terminalInstances[1].dispose).not.toHaveBeenCalled();
  });
});
