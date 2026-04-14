/**
 * Agent Settings Module - 模組匯出
 */

// 型別
export type {
  AgentToolType,
  AgentToolConfig,
  AgentToolScopeOption,
  AgentToolMd,
  HookEventOption,
} from './types';

// 設定常數
export {
  AGENT_TOOL_CONFIGS,
  AGENT_NAVIGATION_IDS,
} from './agentToolConfigs';

// 工具函數
export {
  normalizeAgentType,
  getAgentToolConfig,
  isAgentToolFeature,
  getAgentTypeFromFeatureId,
  getDefaultSubView,
} from './utils';

// API 工廠
export { createAgentSettingsApi } from './services/agentSettingsApi';
export type { AgentSettingsApi } from './services/agentSettingsApi';

// 共用常數
export { SCOPE_BADGE_CLASSES } from './constants/scopeStyles';

