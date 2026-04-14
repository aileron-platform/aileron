
import { createTerminalStore } from './terminalStore';
import type { TerminalStore } from './terminalStore';
import { WebSocketConnectionRegistry, ManagedSocketStatus } from './core/websocketRegistry';
import type { WebSocketType } from './core/websocketRegistry';
import type { Terminal } from '@xterm/xterm';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('TerminalRealtimeManager');

interface ConnectOptions {
  force?: boolean;
}

const TERMINAL_SOCKET_TYPE: WebSocketType = 'terminal';

const RECONNECT_BASE_DELAY = 2_000;
const QUICK_RECONNECT_DELAY = 250;
const CONNECTION_TIMEOUT = 10_000;

export interface TerminalRealtimeAPI {
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => ReturnType<TerminalStore['getSnapshot']>;
  connect: (options?: ConnectOptions) => void;
  disconnect: (options?: { allowReconnect?: boolean }) => void;
  createTab: (name: string, workspacePath?: string) => void;
  closeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  renameTab: (tabId: string, name: string) => void;
  sendInput: (tabId: string, data: string) => void;
  sendResize: (tabId: string, cols: number, rows: number) => void;
  attachXterm: (tabId: string, terminal: Terminal) => () => void;
  clearHistory: (tabId: string) => void;
}

export class TerminalRealtimeManager {
  private store: TerminalStore;

  private registry: WebSocketConnectionRegistry;

  private workspaceId: string | null = null;

  private terminalUrl: string | null = null;

  private connectionTimer: number | null = null;

  private reconnectTimer: number | null = null;

  private shouldReconnect = false;

  private attachments = new Map<string, Map<Terminal, { unsubscribe: () => void; offset: number }>>();

  private apiCache: TerminalRealtimeAPI | null = null;

  private translate: (key: string) => string;

  private getToken: () => string | null;

  constructor(
    registry: WebSocketConnectionRegistry,
    translate?: (key: string) => string,
    getToken?: () => string | null
  ) {
    this.registry = registry;
    this.store = createTerminalStore();
    // Provide fallback translations if translate function not provided
    this.translate = translate || ((key: string) => {
      const fallbacks: Record<string, string> = {
        'common.messages.terminalConnectionFailed': '終端連線網址建立失敗',
        'common.messages.terminalError': '終端連線發生錯誤',
      };
      return fallbacks[key] || key;
    });
    // Provide fallback token getter if not provided
    this.getToken = getToken || (() => {
      try {
        const stored = window.sessionStorage.getItem('oidc_tokens');
        if (stored) {
          const parsed = JSON.parse(stored) as { access_token?: string };
          return parsed.access_token || null;
        }
      } catch (error) {
        logger.warn(' Failed to get token from sessionStorage', error);
      }
      return null;
    });
  }

  get api(): TerminalRealtimeAPI {
    if (!this.apiCache) {
      this.apiCache = {
        subscribe: this.subscribe,
        getSnapshot: this.store.getSnapshot,
        connect: this.connect,
        disconnect: this.disconnect,
        createTab: this.createTab,
        closeTab: this.closeTab,
        switchTab: this.switchTab,
        renameTab: this.renameTab,
        sendInput: this.sendInput,
        sendResize: this.sendResize,
        attachXterm: this.attachXterm,
        clearHistory: this.clearHistory,
      };
    }
    return this.apiCache;
  }

  updateWorkspace(workspaceId: string | null, terminalUrl: string | null) {
    logger.debug(' updateWorkspace called', {
      oldWorkspaceId: this.workspaceId,
      newWorkspaceId: workspaceId,
      oldTerminalUrl: this.terminalUrl,
      newTerminalUrl: terminalUrl,
    });

    const hasChanged =
      this.workspaceId !== workspaceId || this.terminalUrl !== terminalUrl;
    if (!hasChanged) {
      logger.debug(' No change detected, skipping update');
      return;
    }

    logger.debug(' Workspace changed, updating...');
    this.workspaceId = workspaceId;
    this.terminalUrl = terminalUrl;
    this.shouldReconnect = false;
    this.clearTimers();
    this.registry.close(TERMINAL_SOCKET_TYPE);
    this.store.reset();
  }

  dispose() {
    this.shouldReconnect = false;
    this.clearTimers();
    this.registry.close(TERMINAL_SOCKET_TYPE);
    this.attachments.forEach((terminalMap) => {
      terminalMap.forEach(({ unsubscribe }, terminal) => {
        try {
          unsubscribe();
          terminal.dispose?.();
        } catch (error) {
          logger.debug('清理終端附件時發生錯誤', { error });
        }
      });
    });
    this.attachments.clear();
    this.store.reset();
  }

