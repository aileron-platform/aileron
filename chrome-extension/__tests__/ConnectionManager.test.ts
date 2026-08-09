import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConnectionManager,
  EXTENSION_ASSERTION_PROTOCOL_PREFIX,
  EXTENSION_WEBSOCKET_PROTOCOL,
} from "../services/ConnectionManager";
import type { Logger } from "../utils/logger";
import type { BrowserExtensionPairingSession } from "../utils/types";

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  static autoOpen = true;

  readonly url: string;
  readonly protocols: string[];
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  sent: string[] = [];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = Array.isArray(protocols)
      ? protocols
      : protocols
        ? [protocols]
        : [];
    FakeWebSocket.instances.push(this);
    if (FakeWebSocket.autoOpen) {
      queueMicrotask(() => this.open());
    }
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  send(message: string): void {
    this.sent.push(message);
  }

  close(): void {
    this.serverClose();
  }

  serverClose(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code: 1001, reason: "generation recycled", wasClean: true } as CloseEvent);
  }
}

function logger(): Logger {
  return {
    log: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
  };
}

function pairing(): BrowserExtensionPairingSession {
  return {
    assertion: "header.payload.signature",
    runtimeInstanceId: "runtime-instance-123",
    expiresAt: Date.now() + 45_000,
  };
}

describe("ConnectionManager", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    FakeWebSocket.autoOpen = true;
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a single-use pairing assertion only through WebSocket protocols", async () => {
    const testLogger = logger();
    const consumePairingAssertion = vi.fn().mockReturnValue(pairing());
    const manager = new ConnectionManager({
      logger: testLogger,
      onMessage: vi.fn(),
      onDisconnect: vi.fn(),
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("wss://relay.test:443/api/v1/client-browser-relay/extension"),
      buildHealthCheckUrl: vi
        .fn()
        .mockReturnValue("https://relay.test:443/api/v1/client-browser-relay/health"),
      consumePairingAssertion,
      clearPairingAssertion: vi.fn(),
    });

    await manager.ensureConnected();

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).not.toContain("?");
    expect(FakeWebSocket.instances[0].protocols).toEqual([
      EXTENSION_WEBSOCKET_PROTOCOL,
      EXTENSION_ASSERTION_PROTOCOL_PREFIX + "header.payload.signature",
    ]);
    expect(consumePairingAssertion).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(vi.mocked(testLogger.log).mock.calls)).not.toContain(
      "header.payload.signature"
    );
  });

  it("rejects query-string credentials before consuming an assertion", async () => {
    const consumePairingAssertion = vi.fn().mockReturnValue(pairing());
    const manager = new ConnectionManager({
      logger: logger(),
      onMessage: vi.fn(),
      onDisconnect: vi.fn(),
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue(
          "wss://relay.test/api/v1/client-browser-relay/extension?token=static"
        ),
      buildHealthCheckUrl: vi.fn(),
      consumePairingAssertion,
      clearPairingAssertion: vi.fn(),
    });

    await expect(manager.ensureConnected()).rejects.toThrow(
      "must not contain credentials or query parameters"
    );

    expect(consumePairingAssertion).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("fails closed without a fresh pairing assertion", async () => {
    const manager = new ConnectionManager({
      logger: logger(),
      onMessage: vi.fn(),
      onDisconnect: vi.fn(),
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("wss://relay.test/api/v1/client-browser-relay/extension"),
      buildHealthCheckUrl: vi
        .fn()
        .mockReturnValue("https://relay.test/api/v1/client-browser-relay/health"),
      consumePairingAssertion: vi.fn().mockReturnValue(null),
      clearPairingAssertion: vi.fn(),
    });

    await expect(manager.ensureConnected()).rejects.toThrow(
      "fresh browser pairing assertion"
    );

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("clears the generation binding and does not reconnect after recycle", async () => {
    const clearPairingAssertion = vi.fn();
    const onDisconnect = vi.fn();
    const manager = new ConnectionManager({
      logger: logger(),
      onMessage: vi.fn(),
      onDisconnect,
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("wss://relay.test/api/v1/client-browser-relay/extension"),
      buildHealthCheckUrl: vi
        .fn()
        .mockReturnValue("https://relay.test/api/v1/client-browser-relay/health"),
      consumePairingAssertion: vi.fn().mockReturnValue(pairing()),
      clearPairingAssertion,
    });

    await manager.ensureConnected();
    FakeWebSocket.instances[0].serverClose();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(clearPairingAssertion).toHaveBeenCalledWith("runtime-instance-123");
    expect(onDisconnect).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(manager.isConnected()).toBe(false);
  });

  it("cancels an in-flight old-generation handshake before using a new assertion", async () => {
    FakeWebSocket.autoOpen = false;
    const oldPairing = pairing();
    const newPairing = {
      ...pairing(),
      assertion: "new.header.signature",
      runtimeInstanceId: "runtime-instance-new",
    };
    const consumePairingAssertion = vi
      .fn()
      .mockReturnValueOnce(oldPairing)
      .mockReturnValueOnce(newPairing);
    const manager = new ConnectionManager({
      logger: logger(),
      onMessage: vi.fn(),
      onDisconnect: vi.fn(),
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("wss://relay.test/api/v1/client-browser-relay/extension"),
      buildHealthCheckUrl: vi
        .fn()
        .mockReturnValue("https://relay.test/api/v1/client-browser-relay/health"),
      consumePairingAssertion,
      clearPairingAssertion: vi.fn(),
    });

    manager.startMaintaining();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(FakeWebSocket.instances).toHaveLength(1);

    manager.disconnect();
    FakeWebSocket.autoOpen = true;
    manager.startMaintaining();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[0].readyState).toBe(FakeWebSocket.CLOSED);
    expect(FakeWebSocket.instances[1].protocols[1]).toBe(
      EXTENSION_ASSERTION_PROTOCOL_PREFIX + newPairing.assertion
    );
    expect(manager.isConnected()).toBe(true);
  });

  it("can replace a connected generation without clearing the pending assertion", async () => {
    const newPairing = {
      ...pairing(),
      assertion: "new.header.signature",
      runtimeInstanceId: "runtime-instance-new",
    };
    const consumePairingAssertion = vi
      .fn()
      .mockReturnValueOnce(pairing())
      .mockReturnValueOnce(newPairing);
    const clearPairingAssertion = vi.fn();
    const manager = new ConnectionManager({
      logger: logger(),
      onMessage: vi.fn(),
      onDisconnect: vi.fn(),
      getConfig: vi.fn().mockResolvedValue({
        host: "relay.test",
        port: 443,
        basePath: "/api/v1/client-browser-relay",
      }),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("wss://relay.test/api/v1/client-browser-relay/extension"),
      buildHealthCheckUrl: vi
        .fn()
        .mockReturnValue("https://relay.test/api/v1/client-browser-relay/health"),
      consumePairingAssertion,
      clearPairingAssertion,
    });

    await manager.ensureConnected();
    manager.disconnect({ preservePendingPairingAssertion: true });
    await manager.ensureConnected();

    expect(clearPairingAssertion).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].protocols[1]).toBe(
      EXTENSION_ASSERTION_PROTOCOL_PREFIX + newPairing.assertion
    );
  });
});
