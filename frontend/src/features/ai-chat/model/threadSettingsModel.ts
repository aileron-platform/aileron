import type { AgenticToolId, AgentMode, WorkspaceCapabilities } from './threadCapabilitiesModel';

export interface ThreadSettings {
  agenticTool: AgenticToolId;
  model: string;
  claudeMode: AgentMode | null;
}

const findTool = (caps: WorkspaceCapabilities, tool: AgenticToolId) => {
  const capability = caps.tools.find((item) => item.id === tool);
  if (!capability) {
    throw new Error(`Unknown agentic tool: ${tool}`);
  }
  return capability;
};

export const selectTool = (
  caps: WorkspaceCapabilities,
  current: ThreadSettings,
  tool: AgenticToolId,
): ThreadSettings => {
  const capability = findTool(caps, tool);
  return {
    agenticTool: tool,
    model: capability.models.includes(current.model) ? current.model : capability.defaultModel,
    claudeMode: capability.modes ? capability.defaultMode : null,
  };
};

export const selectModel = (current: ThreadSettings, model: string): ThreadSettings => ({
  ...current,
  model,
});

export const selectMode = (current: ThreadSettings, mode: AgentMode): ThreadSettings => ({
  ...current,
  claudeMode: mode,
});

export const normalizeThreadSettings = (
  caps: WorkspaceCapabilities,
  current: ThreadSettings,
): ThreadSettings => {
  const capability = caps.tools.find((item) => item.id === current.agenticTool)
    ?? findTool(caps, caps.defaultTool);
  return {
    agenticTool: capability.id,
    model: capability.models.includes(current.model) ? current.model : capability.defaultModel,
    claudeMode: capability.modes
      ? current.claudeMode && capability.modes.includes(current.claudeMode)
        ? current.claudeMode
        : capability.defaultMode
      : null,
  };
};

export const defaultSettings = (caps: WorkspaceCapabilities): ThreadSettings => {
  const capability = findTool(caps, caps.defaultTool);
  return {
    agenticTool: capability.id,
    model: capability.defaultModel,
    claudeMode: capability.defaultMode,
  };
};
