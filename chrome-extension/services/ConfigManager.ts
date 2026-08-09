/**
 * ConfigManager - Manages relay connection configuration.
 *
 * Supports:
 * - Build-time defaults via import.meta.env (VITE_RELAY_*)
 * - Runtime configuration via chrome.storage.local
 */

import type { Logger } from "../utils/logger";
import type {
  BrowserExtensionPairingAssertion,
  BrowserExtensionPairingSession,
  RelayConfig,
} from "../utils/types";

const STORAGE_KEY = "relayConfig";

// Build-time defaults from environment variables
const DEFAULT_CONFIG: RelayConfig = {
  host: import.meta.env.VITE_RELAY_HOST || "localhost",
  port: parseInt(import.meta.env.VITE_RELAY_PORT || "3002", 10),
  basePath: import.meta.env.VITE_RELAY_BASE_PATH || "/api/v1/client-browser-relay",
};

export class ConfigManager {
  private cachedConfig: RelayConfig | null = null;
  private pairingSession: BrowserExtensionPairingSession | null = null;
  private logger: Logger;
  private now: () => number;

  constructor(logger: Logger, now: () => number = Date.now) {
    this.logger = logger;
    this.now = now;
  }

  /**
   * Get the current relay configuration.
   * Returns saved config from storage or defaults.
   */
  async getConfig(): Promise<RelayConfig> {
    if (this.cachedConfig) {
      return this.cachedConfig;
    }

    try {
      const result = await chrome.storage.local.get(STORAGE_KEY);
      if (result[STORAGE_KEY]) {
        this.cachedConfig = validateRelayConfig({ ...DEFAULT_CONFIG, ...result[STORAGE_KEY] });
      } else {
        this.cachedConfig = { ...DEFAULT_CONFIG };
      }
    } catch (error) {
      this.logger.log(`Failed to load config from storage, using defaults: ${error}`);
      this.cachedConfig = { ...DEFAULT_CONFIG };
    }

    return this.cachedConfig;
  }

  /**
   * Save relay configuration to storage.
   */
  async setConfig(config: Partial<RelayConfig>): Promise<RelayConfig> {
    rejectUnknownConfigFields(config);
    const currentConfig = await this.getConfig();
    const newConfig = validateRelayConfig({
      ...currentConfig,
      ...config,
    });

    await chrome.storage.local.set({ [STORAGE_KEY]: newConfig });
    this.cachedConfig = newConfig;

    return newConfig;
  }

  /**
   * Reset configuration to build-time defaults.
   */
  async resetConfig(): Promise<RelayConfig> {
    await chrome.storage.local.remove(STORAGE_KEY);
    this.cachedConfig = { ...DEFAULT_CONFIG };
    return this.cachedConfig;
  }

  /**
   * Get the default configuration (build-time values).
   */
  getDefaultConfig(): RelayConfig {
    return { ...DEFAULT_CONFIG };
  }

  /**
   * Build the WebSocket URL from configuration.
   */
  buildWebSocketUrl(config: RelayConfig): string {
    const validated = validateRelayConfig(config);
    const protocol = validated.host === "localhost" || validated.host === "127.0.0.1" ? "ws" : "wss";
    return `${protocol}://${validated.host}:${validated.port}${validated.basePath}/extension`;
  }

  /**
   * Build the health check URL from configuration.
   */
  buildHealthCheckUrl(config: RelayConfig): string {
    const validated = validateRelayConfig(config);
    const protocol = validated.host === "localhost" || validated.host === "127.0.0.1" ? "http" : "https";
    return `${protocol}://${validated.host}:${validated.port}${validated.basePath}/health`;
  }

  /**
   * Accept a short-lived Manager assertion without writing it to persistent storage.
   */
  setPairingAssertion(pairing: BrowserExtensionPairingAssertion): BrowserExtensionPairingSession {
    const session = validatePairingAssertion(pairing, this.now());
    this.pairingSession = session;
    return { ...session };
  }

