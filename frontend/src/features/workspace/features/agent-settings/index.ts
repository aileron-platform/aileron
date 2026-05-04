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

// Shared settings UI primitives.
export {
  AgentSettingsLayerSelector,
  AgentSettingsSourceFilter,
  AgentSettingsSourceBadge,
  NewThreadNotice,
  ReadOnlySourceNotice,
  getAgentSettingsSourceIcon,
  getAgentSettingsSourceBadgeClassName,
  normalizeAgentSettingsSourceType,
} from './components/SettingsSourcePrimitives';
export {
  SettingsFileTreeWorkflow,
} from './components/SettingsFileTreeWorkflow';
export type {
  AgentSettingsLayerSelectorProps,
  AgentSettingsSourceFilterProps,
  AgentSettingsSourceOption,
  AgentSettingsSourceDescriptor,
  AgentSettingsSourceType,
} from './components/SettingsSourcePrimitives';
export type {
  SettingsFileSelection,
  SettingsFileTreeScopeOption,
  SettingsFileTreeWorkflowLabels,
  SettingsFileTreeWorkflowProps,
} from './components/SettingsFileTreeWorkflow';
