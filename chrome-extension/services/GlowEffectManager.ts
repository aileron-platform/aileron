/**
 * GlowEffectManager - 管理被控制標籤頁的光暈效果
 */

import type { Logger } from "../utils/logger";
import type { StateManager } from "./StateManager";

export interface GlowEffectManagerDeps {
  logger: Logger;
  stateManager: StateManager;
}

// 光暈效果的 CSS 樣式 - 增強版
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

  /**
   * 設置指定標籤頁的光暈效果
   */
  async setGlow(tabId: number, enabled: boolean): Promise<void> {
    // 讀取使用者全域設定
    const state = await this.stateManager.getState();

    // 只有在使用者啟用光暈功能時才執行
    const shouldGlow = enabled && state.glowEnabled;

    if (shouldGlow) {
      // 先記錄啟用狀態，這樣即使注入失敗，頁面導航後也能恢復
      this.enabledTabs.add(tabId);

      try {
        // 注入 CSS
        await chrome.scripting.insertCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
        this.logger.debug(`Glow enabled for tab ${tabId}`);
      } catch (error) {
        // 某些特殊頁面可能無法注入 CSS（例如空白頁、chrome:// 頁面）
        // 保留 enabledTabs 狀態，這樣頁面導航後可以自動恢復光暈
        this.logger.debug(`Failed to inject glow CSS for tab ${tabId} (will retry on page load):`, error);
      }
    } else {
      // 移除光暈狀態
      this.enabledTabs.delete(tabId);

      try {
        // 移除 CSS
        await chrome.scripting.removeCSS({
          target: { tabId },
          css: GLOW_CSS,
        });
        this.logger.debug(`Glow disabled for tab ${tabId}`);
      } catch (error) {
        // 移除失敗也沒關係，狀態已清除
        this.logger.debug(`Failed to remove glow CSS from tab ${tabId}:`, error);
      }
    }
  }

  /**
   * 檢查指定標籤頁是否已啟用光暈
   */
  isEnabled(tabId: number): boolean {
    return this.enabledTabs.has(tabId);
  }

  /**
   * 獲取指定標籤頁的光暈狀態
   */
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

  /**
   * 處理頁面載入事件，重新注入光暈
   */
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

  /**
   * 處理標籤頁關閉事件，清理狀態
   */
  handleTabClosed(tabId: number): void {
    if (this.enabledTabs.delete(tabId)) {
      this.logger.debug(`Tab ${tabId} closed, glow state cleaned up`);
    }
  }

  /**
   * 移除所有光暈效果並清空狀態
   */
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
