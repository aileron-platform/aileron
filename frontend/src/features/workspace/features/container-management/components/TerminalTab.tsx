/**
 * TerminalTab - 單個 Terminal Tab 組件
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { WebglAddon } from '@xterm/addon-webgl';
import { SearchAddon } from '@xterm/addon-search';
import '@xterm/xterm/css/xterm.css';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TerminalTab');

interface TerminalTabProps {
  tabId: string;
  isActive: boolean; // Keep for backward compatibility or use as "focused"
  isVisible?: boolean; // New prop for visibility
  style?: React.CSSProperties; // New prop for grid positioning
  className?: string; // New prop for custom classes
  onInput: (tabId: string, data: string) => void;
  onResize: (tabId: string, cols: number, rows: number) => void;
  onSelectionChange?: (text: string) => void;
  onTerminalResize?: (cols: number, rows: number) => void;
  onContextMenu?: (event: React.MouseEvent) => void;
  attachXterm: (tabId: string, terminal: XTerm) => () => void;
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
}) => {
  const [hostElement, setHostElement] = useState<HTMLDivElement | null>(null);
  const terminalInstanceRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const detachTerminalRef = useRef<(() => void) | null>(null);
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
    // 清除之前的 timeout 和 animation frame
    if (resizeTimeoutRef.current !== null) {
      clearTimeout(resizeTimeoutRef.current);
    }
    if (rafFitRef.current !== null) {
      cancelAnimationFrame(rafFitRef.current);
    }

    // 使用 timeout 防抖，避免短時間內多次 resize
    resizeTimeoutRef.current = window.setTimeout(() => {
      rafFitRef.current = requestAnimationFrame(() => {
        const fitAddon = fitAddonRef.current;
        const terminal = terminalInstanceRef.current;
        if (!fitAddon || !terminal) return;

        // 如果不可見，不執行 fit，避免錯誤
        if (hostElement && hostElement.offsetParent === null) {
          return;
        }

        try {
          fitAddon.fit();
          const { cols, rows } = terminal;
          const lastSize = lastSentSizeRef.current;
          if (lastSize.cols !== cols || lastSize.rows !== rows) {
            onResize(tabId, cols, rows);
            lastSentSizeRef.current = { cols, rows };
            // 通知父組件更新狀態列
            if (onTerminalResizeRef.current) {
              onTerminalResizeRef.current(cols, rows);
            }
          }
        } catch (error) {
          logger.debug('Terminal fit 失敗', { error });
        }
        rafFitRef.current = null;
      });
      resizeTimeoutRef.current = null;
    }, 100); // 100ms 防抖延遲
  }, [tabId, onResize, hostElement]);

  // 初始化 terminal
  useEffect(() => {
    if (!hostElement) return;

    const terminal = new XTerm({
      allowProposedApi: true,
      cursorBlink: true,
      fontFamily:
        'Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      fontSize: 13,
      scrollback: 1000,
      convertEol: true,
      theme: {
        background: '#0f172a',
        foreground: '#f8fafc',
        cursor: '#22d3ee',
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    const searchAddon = new SearchAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);
    terminal.loadAddon(searchAddon);

    // 嘗試載入 WebGL 加速
    try {
      const webglAddon = new WebglAddon();
      terminal.loadAddon(webglAddon);
    } catch (error) {
      logger.debug('WebGL 加速不可用，使用回退模式', { error });
    }

    terminal.open(hostElement);

    terminalInstanceRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // 等待字體載入後再 fit
    const doc = document as DocumentWithFonts;
    if (doc.fonts && doc.fonts.ready) {
      doc.fonts.ready.then(() => {
        performFit();
      }).catch((error) => {
        logger.debug('字體載入失敗', { error });
        performFit();
      });
    } else {
      performFit();
    }

    // 監聽輸入
    const dataDisposable = terminal.onData((data) => {
      onInput(tabId, data);
    });

    // 監聽選取變化
    const selectionDisposable = terminal.onSelectionChange(() => {
      if (onSelectionChange) {
        onSelectionChange(terminal.getSelection() ?? '');
      }
    });

    // 附加到 realtime manager
    const detach = attachXterm(tabId, terminal);
    detachTerminalRef.current = detach;

    // 監聽容器大小變化
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
      if (detachTerminalRef.current) {
        detachTerminalRef.current();
      }
      terminal.dispose();
    };
  }, [hostElement, tabId, onInput, onSelectionChange, attachXterm, performFit]);

  // 當可見性改變時，重新 fit
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

