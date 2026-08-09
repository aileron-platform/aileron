
import { createTerminalStore } from './terminalStore';
import type { TerminalStore, TerminalTabMetadata } from './terminalStore';
import {
  WebSocketConnectionRegistry,
  type ManagedSocketStatus,
} from '@/shared/realtime/webSocketConnectionRegistry';
import type { Terminal } from '@xterm/xterm';
import { createLogger } from '@/shared/services/logger';
import { TERMINAL_MAX_TABS } from './terminalPolicy';
import { createWebSocketBearerProtocols } from '@/shared/realtime/webSocketBearerProtocols';
import { executionGrantBroker } from '@/features/auth/public';
import { toSameOriginWebSocketUrl } from '@/shared/utils/workspaceGateway';

const logger = createLogger('TerminalRealtimeManager');

interface ConnectOptions {
  force?: boolean;
}

interface TerminalRealtimeManagerOptions {
  onTabClosed?: (tabId: string) => void;
}

interface TerminalConnectionAttempt {
  id: number;
  generation: number;
  scopeId: number | null;
  workspaceId: string;
  terminalUrl: string;
}

const TERMINAL_SOCKET_TYPE = 'terminal' as const;
const TERMINAL_WEBSOCKET_PROTOCOL = 'aileron-terminal-v1';
type TerminalCreateMode = 'always' | 'default_if_empty';
type TerminalSize = { cols: number; rows: number };

export interface TerminalCreateRequest {
  workingDirectory?: string;
  size?: TerminalSize;
  fallbackWorkingDirectory?: string;
}

const RECONNECT_BASE_DELAY = 2_000;
const QUICK_RECONNECT_DELAY = 250;
const CONNECTION_TIMEOUT = 10_000;

export interface TerminalRealtimeAPI {
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => ReturnType<TerminalStore['getSnapshot']>;
  ensureConnected: () => void;
  ensureDefaultTab: (
    workingDirectory?: string,
    size?: TerminalSize,
  ) => void;
  createTab: (request?: TerminalCreateRequest) => void;
  closeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  sendInput: (tabId: string, data: string) => void;
  sendResize: (tabId: string, cols: number, rows: number) => void;
  attachXterm: (tabId: string, terminal: Terminal) => () => void;
  clearTerminal: (tabId: string) => void;
}

interface TerminalRealtimeScope {
  id: number;
  workspaceId: string | null;
  terminalUrl: string | null;
}

export interface TerminalRealtimeBinding {
  api: TerminalRealtimeAPI;
  activate: () => void;
}

export class TerminalRealtimeManager {
  private store: TerminalStore;

  private registry: WebSocketConnectionRegistry;

  private workspaceId: string | null = null;

  private terminalUrl: string | null = null;

  private connectionTimer: number | null = null;

  private reconnectTimer: number | null = null;

  private shouldReconnect = false;

  private connectionGeneration = 0;

  private nextConnectionAttemptId = 1;

  private pendingConnectionAttempt: TerminalConnectionAttempt | null = null;

  // Output is routed directly to the attached xterm instance instead of
  // through the React store, so re-renders don't happen per output chunk.
  // An attachment's lifetime is the tab's lifetime, not the component's:
  // the xterm instance persists in terminalInstanceRegistry across
  // TerminalTab remounts, so this manager keeps writing to it whether or
  // not a component is currently mounted for that tab.
  private terminals = new Map<string, Terminal>();

  private streamState = new Map<string, { lastSeq: number }>();

  private pendingCreateTabs: Array<TerminalCreateRequest & {
    scopeId: number;
    workspaceId: string;
  }> = [];

  private pendingDefaultCreate: {
    scopeId: number;
    workspaceId: string;
    state: 'queued' | 'sent';
    workingDirectory?: string;
    size?: TerminalSize;
  } | null = null;

  private pendingConnectionScope: TerminalRealtimeScope | null = null;

  private latestDeclaredScope: TerminalRealtimeScope | null = null;

  private latestDeclaredBinding: TerminalRealtimeBinding | null = null;

  private activeScopeId: number | null = null;

  private nextScopeId = 1;

  private disposed = false;

  private translate: (key: string) => string;

