const AGENT_SUB_VIEW_LABEL_KEYS: Record<string, string> = {
  'claude-md': 'workspace.agentSettings.common.subViews.claudeMd',
  'agents-md': 'workspace.agentSettings.common.subViews.agentsMd',
  rules: 'workspace.agentSettings.common.subViews.rules',
  mcp: 'workspace.agentSettings.common.subViews.mcp',
  hooks: 'workspace.agentSettings.common.subViews.hooks',
  plugins: 'workspace.agentSettings.common.subViews.plugins',
  'slash-commands': 'workspace.agentSettings.common.subViews.slashCommands',
  prompts: 'workspace.agentSettings.common.subViews.prompts',
  skills: 'workspace.agentSettings.common.subViews.skills',
  subagents: 'workspace.agentSettings.common.subViews.subagents',
  memory: 'workspace.agentSettings.common.subViews.memory',
  'output-styles': 'workspace.agentSettings.common.subViews.outputStyles',
  settings: 'workspace.agentSettings.common.subViews.settings',
};

export const getAgentSubViewLabelKey = (subViewId: string): string => (
  AGENT_SUB_VIEW_LABEL_KEYS[subViewId] ?? 'workspace.agentSettings.common.subViews.unknown'
);