  /**
   * Consume the assertion exactly once before a WebSocket handshake.
   */
  consumePairingAssertion(): BrowserExtensionPairingSession | null {
    const session = this.getPairingAssertion();
    this.pairingSession = null;
    return session;
  }

  getPairingAssertion(): BrowserExtensionPairingSession | null {
    if (!this.pairingSession) {
      return null;
    }
    if (this.pairingSession.expiresAt <= this.now()) {
      this.pairingSession = null;
      return null;
    }
    return { ...this.pairingSession };
  }

  clearPairingAssertion(runtimeInstanceId?: string): void {
    if (
      runtimeInstanceId === undefined ||
      this.pairingSession?.runtimeInstanceId === runtimeInstanceId
    ) {
      this.pairingSession = null;
    }
  }

  /**
   * Clear the cached configuration.
   * Call this when configuration might have changed externally.
   */
  clearCache(): void {
    this.cachedConfig = null;
  }
}

function validateRelayConfig(config: RelayConfig): RelayConfig {
  if (
    typeof config.host !== "string" ||
    config.host.length === 0 ||
    config.host !== config.host.trim() ||
    /[\s/@?#\\]/.test(config.host)
  ) {
    throw new Error("Relay host is invalid");
  }
  if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) {
    throw new Error("Relay port is invalid");
  }
  if (
    typeof config.basePath !== "string" ||
    !/^\/[A-Za-z0-9/_-]+$/.test(config.basePath) ||
    config.basePath.includes("//") ||
    config.basePath.endsWith("/")
  ) {
    throw new Error("Relay base path is invalid");
  }
  return { host: config.host, port: config.port, basePath: config.basePath };
}

function rejectUnknownConfigFields(config: Partial<RelayConfig>): void {
  const allowedFields = new Set(["host", "port", "basePath"]);
  for (const field of Object.keys(config)) {
    if (!allowedFields.has(field)) {
      throw new Error("Relay configuration contains an unsupported field");
    }
  }
}

function validatePairingAssertion(
  pairing: BrowserExtensionPairingAssertion,
  nowMilliseconds: number
): BrowserExtensionPairingSession {
  if (
    !pairing ||
    typeof pairing.assertion !== "string" ||
    pairing.assertion.length === 0 ||
    pairing.assertion.length > 16_384 ||
    /\s/.test(pairing.assertion) ||
    typeof pairing.runtimeInstanceId !== "string" ||
    pairing.runtimeInstanceId.length === 0 ||
    pairing.runtimeInstanceId !== pairing.runtimeInstanceId.trim()
  ) {
    throw new Error("Pairing assertion is invalid");
  }
  const parts = pairing.assertion.split(".");
  if (parts.length !== 3) {
    throw new Error("Pairing assertion is invalid");
  }

  let claims: Record<string, unknown>;
  try {
    claims = JSON.parse(decodeBase64Url(parts[1])) as Record<string, unknown>;
  } catch {
    throw new Error("Pairing assertion is invalid");
  }
  const issuedAt = claims.iat;
  const expiresAt = claims.exp;
  if (
    claims.aud !== "workspace-browser-extension" ||
    claims.action !== "browser_automation" ||
    claims.runtimeInstanceId !== pairing.runtimeInstanceId ||
    typeof issuedAt !== "number" ||
    !Number.isInteger(issuedAt) ||
    typeof expiresAt !== "number" ||
    !Number.isInteger(expiresAt) ||
    expiresAt <= issuedAt ||
    expiresAt - issuedAt > 60 ||
    issuedAt * 1000 > nowMilliseconds
  ) {
    throw new Error("Pairing assertion is invalid");
  }
  const expiresAtMilliseconds = expiresAt * 1000;
  if (expiresAtMilliseconds <= nowMilliseconds) {
    throw new Error("Pairing assertion has expired");
  }
  return {
    assertion: pairing.assertion,
    runtimeInstanceId: pairing.runtimeInstanceId,
    expiresAt: expiresAtMilliseconds,
  };
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return atob(padded);
}