  private notifiedClosedTabIds = new Set<string>();

  constructor(
    registry: WebSocketConnectionRegistry,
    translate?: (key: string) => string,
    private readonly options: TerminalRealtimeManagerOptions = {},
  ) {
    this.registry = registry;
    this.store = createTerminalStore();
    this.translate = translate || ((key: string) => {
      const fallbacks: Record<string, string> = {
        'common.messages.terminalConnectionFailed': 'Failed to create terminal connection URL',
        'common.messages.terminalError': 'Terminal connection error occurred',
      };
      return fallbacks[key] || key;
    });
  }

  declareScope(
    workspaceId: string | null,
    terminalUrl: string | null,
  ): TerminalRealtimeBinding {
    if (
      this.latestDeclaredScope?.workspaceId === workspaceId
      && this.latestDeclaredScope.terminalUrl === terminalUrl
      && this.latestDeclaredBinding
    ) {
      return this.latestDeclaredBinding;
    }

    const scope = {
      id: this.nextScopeId,
      workspaceId,
      terminalUrl,
    };
    this.nextScopeId += 1;
    const api: TerminalRealtimeAPI = {
      subscribe: this.subscribe,
      getSnapshot: this.store.getSnapshot,
      ensureConnected: () => this.ensureConnected(scope),
      ensureDefaultTab: (workingDirectory, size) => {
        this.ensureDefaultTab(scope, workingDirectory, size);
      },
      createTab: (request) => this.createTab(scope, request),
      closeTab: (tabId) => this.closeTab(scope, tabId),
      switchTab: (tabId) => this.switchTab(scope, tabId),
      sendInput: (tabId, data) => this.sendInput(scope, tabId, data),
      sendResize: (tabId, cols, rows) => {
        this.sendResize(scope, tabId, cols, rows);
      },
      attachXterm: (tabId, terminal) => this.attachXterm(scope, tabId, terminal),
      clearTerminal: (tabId) => this.clearTerminal(scope, tabId),
    };
    const binding = {
      api,
      activate: () => this.activateScope(scope),
    };
    this.latestDeclaredScope = scope;
    this.latestDeclaredBinding = binding;
    return binding;
  }

  private activateScope(scope: TerminalRealtimeScope) {
    if (this.latestDeclaredScope?.id !== scope.id) {
      return;
    }

    this.disposed = false;
    const { workspaceId, terminalUrl } = scope;
    logger.debug(' updateWorkspace called', {
      oldWorkspaceId: this.workspaceId,
      newWorkspaceId: workspaceId,
      oldTerminalConfigured: this.terminalUrl !== null,
      newTerminalConfigured: terminalUrl !== null,
    });

    const workspaceChanged = this.workspaceId !== workspaceId;
    const terminalUrlChanged = this.terminalUrl !== terminalUrl;
    const hasChanged = workspaceChanged || terminalUrlChanged;
    const previousActiveScopeId = this.activeScopeId;

    if (workspaceChanged) {
      this.pendingCreateTabs = workspaceId
        ? this.pendingCreateTabs.filter((request) => request.scopeId === scope.id)
        : [];
      if (this.pendingDefaultCreate?.scopeId !== scope.id) {
        this.pendingDefaultCreate = null;
      }
    } else {
      const resumableScopeIds = new Set([previousActiveScopeId, scope.id]);
      this.pendingCreateTabs = this.pendingCreateTabs
        .filter((request) => (
          request.workspaceId === workspaceId
          && resumableScopeIds.has(request.scopeId)
        ))
        .map((request) => ({ ...request, scopeId: scope.id }));
      if (
        this.pendingDefaultCreate
        && this.pendingDefaultCreate.workspaceId === workspaceId
        && resumableScopeIds.has(this.pendingDefaultCreate.scopeId)
      ) {
        this.pendingDefaultCreate = {
          ...this.pendingDefaultCreate,
          scopeId: scope.id,
          state: terminalUrlChanged && this.pendingDefaultCreate.state === 'sent'
            ? 'queued'
            : this.pendingDefaultCreate.state,
        };
      } else {
        this.pendingDefaultCreate = null;
      }
    }

    const shouldResumeConnection = (
      this.pendingConnectionScope?.id === scope.id
      || this.pendingCreateTabs.some((request) => request.scopeId === scope.id)
      || this.pendingDefaultCreate?.scopeId === scope.id
    );

    this.activeScopeId = scope.id;
    if (!hasChanged) {
      this.pendingConnectionScope = null;
      if (shouldResumeConnection && this.workspaceId && this.terminalUrl) {
        this.connect();
      }
      logger.debug(' No change detected, activated latest scope binding');
      return;
    }

    logger.debug(' Workspace terminal configuration changed, updating...');
    this.workspaceId = workspaceId;
    this.terminalUrl = terminalUrl;
    this.connectionGeneration += 1;
    this.shouldReconnect = false;
    this.notifiedClosedTabIds.clear();
    this.clearTimers();
    this.detachSocketListeners(this.registry.getOrCreate(TERMINAL_SOCKET_TYPE).socket);
    this.registry.close(TERMINAL_SOCKET_TYPE);
    this.terminals.clear();
    this.streamState.clear();
    this.store.reset();

    this.pendingConnectionScope = null;
    if (shouldResumeConnection && this.workspaceId && this.terminalUrl) {
      this.connect();
    }
  }

