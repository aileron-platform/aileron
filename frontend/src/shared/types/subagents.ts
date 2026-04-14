export type SubagentScope = 'project' | 'user' | 'plugin';

export interface SubagentItem {
  id: string;
  fileName: string;
  scope: SubagentScope;
  name?: string;
  displayName: string;
  category: string;
  description: string;
  tags?: string[];
  pluginName?: string;
  marketplaceName?: string;
}

export const buildSubagentDisplayName = (
  fileName: string,
  name?: string | null,
  pluginName?: string | null,
): string => {
  // Plugin subagents: 使用 pluginName:fileName 格式
  if (pluginName) {
    return `${pluginName}:${fileName}`;
  }

  // 非 Plugin subagents: 使用 name 或 fileName
  return name?.trim() || fileName;
};

export const buildSubagentCategory = (
  scope: SubagentScope,
  name?: string | null,
): string => {
  const trimmedName = name?.trim();
  return trimmedName && trimmedName.length > 0 ? trimmedName : scope;
};