  private subscribe = (listener: () => void) => {
    return this.store.subscribe(listener);
  };

  private connect = (options: ConnectOptions = {}) => {
    logger.debug(' connect called', {
      workspaceId: this.workspaceId,
      terminalUrl: this.terminalUrl,
      options,
    });

    const { force = false } = options;
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;

    if (!this.workspaceId || !this.terminalUrl) {
      logger.error(' Missing workspaceId or terminalUrl');
      this.store.setStatus('error', 'Terminal URL 尚未就緒');
      return;
    }

    if (
      !force &&
      socket &&
      (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
    ) {
      logger.debug(' Already connected or connecting, skipping');
      return;
    }

    if (socket) {
      try {
        socket.close();
      } catch (error) {
        logger.error('關閉既有終端連線失敗', { error });
      }
    }

    const url = this.buildWebSocketUrl();
    logger.debug(' Built WebSocket URL', { url });
    if (!url) {
      logger.error(' Failed to build WebSocket URL');
      this.store.setStatus('error', this.translate('common.messages.terminalConnectionFailed'));
      return;
    }

    this.shouldReconnect = true;
    this.store.setStatus('connecting');

    logger.debug(' Creating WebSocket connection to:', url);
    const nextSocket = new WebSocket(url);
    logger.debug(' WebSocket created, readyState:', nextSocket.readyState);
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, nextSocket, 'connecting');

    this.connectionTimer = window.setTimeout(() => {
      if (nextSocket.readyState === WebSocket.CONNECTING) {
        try {
          nextSocket.close();
        } catch (error) {
          logger.error('終端連線逾時計時器關閉失敗', { error });
        }
      }
    }, CONNECTION_TIMEOUT);

    nextSocket.addEventListener('open', this.handleOpen);
    nextSocket.addEventListener('message', this.handleMessage);
    nextSocket.addEventListener('close', this.handleClose);
    nextSocket.addEventListener('error', this.handleError);
  };