  dispose() {
    this.connectionGeneration += 1;
    this.pendingConnectionAttempt = null;
    this.shouldReconnect = false;
    this.notifiedClosedTabIds.clear();
    this.clearTimers();
    this.clearPendingCreates();
    this.pendingConnectionScope = null;
    this.activeScopeId = null;
    this.disposed = true;
    this.detachSocketListeners(this.registry.getOrCreate(TERMINAL_SOCKET_TYPE).socket);
    this.registry.close(TERMINAL_SOCKET_TYPE);
    this.terminals.clear();
    this.streamState.clear();
    this.store.reset();
  }

  private subscribe = (listener: () => void) => {
    return this.store.subscribe(listener);
  };

  private ensureConnected(scope: TerminalRealtimeScope) {
    if (!scope.workspaceId || !scope.terminalUrl) {
      return;
    }
    if (!this.isCurrentScope(scope)) {
      if (!this.isLatestDeclaredScope(scope)) {
        return;
      }
      this.pendingConnectionScope = scope;
      return;
    }
    this.pendingConnectionScope = null;
    this.connect({ force: false });
  }

  private ensureDefaultTab(
    scope: TerminalRealtimeScope,
    workingDirectory?: string,
    size?: { cols: number; rows: number },
  ) {
    if (!scope.workspaceId) {
      return;
    }
    const isCurrentScope = this.isCurrentScope(scope);
    if (!isCurrentScope && !this.isLatestDeclaredScope(scope)) {
      return;
    }
    const snapshot = isCurrentScope ? this.store.getSnapshot() : null;
    if (snapshot && snapshot.tabs.length > 0) {
      this.pendingDefaultCreate = null;
      return;
    }
    this.ensureConnected(scope);
    if (this.pendingDefaultCreate?.workspaceId === scope.workspaceId) {
      return;
    }
    this.pendingDefaultCreate = {
      scopeId: scope.id,
      workspaceId: scope.workspaceId,
      state: 'queued',
      workingDirectory,
      size,
    };
    if (isCurrentScope) {
      this.flushPendingCreateTabs();
    }
  }

