import type { AgentSettingsToolId, AgentToolConfig } from './model/capabilities';
import type { PageEntry, SubViewId } from './pageRegistryRuntime';
import { isAgentCapabilityEnabled } from './agentToolConfigModel';

export type AgentSettingsPageRegistry = Partial<Record<AgentSettingsToolId, Partial<Record<SubViewId, PageEntry>>>>;

export const resolveAgentSettingsPageEntry = (
  registry: AgentSettingsPageRegistry,
  config: AgentToolConfig,
  subView: string,
): PageEntry | null => {
  const pageEntry = registry[config.id]?.[subView];
  if (!pageEntry) {
    return null;
  }

  if (pageEntry.requiresCapability) {
    if (!isAgentCapabilityEnabled(config.capabilities, pageEntry.requiresCapability)) {
      return null;
    }
  }

  if (pageEntry.isSupported && !pageEntry.isSupported(config)) {
    return null;
  }

  return pageEntry;
};
