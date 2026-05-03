/**
 * Agent Settings module exports.
 */

// Types.
export type {
  AgentToolType,
  AgentToolConfig,
  AgentToolScopeOption,
  AgentToolMd,
  HookEventOption,
} from './types';

// Configuration constants.
export {
  AGENT_TOOL_CONFIGS,
  AGENT_NAVIGATION_IDS,
} from './agentToolConfigs';

// Utilities.
export {
  normalizeAgentType,
  getAgentToolConfig,
  isAgentToolFeature,
  getAgentTypeFromFeatureId,
  getDefaultSubView,
} from './utils';

// API factory.
export { createAgentSettingsApi } from './services/agentSettingsApi';
export type { AgentSettingsApi } from './services/agentSettingsApi';

// Shared constants.
export { SCOPE_BADGE_CLASSES } from './constants/scopeStyles';

// Shared settings UI primitives.
export {
  AgentSettingsLayerSelector,
  AgentSettingsSourceBadge,
  NewThreadNotice,
  ReadOnlySourceNotice,
  getAgentSettingsSourceIcon,
} from './components/SettingsSourcePrimitives';
export {
  SettingsFileTreeWorkflow,
} from './components/SettingsFileTreeWorkflow';
export type {
  AgentSettingsLayerSelectorProps,
  AgentSettingsSourceDescriptor,
  AgentSettingsSourceType,
} from './components/SettingsSourcePrimitives';
export type {
  SettingsFileSelection,
  SettingsFileTreeScopeOption,
  SettingsFileTreeWorkflowLabels,
  SettingsFileTreeWorkflowProps,
} from './components/SettingsFileTreeWorkflow';