  private connect = async (options: ConnectOptions = {}) => {
    logger.debug(' connect called', {
      workspaceId: this.workspaceId,
      terminalConfigured: this.terminalUrl !== null,
      options,
    });

    const { force = false } = options;
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;

    if (!this.workspaceId || !this.terminalUrl) {
      logger.error(' Missing workspaceId or terminalUrl');
      this.store.setStatus('error', this.translate('common.messages.terminalConnectionFailed'));
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

    if (this.pendingConnectionAttempt?.generation === this.connectionGeneration) {
      logger.debug(' Connection attempt already pending, skipping');
      return;
    }

    if (socket) {
      this.detachSocketListeners(socket);
      try {
        socket.close();
      } catch (error) {
        logger.error('Failed to close existing terminal connection', { error });
      }
    }

    const attempt: TerminalConnectionAttempt = {
      id: this.nextConnectionAttemptId,
      generation: this.connectionGeneration,
      scopeId: this.activeScopeId,
      workspaceId: this.workspaceId,
      terminalUrl: this.terminalUrl,
    };
    this.nextConnectionAttemptId += 1;
    this.pendingConnectionAttempt = attempt;
    const pendingConnection = this.buildWebSocketConnection(
      attempt.workspaceId,
      attempt.terminalUrl,
    );
    const connection = pendingConnection instanceof Promise
      ? await pendingConnection
      : pendingConnection;
    if (!this.isCurrentConnectionAttempt(attempt)) {
      logger.debug(' Discarding stale terminal connection attempt');
      return;
    }
    this.pendingConnectionAttempt = null;
    const url = connection?.url ?? null;
    logger.debug(' Built WebSocket URL', { url });
    if (!connection) {
      logger.error(' Failed to build WebSocket URL');
      this.store.setStatus('error', this.translate('common.messages.terminalConnectionFailed'));
      return;
    }

    this.shouldReconnect = true;
    this.store.setStatus('connecting');

    logger.debug(' Creating WebSocket connection to:', url);
    const nextSocket = new WebSocket(connection.url, connection.protocols);
    logger.debug(' WebSocket created, readyState:', nextSocket.readyState);
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, nextSocket, 'connecting');

    this.connectionTimer = window.setTimeout(() => {
      if (nextSocket.readyState === WebSocket.CONNECTING) {
        try {
          nextSocket.close();
        } catch (error) {
          logger.error('Failed to close terminal connection after timeout', { error });
        }
      }
    }, CONNECTION_TIMEOUT);

    nextSocket.addEventListener('open', this.handleOpen);
    nextSocket.addEventListener('message', this.handleMessage);
    nextSocket.addEventListener('close', this.handleClose);
    nextSocket.addEventListener('error', this.handleError);
  };

  private createTab(
    scope: TerminalRealtimeScope,
    request: TerminalCreateRequest = {},
  ) {
    const { workingDirectory, size, fallbackWorkingDirectory } = request;
    if (!scope.workspaceId) {
      return;
    }
    const isCurrentScope = this.isCurrentScope(scope);
    if (!isCurrentScope && !this.isLatestDeclaredScope(scope)) {
      return;
    }
    const snapshot = isCurrentScope ? this.store.getSnapshot() : null;
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    const canSend = (
      isCurrentScope
      && socket
      && socket.readyState === WebSocket.OPEN
      && snapshot?.isSynced
    );
    const plannedCount = (snapshot?.tabs.length ?? 0)
      + this.pendingCreateTabs.filter(
        (request) => request.workspaceId === scope.workspaceId,
      ).length
      + (this.pendingDefaultCreate?.workspaceId === scope.workspaceId ? 1 : 0);

    if (plannedCount >= TERMINAL_MAX_TABS) {
      logger.warn('Terminal tab limit reached; create request ignored', { plannedCount });
      return;
    }

    if (!canSend) {
      this.ensureConnected(scope);
      this.pendingCreateTabs.push({
        scopeId: scope.id,
        workspaceId: scope.workspaceId,
        workingDirectory,
        fallbackWorkingDirectory,
        size,
      });
      return;
    }

    this.sendCreateTab(scope.workspaceId, 'always', {
      workingDirectory,
      size,
      fallbackWorkingDirectory,
    });
  }

  private sendCreateTab(
    workspaceId: string,
    createMode: TerminalCreateMode,
    request: TerminalCreateRequest = {},
  ) {
    const { workingDirectory, size, fallbackWorkingDirectory } = request;
    if (workspaceId !== this.workspaceId) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    const data: Record<string, string | number> = {
      create_mode: createMode,
      working_directory: workingDirectory || '/workspace',
      cols: size?.cols ?? 80,
      rows: size?.rows ?? 24,
    };
    if (fallbackWorkingDirectory) {
      data.fallback_working_directory = fallbackWorkingDirectory;
    }
    socket.send(JSON.stringify({ type: 'create_tab', data }));
  }

  private flushPendingCreateTabs() {
    const snapshot = this.store.getSnapshot();
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN || !snapshot.isSynced) {
      return;
    }

