import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon } from '@xterm/addon-search';
import { Unicode11Addon } from '@xterm/addon-unicode11';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { WebglAddon } from '@xterm/addon-webgl';
import { Terminal as XTerm } from '@xterm/xterm';
import type { ITheme } from '@xterm/xterm';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TerminalInstanceRegistry');

export type TerminalResolvedTheme = 'light' | 'dark';

const TERMINAL_THEMES: Record<TerminalResolvedTheme, ITheme> = {
  dark: {
    background: '#0f172a',
    foreground: '#f8fafc',
    cursor: '#22d3ee',
  },
  light: {
    background: '#ffffff',
    foreground: '#111827',
    cursor: '#2563eb',
    selectionBackground: '#bfdbfe',
  },
};

export interface TerminalRegistryEntry {
  terminal: XTerm;
  fitAddon: FitAddon;
  webglAddon?: WebglAddon;
}

const terminalRegistry = new Map<string, TerminalRegistryEntry>();

const applyTerminalThemeToEntry = (
  entry: TerminalRegistryEntry,
  theme: TerminalResolvedTheme,
) => {
  entry.terminal.options.theme = TERMINAL_THEMES[theme];
  entry.terminal.refresh(0, Math.max(entry.terminal.rows - 1, 0));
};

const TERMINAL_FONT_FAMILY =
  'Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", ' +
  '"Noto Sans Mono CJK TC", "PingFang TC", "Microsoft JhengHei", monospace';

const createTerminalEntry = (theme: TerminalResolvedTheme): TerminalRegistryEntry => {
  const terminal = new XTerm({
    allowProposedApi: true,
    cursorBlink: true,
    bracketedPasteMode: true,
    fontFamily: TERMINAL_FONT_FAMILY,
    fontSize: 13,
    scrollback: 1000,
    theme: TERMINAL_THEMES[theme],
  });

  const fitAddon = new FitAddon();
  const webLinksAddon = new WebLinksAddon();
  const searchAddon = new SearchAddon();
  const unicode11Addon = new Unicode11Addon();

  terminal.loadAddon(fitAddon);
  terminal.loadAddon(webLinksAddon);
  terminal.loadAddon(searchAddon);
  terminal.loadAddon(unicode11Addon);
  terminal.unicode.activeVersion = '11';

  return { terminal, fitAddon };
};

// WebGL renderer must load after terminal.open(); DOM renderer is the fallback on context loss.
export const activateTerminalRenderer = (tabId: string) => {
  const entry = terminalRegistry.get(tabId);
  if (!entry || entry.webglAddon || !entry.terminal.element) {
    return;
  }

  try {
    const webglAddon = new WebglAddon();
    webglAddon.onContextLoss(() => {
      webglAddon.dispose();
      const current = terminalRegistry.get(tabId);
      if (current && current.webglAddon === webglAddon) {
        current.webglAddon = undefined;
      }
    });
    entry.terminal.loadAddon(webglAddon);
    entry.webglAddon = webglAddon;
  } catch (error) {
    logger.debug('WebGL renderer unavailable, using DOM renderer', { error });
  }
};

export const getOrCreateTerminalEntry = (
  tabId: string,
  theme: TerminalResolvedTheme = 'dark',
): TerminalRegistryEntry => {
  let entry = terminalRegistry.get(tabId);
  if (!entry) {
    entry = createTerminalEntry(theme);
    terminalRegistry.set(tabId, entry);
  } else {
    applyTerminalThemeToEntry(entry, theme);
  }
  return entry;
};

export const disposeTerminalInstance = (tabId: string) => {
  const entry = terminalRegistry.get(tabId);
  if (!entry) return;
  entry.webglAddon?.dispose();
  entry.terminal.dispose();
  terminalRegistry.delete(tabId);
};

export const disposeAllTerminalInstances = () => {
  terminalRegistry.forEach((entry) => {
    entry.webglAddon?.dispose();
    entry.terminal.dispose();
  });
  terminalRegistry.clear();
};
