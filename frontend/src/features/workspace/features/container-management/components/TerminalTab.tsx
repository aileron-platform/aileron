/**
 * TerminalTab - Single terminal tab component
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { Terminal as XTerm } from '@xterm/xterm';
import type { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { createLogger } from '@/shared/services/logger';
import { activateTerminalRenderer, getOrCreateTerminalEntry } from '../../../realtime/terminalInstanceRegistry';
import type { TerminalResolvedTheme } from '../../../realtime/terminalInstanceRegistry';

const logger = createLogger('TerminalTab');

interface TerminalTabProps {
  tabId: string;
  isActive: boolean;
  isVisible?: boolean;
  style?: React.CSSProperties;
  className?: string;
  onInput: (tabId: string, data: string) => void;
  onResize: (tabId: string, cols: number, rows: number) => void;
  onSelectionChange?: (text: string) => void;
  onTerminalResize?: (cols: number, rows: number) => void;
  onContextMenu?: (event: React.MouseEvent) => void;
  attachXterm: (tabId: string, terminal: XTerm) => () => void;
  terminalTheme?: TerminalResolvedTheme;
}

type DocumentWithFonts = Document & { fonts?: Document['fonts'] };

export const TerminalTab: React.FC<TerminalTabProps> = ({
  tabId,
  isActive,
  isVisible = true,
  style,
  className,
  onInput,
  onResize,
  onSelectionChange,
  onTerminalResize,
  onContextMenu,
  attachXterm,
  terminalTheme = 'dark',
}) => {
  const [hostElement, setHostElement] = useState<HTMLDivElement | null>(null);
  const terminalInstanceRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const rafFitRef = useRef<number | null>(null);
  const lastSentSizeRef = useRef({ cols: 0, rows: 0 });
  const resizeTimeoutRef = useRef<number | null>(null);
  const onTerminalResizeRef = useRef(onTerminalResize);

  useEffect(() => {
    onTerminalResizeRef.current = onTerminalResize;
  }, [onTerminalResize]);

  const setHostRef = useCallback((node: HTMLDivElement | null) => {
    setHostElement(node);
  }, []);

  const performFit = useCallback(() => {
    // Cancel pending fit work before scheduling the next resize pass.
    if (resizeTimeoutRef.current !== null) {
      clearTimeout(resizeTimeoutRef.current);
    }
    if (rafFitRef.current !== null) {
      cancelAnimationFrame(rafFitRef.current);
    }

    // Debounce resize bursts to avoid sending excessive PTY resize events.
    resizeTimeoutRef.current = window.setTimeout(() => {
      rafFitRef.current = requestAnimationFrame(() => {
        const fitAddon = fitAddonRef.current;
        const terminal = terminalInstanceRef.current;
        if (!fitAddon || !terminal) return;

        // Skip fitting hidden terminals because xterm cannot measure them reliably.
        if (hostElement && hostElement.offsetParent === null) {
          return;
        }

        try {
          fitAddon.fit();
          const { cols, rows } = terminal;
          terminal.refresh(0, Math.max(rows - 1, 0));
          const lastSize = lastSentSizeRef.current;
          if (lastSize.cols !== cols || lastSize.rows !== rows) {
            onResize(tabId, cols, rows);
            lastSentSizeRef.current = { cols, rows };
            // Notify the parent so the status bar stays in sync.
            if (onTerminalResizeRef.current) {
              onTerminalResizeRef.current(cols, rows);
            }
          }
        } catch (error) {
          logger.debug('Terminal fit failed', { error });
        }
        rafFitRef.current = null;
      });
      resizeTimeoutRef.current = null;
    }, 100);
  }, [tabId, onResize, hostElement]);

  // Initialize or reattach the terminal instance for this tab.
  useEffect(() => {
    if (!hostElement) return;

    const entry = getOrCreateTerminalEntry(tabId, terminalTheme);
    const { terminal, fitAddon } = entry;
    const terminalElement = terminal.element;
    if (terminalElement) {
      hostElement.appendChild(terminalElement);
    } else {
      terminal.open(hostElement);
    }
    activateTerminalRenderer(tabId);
    terminal.attachCustomKeyEventHandler((event) => {
      if (event.type === 'keydown' && event.key === 'Enter' && event.shiftKey) {
        event.preventDefault();
        onInput(tabId, '\n');
        return false;
      }
      return true;
    });

    terminalInstanceRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Wait for fonts before fitting so character dimensions are stable.
    const doc = document as DocumentWithFonts;
    if (doc.fonts && doc.fonts.ready) {
      doc.fonts.ready.then(() => {
        performFit();
      }).catch((error) => {
        logger.debug('Font loading failed', { error });
        performFit();
      });
    } else {
      performFit();
    }

    // Forward terminal input to the remote PTY.
    const dataDisposable = terminal.onData((data) => {
      onInput(tabId, data);
    });

    // Track selection for copy actions.
    const selectionDisposable = terminal.onSelectionChange(() => {
      if (onSelectionChange) {
        onSelectionChange(terminal.getSelection() ?? '');
      }
    });

    // Register with the realtime manager so PTY output is written directly
    // to this xterm instance. Registration outlives this component: the
    // manager keeps writing to the persisted instance in
    // terminalInstanceRegistry even while unmounted, so there is nothing to
    // detach on cleanup below.
    attachXterm(tabId, terminal);

    // Observe container size changes.
    const resizeObserver = new ResizeObserver(() => {
      performFit();
    });
    resizeObserver.observe(hostElement);
    resizeObserverRef.current = resizeObserver;

    return () => {
      if (resizeTimeoutRef.current !== null) {
        clearTimeout(resizeTimeoutRef.current);
      }
      if (rafFitRef.current !== null) {
        cancelAnimationFrame(rafFitRef.current);
      }
      resizeObserver.disconnect();
      dataDisposable.dispose();
      selectionDisposable.dispose();
      terminalInstanceRef.current = null;
      fitAddonRef.current = null;
    };
  }, [hostElement, tabId, terminalTheme, onInput, onSelectionChange, attachXterm, performFit]);

  // Refit when visibility changes.
  useEffect(() => {
    if (isVisible) {
      performFit();
    }
  }, [isVisible, performFit]);

  return (
    <div
      ref={setHostRef}
      className={`h-full w-full ${isVisible ? 'block' : 'hidden'} ${className || ''}`}
      style={{ minHeight: 0, ...style }}
      onContextMenu={onContextMenu}
    />
  );
};
