import { beforeEach, describe, expect, it, vi } from "vitest";
import { fakeBrowser } from "wxt/testing";
import { ConfigManager } from "../services/ConfigManager";
import type { Logger } from "../utils/logger";

const NOW = 2_000_000_000_000;

function logger(): Logger {
  return {
    log: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
  };
}

function pairingAssertion(
  runtimeInstanceId = "runtime-instance-123",
  issuedAt = NOW / 1000,
  expiresAt = NOW / 1000 + 45
): string {
  const header = encodeBase64Url({ alg: "EdDSA", kid: "manager-key-v1" });
  const payload = encodeBase64Url({
    aud: "workspace-browser-extension",
    action: "browser_automation",
    runtimeInstanceId,
    iat: issuedAt,
    exp: expiresAt,
  });
  return `${header}.${payload}.signature`;
}

function encodeBase64Url(value: object): string {
  return btoa(JSON.stringify(value))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

describe("ConfigManager", () => {
  beforeEach(() => {
    fakeBrowser.reset();
  });

  it("builds credential-free extension and exact health URLs", async () => {
    const manager = new ConfigManager(logger(), () => NOW);
    const config = await manager.getConfig();

    expect(manager.buildWebSocketUrl(config)).toBe(
      "ws://localhost:3002/api/v1/client-browser-relay/extension"
    );
    expect(manager.buildHealthCheckUrl(config)).toBe(
      "http://localhost:3002/api/v1/client-browser-relay/health"
    );
  });

  it("rejects static token fields instead of persisting them", async () => {
    const manager = new ConfigManager(logger(), () => NOW);

    await expect(
      manager.setConfig({ token: "static-token" } as never)
    ).rejects.toThrow("unsupported field");

    const stored = await fakeBrowser.storage.local.get("relayConfig");
    expect(stored.relayConfig).toBeUndefined();
  });

  it("holds a valid pairing assertion only in memory and consumes it once", async () => {
    const manager = new ConfigManager(logger(), () => NOW);
    const assertion = pairingAssertion();

    const accepted = manager.setPairingAssertion({
      assertion,
      runtimeInstanceId: "runtime-instance-123",
    });
    const consumed = manager.consumePairingAssertion();
    const second = manager.consumePairingAssertion();

    expect(accepted).toEqual({
      assertion,
      runtimeInstanceId: "runtime-instance-123",
      expiresAt: NOW + 45_000,
    });
    expect(consumed).toEqual(accepted);
    expect(second).toBeNull();
    const persisted = await fakeBrowser.storage.local.get(null);
    expect(JSON.stringify(persisted)).not.toContain(assertion);
  });

  it("rejects expired or overlong pairing assertions", () => {
    const manager = new ConfigManager(logger(), () => NOW);

    expect(() =>
      manager.setPairingAssertion({
        assertion: pairingAssertion(
          "runtime-instance-123",
          NOW / 1000 - 45,
          NOW / 1000
        ),
        runtimeInstanceId: "runtime-instance-123",
      })
    ).toThrow("expired");
    expect(() =>
      manager.setPairingAssertion({
        assertion: pairingAssertion(
          "runtime-instance-123",
          NOW / 1000,
          NOW / 1000 + 61
        ),
        runtimeInstanceId: "runtime-instance-123",
      })
    ).toThrow("invalid");
  });

  it("rejects an assertion whose generation does not match its binding", () => {
    const manager = new ConfigManager(logger(), () => NOW);

    expect(() =>
      manager.setPairingAssertion({
        assertion: pairingAssertion("runtime-instance-old"),
        runtimeInstanceId: "runtime-instance-new",
      })
    ).toThrow("invalid");
  });

  it("replaces an old generation assertion and clears expired state", () => {
    let currentTime = NOW;
    const manager = new ConfigManager(logger(), () => currentTime);
    manager.setPairingAssertion({
      assertion: pairingAssertion("runtime-instance-old"),
      runtimeInstanceId: "runtime-instance-old",
    });
    const newAssertion = pairingAssertion("runtime-instance-new");

    manager.setPairingAssertion({
      assertion: newAssertion,
      runtimeInstanceId: "runtime-instance-new",
    });

    expect(manager.getPairingAssertion()?.runtimeInstanceId).toBe(
      "runtime-instance-new"
    );
    currentTime = NOW + 46_000;
    expect(manager.getPairingAssertion()).toBeNull();
  });
});
