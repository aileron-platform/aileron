/**
 * ConnectionManager - Manages WebSocket connection to relay server.
 */

import type { Logger } from "../utils/logger";
import type { ExtensionCommandMessage, ExtensionResponseMessage, RelayConfig } from "../utils/types";

const RECONNECT_INTERVAL = 3000;

export interface ConnectionManagerDeps {
  logger: Logger;
  onMessage: (message: ExtensionCommandMessage) => Promise<unknown>;
  onDisconnect: () => void;
  getConfig: () => Promise<RelayConfig>;
  buildWebSocketUrl: (config: RelayConfig) => string;
  buildHealthCheckUrl: (config: RelayConfig) => string;
}

export class ConnectionManager {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldMaintain = false;
  private isConnecting = false;
  private maintainCallCount = 0;
  private clientId: string;
  private logger: Logger;
  private onMessage: (message: ExtensionCommandMessage) => Promise<unknown>;
  private onDisconnect: () => void;
  private getConfig: () => Promise<RelayConfig>;
  private buildWebSocketUrl: (config: RelayConfig) => string;
  private buildHealthCheckUrl: (config: RelayConfig) => string;

  constructor(deps: ConnectionManagerDeps) {
    this.clientId = `ext-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    this.logger = deps.logger;
    this.onMessage = deps.onMessage;
    this.onDisconnect = deps.onDisconnect;
    this.getConfig = deps.getConfig;
    this.buildWebSocketUrl = deps.buildWebSocketUrl;
    this.buildHealthCheckUrl = deps.buildHealthCheckUrl;
    this.logger.log(`ConnectionManager created with client ID: ${this.clientId}`);
  }

  /**
   * Check if WebSocket is open (may be stale if server crashed).
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Check if currently attempting to connect.
   */
  isAttemptingConnection(): boolean {
    return this.isConnecting || this.ws?.readyState === WebSocket.CONNECTING;
  }

  /**
   * Check if connection is active.
   * Returns true if WebSocket is open, false otherwise.
   * Health checks are only performed during connection establishment.
   */
  async checkConnection(): Promise<boolean> {
    return this.isConnected();
  }

  /**
   * Send a message to the relay server.
   */
  send(message: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.debug("Error sending message:", error);
      }
    } else {
      // Log when message is dropped due to non-OPEN state
      this.logger.debug(`Message dropped: WebSocket not OPEN (readyState=${this.ws?.readyState})`);
    }
  }

  /**
   * Start maintaining connection (auto-reconnect).
   */
  startMaintaining(): void {
    this.maintainCallCount++;
    this.logger.log(`startMaintaining called (count: ${this.maintainCallCount})`);

    this.shouldMaintain = true;

    // Clear any existing timer
    if (this.reconnectTimer) {
      this.logger.debug("startMaintaining: Clearing existing timer");
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    // If already connected or attempting to connect, no need to do anything
    if (this.isConnected()) {
      this.logger.debug("startMaintaining: Already connected, skipping");
      return;
    }

    if (this.isAttemptingConnection()) {
      this.logger.debug("startMaintaining: Already attempting connection, skipping");
      return;
    }

    this.logger.log("startMaintaining: Proceeding with connection attempt");

    // Try to connect
    this.tryConnect()
      .then(() => {
        // Connection successful, no need for retry timer
        this.logger.log("startMaintaining: Connection successful");
      })
      .catch((err) => {
        // Connection failed, schedule retry if still maintaining
        this.logger.log(`startMaintaining: Connection failed - ${err.message}`);
        if (this.shouldMaintain && !this.isConnected() && !this.isAttemptingConnection()) {
          this.logger.log(`startMaintaining: Scheduling retry in ${RECONNECT_INTERVAL}ms`);
          this.reconnectTimer = setTimeout(() => this.startMaintaining(), RECONNECT_INTERVAL);
        }
      });
  }

  /**
   * Stop connection maintenance.
   */
  stopMaintaining(): void {
    this.shouldMaintain = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Disconnect from relay and stop maintaining connection.
   */
  disconnect(): void {
    this.logger.log("disconnect: Called");
    this.stopMaintaining();
    if (this.ws) {
      this.logger.log("disconnect: Closing WebSocket");
      this.ws.close();
      this.ws = null;
    }
    this.onDisconnect();
  }

  /**
   * Ensure connection is established, waiting if needed.
   */
  async ensureConnected(): Promise<void> {
    if (this.isConnected()) return;

    await this.tryConnect();

    if (!this.isConnected()) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await this.tryConnect();
    }

    if (!this.isConnected()) {
      throw new Error("Could not connect to relay server");
    }
  }

  /**
   * Try to connect to relay server once.
   */
  private async tryConnect(): Promise<void> {
    const attemptId = `${this.clientId}-${Date.now()}`;

    // Prevent concurrent connection attempts
    if (this.isConnected() || this.isConnecting) {
      this.logger.debug(`tryConnect [${attemptId}]: Skipping (connected=${this.isConnected()}, connecting=${this.isConnecting})`);
      return;
    }

    this.logger.log(`tryConnect [${attemptId}]: Starting connection attempt`);
    this.isConnecting = true;

    try {
      const config = await this.getConfig();
      const healthUrl = this.buildHealthCheckUrl(config);
      const wsUrl = this.buildWebSocketUrl(config);

      // Check if server is available
      try {
        await fetch(healthUrl, { method: "GET" });
      } catch (err) {
        this.logger.debug(`tryConnect: Health check failed - ${err}`);
        this.isConnecting = false; // Reset flag before early return
        return;
      }

      this.logger.log(`tryConnect: [${this.clientId}] Health check passed, creating WebSocket...`, wsUrl);
      const socket = new WebSocket(wsUrl);
      this.logger.log(`tryConnect: [${this.clientId}] WebSocket created, readyState=${socket.readyState}`);

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("Connection timeout"));
        }, 5000);

        socket.onopen = () => {
          this.logger.log(`tryConnect: [${this.clientId}] WebSocket onopen`);
          clearTimeout(timeout);
          resolve();
        };

        socket.onerror = (err) => {
          this.logger.log(`tryConnect: [${this.clientId}] WebSocket onerror`, err);
          clearTimeout(timeout);
          reject(new Error("WebSocket connection failed"));
        };

        socket.onclose = (event) => {
          this.logger.log(`tryConnect: [${this.clientId}] WebSocket onclose during setup: code=${event.code}`);
          clearTimeout(timeout);
          reject(new Error(`WebSocket closed: ${event.reason || event.code}`));
        };
      });

      this.logger.log(`tryConnect: [${this.clientId}] Promise resolved`);

      // CRITICAL: Set this.ws FIRST so isConnected() returns true
      // This prevents concurrent connection attempts
      this.ws = socket;
      this.logger.log(`tryConnect: [${this.clientId}] this.ws set`);

      // CRITICAL: Reset isConnecting BEFORE setupSocketHandlers
      // to prevent race conditions during handler setup
      this.isConnecting = false;
      this.logger.log(`tryConnect: [${this.clientId}] isConnecting = false`);

      this.setupSocketHandlers(socket);
      this.logger.log(`tryConnect: [${this.clientId}] Connection complete`);
    } catch (err) {
      this.isConnecting = false;
      this.logger.log(`tryConnect: [${this.clientId}] Error: ${err}, isConnecting = false`);
      throw err;
    }
  }

  /**
   * Set up WebSocket event handlers.
   */
  private setupSocketHandlers(socket: WebSocket): void {
    this.logger.log("setupSocketHandlers: Setting up event handlers");
    socket.onmessage = async (event: MessageEvent) => {
      let message: ExtensionCommandMessage;
      try {
        message = JSON.parse(event.data);
      } catch (error) {
        this.logger.debug("Error parsing message:", error);
        this.send({
          error: { code: -32700, message: "Parse error" },
        });
        return;
      }

      const response: ExtensionResponseMessage = { id: message.id };
      try {
        response.result = await this.onMessage(message);
      } catch (error) {
        this.logger.debug("Error handling command:", error);
        response.error = (error as Error).message;
      }
      this.send(response);
    };

    socket.onclose = (event: CloseEvent) => {
      this.logger.log(`Connection closed: code=${event.code}, reason=${event.reason || 'none'}, wasClean=${event.wasClean}`);

      // Only clear ws if this is the current socket
      if (this.ws === socket) {
        this.logger.log(`Clearing current connection (ws === socket)`);
        this.ws = null;
        this.onDisconnect();

        // Add delay before reconnect to prevent rapid connection storms
        // Schedule reconnect if maintaining and not already trying to connect
        if (this.shouldMaintain && !this.reconnectTimer && !this.isConnecting) {
          this.logger.log(`Scheduling reconnect in ${RECONNECT_INTERVAL}ms`);
          this.reconnectTimer = setTimeout(() => this.startMaintaining(), RECONNECT_INTERVAL);
        } else {
          this.logger.debug(`Skipping reconnect: shouldMaintain=${this.shouldMaintain}, reconnectTimer=${!!this.reconnectTimer}, isConnecting=${this.isConnecting}`);
        }
      } else {
        this.logger.log(`Ignoring close event from stale socket (ws !== socket)`);
      }
    };

    socket.onerror = (event: Event) => {
      this.logger.debug("WebSocket error:", event);
    };
  }
}
