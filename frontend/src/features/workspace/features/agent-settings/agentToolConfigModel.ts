import type { AgentToolCapabilities } from './model/capabilities';

export type AgentToolCapabilityKey = keyof AgentToolCapabilities;

const CAPABILITY_SUB_VIEW_IDS: Partial<Record<AgentToolCapabilityKey, string>> = {
  mcp: 'mcp',
  skills: 'skills',
  slashCommands: 'slash-commands',
  agentDefinitions: 'subagents',
  hooks: 'hooks',
  outputStyles: 'output-styles',
  memory: 'memory',
  prompts: 'prompts',
  rules: 'rules',
  plugins: 'plugins',
  settings: 'settings',
};

const NAVIGATION_CAPABILITY_ORDER: AgentToolCapabilityKey[] = [
  'mcp',
  'skills',
  'slashCommands',
  'agentDefinitions',
  'hooks',
  'outputStyles',
  'memory',
  'prompts',
  'rules',
  'plugins',
  'settings',
];

export const isAgentCapabilityEnabled = (
  capabilities: AgentToolCapabilities,
  capabilityKey: AgentToolCapabilityKey,
): boolean => {
  const capability = capabilities[capabilityKey];
  return Boolean(capability && capability.supported !== false);
};

export const buildAgentSettingsSubViews = (
  instructionSubView: string,
  capabilities: AgentToolCapabilities,
  extra: string[] = [],
): string[] => [
  instructionSubView,
  ...NAVIGATION_CAPABILITY_ORDER.flatMap((capabilityKey) => {
    const subViewId = CAPABILITY_SUB_VIEW_IDS[capabilityKey];
    return subViewId && isAgentCapabilityEnabled(capabilities, capabilityKey) ? [subViewId] : [];
  }),
  ...extra,
];
