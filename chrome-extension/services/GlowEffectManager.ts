/**
 * GlowEffectManager - Manages glow effect for controlled tabs
 */

import type { Logger } from "../utils/logger";
import type { StateManager } from "./StateManager";

export interface GlowEffectManagerDeps {
  logger: Logger;
  stateManager: StateManager;
}

// Glow effect CSS - enhanced version
const GLOW_CSS = `
html::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 2147483647;
  border: 6px solid rgba(76, 175, 80, 0.9);
  box-shadow:
    inset 0 0 30px rgba(76, 175, 80, 0.5),
    inset 0 0 60px rgba(76, 175, 80, 0.3),
    inset 0 0 90px rgba(76, 175, 80, 0.2),
    0 0 30px rgba(76, 175, 80, 0.6),
    0 0 60px rgba(76, 175, 80, 0.5),
    0 0 90px rgba(76, 175, 80, 0.4),
    0 0 120px rgba(76, 175, 80, 0.3);
  animation: ai-hub-glow-pulse 1.5s ease-in-out infinite;
}

@keyframes ai-hub-glow-pulse {
  0%, 100% {
    opacity: 1;
    border-color: rgba(76, 175, 80, 0.9);
    box-shadow:
      inset 0 0 30px rgba(76, 175, 80, 0.5),
      inset 0 0 60px rgba(76, 175, 80, 0.3),
      inset 0 0 90px rgba(76, 175, 80, 0.2),
      0 0 30px rgba(76, 175, 80, 0.6),
      0 0 60px rgba(76, 175, 80, 0.5),
      0 0 90px rgba(76, 175, 80, 0.4),
      0 0 120px rgba(76, 175, 80, 0.3);
  }
  50% {
    opacity: 0.4;
    border-color: rgba(76, 175, 80, 0.5);
    box-shadow:
      inset 0 0 20px rgba(76, 175, 80, 0.3),
      inset 0 0 40px rgba(76, 175, 80, 0.2),
      inset 0 0 60px rgba(76, 175, 80, 0.1),
      0 0 20px rgba(76, 175, 80, 0.4),
      0 0 40px rgba(76, 175, 80, 0.3),
      0 0 60px rgba(76, 175, 80, 0.2),
      0 0 80px rgba(76, 175, 80, 0.1);
  }
}
`;

export class GlowEffectManager {
  private logger: Logger;
  private stateManager: StateManager;
  private enabledTabs = new Set<number>();

  constructor(deps: GlowEffectManagerDeps) {
    this.logger = deps.logger;
    this.stateManager = deps.stateManager;
  }

  async setGlow(tabId: number, enabled: boolean): Promise<void> {
    const state = await this.stateManager.getState();

    const shouldGlow = enabled && state.glowEnabled;

    if (shouldGlow) {
      // Record enabled state first, so glow can be restored after page navigation even if injection fails
      this.enabledTabs.add(tabId);

      try {
        await chrome.scripting.insertCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
        this.logger.debug(`Glow enabled for tab ${tabId}`);
      } catch (error) {
        // Some special pages cannot accept CSS injection (e.g., blank pages, chrome:// pages)
        // Keep enabledTabs state so glow can be automatically restored after page navigation
        this.logger.debug(`Failed to inject glow CSS for tab ${tabId} (will retry on page load):`, error);
      }
    } else {
      this.enabledTabs.delete(tabId);

      try {
        await chrome.scripting.removeCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
        this.logger.debug(`Glow disabled for tab ${tabId}`);
      } catch (error) {
        // Failed removal is acceptable; state has been cleared
        this.logger.debug(`Failed to remove glow CSS from tab ${tabId}:`, error);
      }
    }
  }

  isEnabled(tabId: number): boolean {
    return this.enabledTabs.has(tabId);
  }

  async getGlowState(tabId: number): Promise<{
    enabled: boolean;
    userEnabled: boolean;
  }> {
    const state = await this.stateManager.getState();
    return {
      enabled: this.enabledTabs.has(tabId) && state.glowEnabled,
      userEnabled: state.glowEnabled,
    };
  }

  async handlePageLoad(tabId: number): Promise<void> {
    if (this.enabledTabs.has(tabId)) {
      this.logger.debug(`Page loaded for tab ${tabId}, re-injecting glow`);
      try {
        await chrome.scripting.insertCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
      } catch (error) {
        this.logger.debug(`Failed to re-inject glow CSS for tab ${tabId}:`, error);
      }
    }
  }

  handleTabClosed(tabId: number): void {
    if (this.enabledTabs.delete(tabId)) {
      this.logger.debug(`Tab ${tabId} closed, glow state cleaned up`);
    }
  }

  async removeAll(): Promise<void> {
    const tabIds = Array.from(this.enabledTabs);
    this.logger.debug(`Removing glow from ${tabIds.length} tabs`);

    for (const tabId of tabIds) {
      try {
        await chrome.scripting.removeCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
      } catch (error) {
        this.logger.debug(`Failed to remove glow CSS from tab ${tabId}:`, error);
      }
    }

    this.enabledTabs.clear();
  }
}
