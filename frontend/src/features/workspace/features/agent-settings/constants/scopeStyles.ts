/**
 * CLI Settings Scope 樣式常數
 * 統一管理所有 scope 相關的樣式定義
 *
 * 設計理念：語義化配色
 * - Project (專案層級): 使用主題色 (primary)，表示最高層級
 * - User (使用者層級): 使用次要色 (secondary)，表示中間層級
 * - Local (本地層級): 使用靜音色 (muted)，表示最低層級
 * - Plugin (插件層級): 使用紫色系，表示外部擴展
 *
 * 自動適配主題：
 * - Light Mode: 綠色主題 (#00994e)
 * - Dark Mode: 藍色主題 (#3B82F6)
 */

import type { ClaudeScope } from '../../claude-code/types';

/**
 * Scope 標籤樣式對照表
 * 使用設計系統的顏色變數，完全整合 Tailwind 配置
 */
export const SCOPE_BADGE_CLASSES: Record<ClaudeScope, string> = {
  // Project (專案層級) - 使用主題色，表示最高層級
  project: 'bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary border-primary/20 dark:border-primary/30',

  // User (使用者層級) - 使用次要色，表示中間層級
  user: 'bg-secondary dark:bg-secondary text-secondary-foreground dark:text-secondary-foreground border-border dark:border-border',

  // Local (本地層級) - 使用靜音色，表示最低層級
  local: 'bg-muted dark:bg-muted text-muted-foreground dark:text-muted-foreground border-border dark:border-border',

  // Plugin (插件層級) - 使用紫色系，表示外部擴展
  plugin: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
};
