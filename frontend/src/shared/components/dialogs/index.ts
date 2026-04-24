/**
 * 共享 Dialog 元件
 */

export {
  AgentDialog,
  type AgentDialogProps,
  type WorkspaceAgentData,
  type TemplateAgentData,
  type AgentScope,
} from './AgentDialog';

export {
  OutputStyleDialog,
  type OutputStyleDialogProps,
  type WorkspaceOutputStyleData,
  type TemplateOutputStyleData,
  type OutputStyleScope,
} from './OutputStyleDialog';

export {
  CommandDialog,
  type CommandDialogProps,
  type WorkspaceCommandData,
  type TemplateCommandData,
  type CommandScope,
} from './CommandDialog';

export {
  HookDialog,
  type HookDialogProps,
  type EventOption,
  type WorkspaceHookData,
  type TemplateHookData,
  type HookScope,
  type HookMatcher,
  type HookActionConfig,
} from './HookDialog';

export {
  MCPServerDialog,
  type MCPServerDialogProps,
  type WorkspaceMCPServerData,
  type TemplateMCPServerData,
  type MCPServerScope,
  type MCPTransport,
} from './MCPServerDialog';