    if (
      snapshot.tabs.length > 0
      && this.pendingDefaultCreate?.workspaceId === this.workspaceId
    ) {
      this.pendingDefaultCreate = null;
    }

    let createdDefault = false;
    if (
      snapshot.tabs.length === 0
      && this.pendingDefaultCreate?.workspaceId === this.workspaceId
      && this.pendingDefaultCreate.state === 'queued'
    ) {
      const request = this.pendingDefaultCreate;
      this.pendingDefaultCreate = {
        ...request,
        state: 'sent',
      };
      this.sendCreateTab(request.workspaceId, 'default_if_empty', {
        workingDirectory: request.workingDirectory,
        size: request.size,
      });
      createdDefault = true;
    }

    const availableSlots = Math.max(
      TERMINAL_MAX_TABS - snapshot.tabs.length - (createdDefault ? 1 : 0),
      0,
    );
    if (availableSlots === 0) {
      return;
    }
    const currentWorkspaceRequests = this.pendingCreateTabs.filter(
      (request) => request.workspaceId === this.workspaceId,
    );
    const queued = currentWorkspaceRequests.slice(0, availableSlots);
    const queuedRequests = new Set(queued);
    this.pendingCreateTabs = this.pendingCreateTabs.filter(
      (request) => !queuedRequests.has(request),
    );
    queued.forEach(({
      workspaceId,
      workingDirectory,
      fallbackWorkingDirectory,
      size,
    }) => {
      this.sendCreateTab(workspaceId, 'always', {
        workingDirectory,
        size,
        fallbackWorkingDirectory,
      });
    });
  }

  private clearPendingCreates() {
    this.pendingCreateTabs = [];
    this.pendingDefaultCreate = null;
  }

  private forgetTerminal(tabId: string) {
    this.terminals.delete(tabId);
    this.streamState.delete(tabId);
  }

  private closeTab = (scope: TerminalRealtimeScope, tabId: string) => {
    if (!this.isCurrentScope(scope)) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
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
    this.forgetTerminal(tabId);
    this.notifyTabClosed(tabId);
  };

  private switchTab = (scope: TerminalRealtimeScope, tabId: string) => {
    if (!this.isCurrentScope(scope)) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
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

  private sendInput = (scope: TerminalRealtimeScope, tabId: string, data: string) => {
    if (!this.isCurrentScope(scope)) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
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

  private sendResize = (
    scope: TerminalRealtimeScope,
    tabId: string,
    cols: number,
    rows: number,
  ) => {
    if (!this.isCurrentScope(scope)) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
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

  private attachXterm = (
    scope: TerminalRealtimeScope,
    tabId: string,
    terminal: Terminal,
  ) => {
    if (!this.isCurrentScope(scope)) {
      return () => {};
    }
    this.terminals.set(tabId, terminal);
    if (!this.streamState.has(tabId)) {
      this.streamState.set(tabId, { lastSeq: 0 });
    }

    // Catch up on anything produced before this terminal was registered
    // (first attach) or missed while unregistered (shouldn't normally
    // happen since registration outlives the component, but this is the
    // recovery path if it does).
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN && this.store.getSnapshot().isSynced) {
      const state = this.streamState.get(tabId)!;
      this.requestReplay(tabId, state.lastSeq + 1);
    }

    // Attachment lifetime is the tab's lifetime (torn down via
    // forgetTerminal on close/dispose), so there is nothing to unwind here.
    return () => {};
  };

  private clearTerminal = (scope: TerminalRealtimeScope, tabId: string) => {
    if (!this.isCurrentScope(scope)) {
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'clear',
          tab_id: tabId,
        }),
      );
    }
  };

  private isCurrentScope(scope: TerminalRealtimeScope): boolean {
    return (
      !this.disposed
      && this.activeScopeId === scope.id
      && this.workspaceId === scope.workspaceId
      && this.terminalUrl === scope.terminalUrl
    );
  }

  private isLatestDeclaredScope(scope: TerminalRealtimeScope): boolean {
    return this.latestDeclaredScope?.id === scope.id;
  }

  private isCurrentConnectionAttempt(attempt: TerminalConnectionAttempt): boolean {
    return (
      !this.disposed
      && this.pendingConnectionAttempt?.id === attempt.id
      && this.connectionGeneration === attempt.generation
      && this.activeScopeId === attempt.scopeId
      && this.workspaceId === attempt.workspaceId
      && this.terminalUrl === attempt.terminalUrl
    );
  }

  private buildWebSocketConnection(
    workspaceId: string,
    terminalUrl: string,
  ): Promise<{
    url: string;
    protocols: string[];
  } | null> | { url: string; protocols: string[] } | null {
    try {
      const url = new URL(toSameOriginWebSocketUrl(terminalUrl));

      executionGrantBroker.registerTarget(terminalUrl, workspaceId);
      const grant = executionGrantBroker.getGrant(
        terminalUrl,
        'workspace-terminal',
        'terminal',
        workspaceId,
      );
      url.searchParams.set('workspace_id', workspaceId);
      const build = (token: string) => ({
        url: url.toString(),
        protocols: createWebSocketBearerProtocols(TERMINAL_WEBSOCKET_PROTOCOL, token),
      });
      if (typeof (grant as unknown) === 'string') {
        return build(grant as unknown as string);
      }
      return grant.then(build).catch((error: unknown) => {
        logger.error('Failed to build terminal WebSocket URL', { error });
        return null;
      });
    } catch (error) {
      logger.error('Failed to build terminal WebSocket URL', { error });
      return null;
    }
  }

  private handleOpen = (event: Event) => {
    if (!this.isCurrentSocketEvent(event)) {
      logger.debug('Ignoring stale terminal socket open event');
      return;
    }
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    this.registry.setSocket(TERMINAL_SOCKET_TYPE, managed.socket, 'open');
    this.registry.resetAttempts(TERMINAL_SOCKET_TYPE);
    this.clearConnectionTimer();
    this.store.setStatus('open');
    this.store.setSynced(false);
    this.sendListTabs();
  };

  private sendListTabs() {
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'list_tabs' }));
    }
  }

  private requestReplay(tabId: string, fromSeq: number) {
    const managed = this.registry.getOrCreate(TERMINAL_SOCKET_TYPE);
    const socket = managed.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'replay',
          tab_id: tabId,
          data: { from_seq: fromSeq },
        }),
      );
    }
  }

  private handleMessage = (event: MessageEvent<string>) => {
    if (!this.isCurrentSocketEvent(event)) {
      logger.debug('Ignoring stale terminal socket message event');
      return;
    }
    try {
      const payload = JSON.parse(event.data) as
        | { type: 'connected'; data: { client_id: string; user_id: string } }
        | { type: 'tab_created'; tab_id: string; data: { tab: TerminalTabMetadata } }
        | { type: 'tab_updated'; tab_id: string; data: { tab: TerminalTabMetadata } }
        | { type: 'tab_closed'; tab_id: string }
        | { type: 'tab_switched'; tab_id: string }
        | { type: 'output'; tab_id: string; data: { data: string; seq?: number } }
        | { type: 'tab_replay_reset'; tab_id: string; data: { requested_seq: number; floor_seq: number } }
        | { type: 'tab_cleared'; tab_id: string; data: { floor_seq: number } }
        | { type: 'tab_list'; data: { tabs: TerminalTabMetadata[] } }
        | { type: 'error'; data: { code: string; message: string }; tab_id?: string };

      switch (payload.type) {
        case 'connected':
          this.store.setClientId(payload.data.client_id);
          this.store.setStatus('open');
          break;
        case 'tab_created': {
          this.store.upsertTab(payload.data.tab);
          this.pendingDefaultCreate = null;
          // Only replay if a terminal is already attached; otherwise
          // attachXterm will request the catch-up replay once it attaches.
          if (this.terminals.has(payload.tab_id)) {
            const state = this.streamState.get(payload.tab_id) ?? { lastSeq: 0 };
            this.requestReplay(payload.tab_id, state.lastSeq + 1);
          }
          break;
        }
        case 'tab_updated':
          this.store.upsertTab(payload.data.tab);
          break;
        case 'tab_closed':
          this.store.closeTab(payload.tab_id);
          this.forgetTerminal(payload.tab_id);
          this.notifyTabClosed(payload.tab_id);
          break;
        case 'tab_switched':
          this.store.switchTab(payload.tab_id);
          break;
        case 'output': {
          const terminal = this.terminals.get(payload.tab_id);
          if (!terminal) {
            // No attached terminal yet: drop without advancing lastSeq so a
            // later attach replays from the start instead of from a gap.
            break;
          }
          const seq = payload.data.seq;
          const state = this.streamState.get(payload.tab_id);
          if (state && seq !== undefined && seq <= state.lastSeq) {
            // Duplicate delivery (live broadcast + replay can overlap).
            break;
          }
          try {
            terminal.write(payload.data.data);
          } catch (error) {
            logger.debug('Failed to write terminal output', { error });
          }
          if (seq !== undefined) {
            this.streamState.set(payload.tab_id, { lastSeq: seq });
          }
          break;
        }
        case 'tab_replay_reset': {
          const terminal = this.terminals.get(payload.tab_id);
          if (terminal) {
            try {
              terminal.reset();
            } catch (error) {
              logger.debug('Failed to reset terminal after replay reset', { error });
            }
          }
          const floorSeq = payload.data.floor_seq;
          this.streamState.set(payload.tab_id, { lastSeq: floorSeq - 1 });
          this.requestReplay(payload.tab_id, floorSeq);
          break;
        }
        case 'tab_cleared': {
          // Server-confirmed clear: reset the screen and move the local
          // seq cursor to the new floor. Unlike tab_replay_reset there is
          // nothing to replay — the ring was just emptied.
          const terminal = this.terminals.get(payload.tab_id);
          if (terminal) {
            try {
              terminal.reset();
            } catch (error) {
              logger.debug('Failed to reset terminal after clear', { error });
            }
          }
          this.streamState.set(payload.tab_id, { lastSeq: payload.data.floor_seq - 1 });
          break;
        }
        case 'tab_list': {
          this.store.applyTabList(payload.data.tabs);
          const listedTabIds = new Set(payload.data.tabs.map((tab) => tab.tab_id));
          payload.data.tabs.forEach((tab) => {
            if (!this.terminals.has(tab.tab_id)) {
              return;
            }
            const state = this.streamState.get(tab.tab_id) ?? { lastSeq: 0 };
            this.requestReplay(tab.tab_id, state.lastSeq + 1);
          });
          // Tabs that vanished server-side (e.g. closed while disconnected)
          // no longer need bookkeeping here.
          Array.from(this.terminals.keys()).forEach((tabId) => {
            if (!listedTabIds.has(tabId)) {
              this.forgetTerminal(tabId);
            }
          });
          this.flushPendingCreateTabs();
          break;
        }
        case 'error':
          this.store.setStatus('error', payload.data.message);
          break;
        default:
          break;
      }
    } catch (error) {
      logger.error('Failed to parse terminal WebSocket message', { error });
    }
  };

  private handleClose = (event: CloseEvent) => {
    if (!this.isCurrentSocketEvent(event)) {
      logger.debug('Ignoring stale terminal socket close event');
      return;
    }
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
    if (!this.isCurrentSocketEvent(event)) {
      logger.debug('Ignoring stale terminal socket error event');
      return;
    }
    logger.error('Terminal WebSocket error', { event });
    this.store.setStatus('error', this.translate('common.messages.terminalError'));
  };

  private isCurrentSocketEvent(event: Event): boolean {
    return event.target === this.registry.getOrCreate(TERMINAL_SOCKET_TYPE).socket;
  }

  private detachSocketListeners(socket?: WebSocket | null) {
    if (!socket) {
      return;
    }
    socket.removeEventListener('open', this.handleOpen);
    socket.removeEventListener('message', this.handleMessage);
    socket.removeEventListener('close', this.handleClose);
    socket.removeEventListener('error', this.handleError);
  }

  private notifyTabClosed(tabId: string) {
    if (this.notifiedClosedTabIds.has(tabId)) {
      return;
    }
    this.notifiedClosedTabIds.add(tabId);
    this.options.onTabClosed?.(tabId);
  }

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