  private disconnect = ({ allowReconnect = true } = {}) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    this.shouldReconnect = allowReconnect;
    this.clearTimers();
    if (managed.socket) {
      try {
        managed.socket.close();
      } catch (error) {
        logger.error('關閉終端 WebSocket 失敗', { error });
      }
    }
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, null, 'closed');
    if (!allowReconnect) {
      this.store.setStatus('closed');
    }
  };

  private createTab = (name: string, workspacePath?: string) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'create_tab',
          data: {
            name,
            workspace_path: workspacePath || '/workspace',
            cols: 80,
            rows: 24,
          },
        }),
      );
    }
  };

  private closeTab = (tabId: string) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'close_tab',
          tab_id: tabId,
        }),
      );
    }
    this.store.closeTab(tabId);
    this.attachments.delete(tabId);
  };

  private switchTab = (tabId: string) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'switch_tab',
          tab_id: tabId,
        }),
      );
    }
    this.store.switchTab(tabId);
  };

  private renameTab = (tabId: string, name: string) => {
    this.store.renameTab(tabId, name);
  };

  private sendInput = (tabId: string, data: string) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'input',
          tab_id: tabId,
          data: {
            data,
          },
        }),
      );
    }
  };

  private sendResize = (tabId: string, cols: number, rows: number) => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'resize',
          tab_id: tabId,
          data: {
            cols,
            rows,
          },
        }),
      );
    }
  };

  private attachXterm = (tabId: string, terminal: Terminal) => {
    const snapshot = this.store.getSnapshot();
    const tab = snapshot.tabs.find((t) => t.tabId === tabId);

    if (!tab) {
      logger.warn(`Tab ${tabId} not found`);
      return () => { };
    }

    const initialHistory = tab.history;
    initialHistory.forEach((entry) => {
      try {
        terminal.write(entry.data);
      } catch (error) {
        logger.debug('寫入既有終端歷史失敗', { error });
      }
    });

    const attachment = {
      unsubscribe: () => { },
      offset: initialHistory.length,
    };

    const unsubscribe = this.store.subscribe(() => {
      const currentSnapshot = this.store.getSnapshot();
      const currentTab = currentSnapshot.tabs.find((t) => t.tabId === tabId);

      if (!currentTab) {
        return;
      }

      const historyLength = currentTab.history.length;

      if (historyLength < attachment.offset) {
        attachment.offset = historyLength;
      }

      if (historyLength <= attachment.offset) {
        return;
      }

      const pending = currentTab.history.slice(attachment.offset);
      if (pending.length > 0) {
        const combined = pending.map((entry) => entry.data).join('');
        try {
          terminal.write(combined);
        } catch (error) {
          logger.debug('寫入終端輸出失敗', { error });
        }
        attachment.offset = historyLength;
      }
    });

    attachment.unsubscribe = unsubscribe;

    if (!this.attachments.has(tabId)) {
      this.attachments.set(tabId, new Map());
    }
    this.attachments.get(tabId)!.set(terminal, attachment);

    return () => {
      const tabAttachments = this.attachments.get(tabId);
      if (tabAttachments) {
        const detachAttachment = tabAttachments.get(terminal);
        if (detachAttachment) {
          detachAttachment.unsubscribe();
          tabAttachments.delete(terminal);
        }
      }
    };
  };

  private clearHistory = (tabId: string) => {
    this.store.clearHistory(tabId);
    const tabAttachments = this.attachments.get(tabId);
    if (tabAttachments) {
      tabAttachments.forEach((attachment, terminal) => {
        try {
          terminal.reset();
        } catch (error) {
          logger.debug('清除終端歷史失敗', { error });
        }
        attachment.offset = 0;
      });
    }
  };

  private buildWebSocketUrl(): string | null {
    if (!this.terminalUrl || !this.workspaceId) {
      return null;
    }
    try {
      const url = new URL(this.terminalUrl);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';

      // Go terminal service WebSocket 路徑
      url.pathname = '/ws/terminal';

      // 添加 token 參數
      const token = this.getToken();
      if (token) {
        url.searchParams.set('token', token);
      } else {
        logger.warn(' No token available for WebSocket connection');
      }

      return url.toString();
    } catch (error) {
      logger.error('建立終端 WebSocket URL 失敗', { error });
      return null;
    }
  }

  private handleOpen = () => {
    const managed = this.registry.get(TERMINAL_SOCKET_TYPE);
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, managed.socket, 'open');
    this.registry.resetAttempts(TERMINAL_SOCKET_TYPE);
    this.clearConnectionTimer();
    this.store.setStatus('open');
  };

  private handleMessage = (event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as
        | { type: 'connected'; data: { client_id: string; user_id: string } }
        | { type: 'tab_created'; tab_id: string; data: { session_id: string; name: string; workspace_path: string } }
        | { type: 'tab_closed'; tab_id: string }
        | { type: 'tab_switched'; tab_id: string }
        | { type: 'output'; tab_id: string; data: { data: string } }
        | { type: 'tab_list'; data: { tabs: Array<{ tab_id: string; session_id: string; name: string }> } }
        | { type: 'error'; data: { code: string; message: string }; tab_id?: string };

      switch (payload.type) {
        case 'connected':
          this.store.setClientId(payload.data.client_id);
          this.store.setStatus('open');
          break;
        case 'tab_created':
          this.store.createTab(
            payload.tab_id,
            payload.data.name,
            payload.data.session_id,
            payload.data.workspace_path
          );
          break;
        case 'tab_closed':
          this.store.closeTab(payload.tab_id);
          break;
        case 'tab_switched':
          this.store.switchTab(payload.tab_id);
          break;
        case 'output':
          this.store.appendOutput(payload.tab_id, payload.data.data);
          break;
        case 'tab_list':
          // 處理 tab 列表
          payload.data.tabs.forEach((tab) => {
            const existingTab = this.store.getSnapshot().tabs.find((t) => t.tabId === tab.tab_id);
            if (!existingTab) {
              this.store.createTab(tab.tab_id, tab.name, tab.session_id);
            }
          });
          break;
        case 'error':
          this.store.setStatus('error', payload.data.message);
          break;
        default:
          break;
      }
    } catch (error) {
      logger.error('解析終端 WebSocket 訊息失敗', { error });
    }
  };

  private handleClose = (event: CloseEvent) => {
    this.clearTimers();
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, null, 'closed');
    if (event.code === 1000) {
      this.store.setStatus('closed');
      return;
    }
    if (!this.shouldReconnect) {
      this.store.setStatus('closed');
      return;
    }
    this.store.setStatus('reconnecting');
    const delay = event.wasClean ? QUICK_RECONNECT_DELAY : RECONNECT_BASE_DELAY;
    this.registry.incrementAttempts(TERMINAL_SOCKET_TYPE);
    this.reconnectTimer = window.setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect({ force: true });
      }
    }, delay);
  };

  private handleError = (event: Event) => {
    logger.error('終端 WebSocket 發生錯誤', { event });
    this.store.setStatus('error', this.translate('common.messages.terminalError'));
  };

  private clearTimers() {
    this.clearConnectionTimer();
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearConnectionTimer() {
    if (this.connectionTimer !== null) {
      window.clearTimeout(this.connectionTimer);
      this.connectionTimer = null;
    }
  }
}
