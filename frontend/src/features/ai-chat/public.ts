export {
  AiChatIntegrationProvider,
  useAiChatIntegration,
} from './contexts/AiChatIntegrationContext';
export type {
  AiChatCodeReference,
  AiChatFileChooserProps,
  AiChatIntegrationValue,
} from './contexts/AiChatIntegrationContext';
export type {
  AiChatHandoffDelivery,
  AiChatHandoffInput,
  AiChatHandoffRequest,
} from './model/chatHandoffModel';
export { CompanionChatPanel } from './components/CompanionChatPanel';
export { ThreadTimeline } from './components/messages/ThreadTimeline';
export {
  AgentSettingsMenu,
  ModeSettingsMenu,
  ModelSettingsMenu,
} from './components/ThreadSettingsMenu';
export {
  defaultSettings,
  normalizeThreadSettings,
} from './model/threadSettingsModel';
export type { ThreadSettings } from './model/threadSettingsModel';
export { getThreadApi, ThreadApiError } from './api/threadApi';
export {
  aiChatAutomationExecutionThreadQueryKey,
  aiChatThreadQueryKey,
} from './api/threadQueryKeys';
export { subscribeThreadEvents, useThreadEvents } from './realtime/threadEvents';
export type { AgenticToolId, WorkspaceCapabilities } from './model/threadCapabilitiesModel';

export const loadAiChatPage = () =>
  import('./AiChatPage').then(({ AiChatPage }) => ({
    default: AiChatPage,
  }));
