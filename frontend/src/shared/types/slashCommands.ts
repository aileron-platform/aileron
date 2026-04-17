export type SlashCommandScope = 'project' | 'user' | 'plugin';
export type SlashCommandItemKind = 'slash-command' | 'skill';

export interface SlashCommandItem {
  id: string;
  fileName: string;
  scope: SlashCommandScope;
  kind: SlashCommandItemKind;
  namespace?: string;
  pluginName?: string;
  displayName: string;
  category: string;
  description: string;
  invocation: string;
  tags?: string[];
}

const stripSlashCommandExtension = (value: string): string => (
  value.replace(/\.(md|toml)$/i, '')
);

export const buildSlashCommandDisplayName = (
  fileName: string,
  namespace?: string | null,
  pluginName?: string | null,
): string => {
  const commandName = stripSlashCommandExtension(fileName);

  // Plugin commands: 使用 pluginName:fileName 格式
  if (pluginName) {
    return `${pluginName}:${commandName}`;
  }

  // 非 Plugin commands: 使用 namespace/fileName 格式（如果有 namespace）
  const trimmedNamespace = namespace?.trim();
  return trimmedNamespace ? `${trimmedNamespace}/${commandName}` : commandName;
};

export const buildSlashCommandCategory = (
  scope: SlashCommandScope,
  namespace?: string | null,
): string => {
  const trimmedNamespace = namespace?.trim();
  return trimmedNamespace && trimmedNamespace.length > 0 ? trimmedNamespace : scope;
};

export const buildSlashCommandInvocation = (displayName: string): string => `/${displayName}`;

export const buildSkillDisplayName = (
  skillName: string,
  pluginName?: string | null,
): string => {
  const trimmedSkillName = skillName.trim();
  const trimmedPluginName = pluginName?.trim();
  return trimmedPluginName ? `${trimmedPluginName}:${trimmedSkillName}` : trimmedSkillName;
};

export const buildSkillInvocation = (
  skillName: string,
  pluginName?: string | null,
): string => `/${buildSkillDisplayName(skillName, pluginName)}`;
