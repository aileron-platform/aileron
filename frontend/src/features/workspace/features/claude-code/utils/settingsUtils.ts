/**
 * SettingsPage 工具函數
 */

import type { ClaudeMcpServerPolicy } from '../services/claudeCodeApi';

// ============================================================================
// 規則正規化
// ============================================================================

/**
 * 正規化規則陣列（去空白、過濾空值、排序）
 */
export const normalizeRules = (rules: string[]): string[] =>
  rules
    .map((rule) => rule.trim())
    .filter((rule) => rule.length > 0)
    .sort((a, b) => a.localeCompare(b));

/**
 * 正規化環境變數陣列
 */
export const normalizeEnvEntries = (
  entries: Array<{ key: string; value: string }>
): Array<{ key: string; value: string }> =>
  entries
    .map(({ key, value }) => ({ key: key.trim(), value }))
    .filter(({ key, value }) => key.length > 0 || value.trim().length > 0)
    .sort((a, b) => {
      const keyCompare = a.key.localeCompare(b.key);
      if (keyCompare !== 0) {
        return keyCompare;
      }
      return a.value.localeCompare(b.value);
    });

export type McpServerPolicyState = Pick<ClaudeMcpServerPolicy, 'serverName'>;

/**
 * 正規化 MCP 伺服器政策陣列
 */
export const normalizeMcpPolicies = (
  policies: McpServerPolicyState[]
): McpServerPolicyState[] => {
  const normalizedNames = normalizeRules(policies.map((policy) => policy.serverName));
  return normalizedNames.map((serverName) => ({ serverName }));
};

// ============================================================================
// 比較函數
// ============================================================================

/**
 * 比較兩個字串陣列是否相等
 */
export const arraysEqual = (left: string[], right: string[]): boolean => {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => value === right[index]);
};

/**
 * 比較兩個環境變數陣列是否相等
 */
export const envEntriesEqual = (
  left: Array<{ key: string; value: string }>,
  right: Array<{ key: string; value: string }>
): boolean => {
  const normalizedLeft = normalizeEnvEntries(left);
  const normalizedRight = normalizeEnvEntries(right);
  if (normalizedLeft.length !== normalizedRight.length) {
    return false;
  }
  return normalizedLeft.every((entry, index) => {
    const rightEntry = normalizedRight[index];
    return entry.key === rightEntry.key && entry.value === rightEntry.value;
  });
};

/**
 * 比較兩個 MCP 伺服器政策陣列是否相等
 */
export const mcpPoliciesEqual = (
  left: McpServerPolicyState[],
  right: McpServerPolicyState[]
): boolean => {
  const normalizedLeft = normalizeMcpPolicies(left);
  const normalizedRight = normalizeMcpPolicies(right);
  if (normalizedLeft.length !== normalizedRight.length) {
    return false;
  }
  return normalizedLeft.every(
    (policy, index) => policy.serverName === normalizedRight[index].serverName
  );
};

/**
 * 比較兩個插件啟用狀態物件是否相等
 */
export const pluginsEqual = (
  left: Record<string, boolean>,
  right: Record<string, boolean>
): boolean => {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();

  if (!arraysEqual(leftKeys, rightKeys)) {
    return false;
  }

  return leftKeys.every((key) => left[key] === right[key]);
};
