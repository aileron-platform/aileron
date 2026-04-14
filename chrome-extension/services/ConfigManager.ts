/**
 * ConfigManager - Manages relay connection configuration.
 *
 * Supports:
 * - Build-time defaults via import.meta.env (VITE_RELAY_*)
 * - Runtime configuration via chrome.storage.local
 */

import type { Logger } from "../utils/logger";

export interface RelayConfig {
  host: string;
  port: number;
  basePath: string;
}

const STORAGE_KEY = "relayConfig";

// Build-time defaults from environment variables
const DEFAULT_CONFIG: RelayConfig = {
  host: import.meta.env.VITE_RELAY_HOST || "localhost",
  port: parseInt(import.meta.env.VITE_RELAY_PORT || "3002", 10),
  basePath: import.meta.env.VITE_RELAY_BASE_PATH || "/api/v1/client-browser-relay",
};

export class ConfigManager {
  private cachedConfig: RelayConfig | null = null;
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
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
        this.cachedConfig = { ...DEFAULT_CONFIG, ...result[STORAGE_KEY] };
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
    const currentConfig = await this.getConfig();
    const newConfig: RelayConfig = {
      ...currentConfig,
      ...config,
    };

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
    const protocol = config.host === "localhost" || config.host === "127.0.0.1" ? "ws" : "wss";
    return `${protocol}://${config.host}:${config.port}${config.basePath}/extension`;
  }

  /**
   * Build the health check URL from configuration.
   */
  buildHealthCheckUrl(config: RelayConfig): string {
    const protocol = config.host === "localhost" || config.host === "127.0.0.1" ? "http" : "https";
    return `${protocol}://${config.host}:${config.port}${config.basePath}/`;
  }

  /**
   * Clear the cached configuration.
   * Call this when configuration might have changed externally.
   */
  clearCache(): void {
    this.cachedConfig = null;
  }
}
