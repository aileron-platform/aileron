/**
 * Agent Settings - 工具函數
 */

import type { AgentToolType, AgentToolConfig } from './types';
import { AGENT_TOOL_CONFIGS, AGENT_NAVIGATION_IDS } from './agentToolConfigs';

/**
 * Agent type 正規化對照表
 * 參考 agentSessionTypes.ts 的 CLI_TO_AGENTIC_TOOL_MAP
 */
const normalizeAgentTypeKey = (value: string): string =>
  value.trim().toLowerCase().replace(/[\s-]+/g, '');

/**
 * 將原始 Agent type 字串正規化為 AgentToolType
 */
export const normalizeAgentType = (raw: string | null | undefined): AgentToolType => {
  if (!raw) return 'claude';
  const normalized = normalizeAgentTypeKey(raw);

  switch (normalized) {
    case 'claude':
    case 'claudecode':
      return 'claude';
    case 'codex':
      return 'codex';
    case 'gemini':
      return 'gemini';
    case 'opencode':
      return 'opencode';
    default:
      return 'claude';
  }
};

/**
 * 取得 Agent 工具設定物件
 */
export const getAgentToolConfig = (agentType: AgentToolType): AgentToolConfig => {
  return AGENT_TOOL_CONFIGS[agentType];
};

/**
 * 判斷 featureId 是否為 Agent 工具設定功能
 */
export const isAgentToolFeature = (featureId: string): boolean => {
  return AGENT_NAVIGATION_IDS.includes(featureId);
};

/**
 * 從 featureId 反查 AgentToolType
 */
export const getAgentTypeFromFeatureId = (featureId: string): AgentToolType | null => {
  for (const config of Object.values(AGENT_TOOL_CONFIGS)) {
    if (config.navigationId === featureId) {
      return config.id;
    }
  }
  return null;
};

/**
 * 取得 Agent 工具的預設子視圖（指令檔案）
 */
export const getDefaultSubView = (agentType: AgentToolType): string => {
  const config = getAgentToolConfig(agentType);
  return config.agentsMd.subViewId;
};
