/**
 * 共享 Dialog 元件
 */

export {
  SubAgentDialog,
  type SubAgentDialogProps,
  type WorkspaceSubAgentData,
  type TemplateSubAgentData,
  type SubAgentScope,
} from './SubAgentDialog';

export {
  OutputStyleDialog,
  type OutputStyleDialogProps,
  type WorkspaceOutputStyleData,
  type TemplateOutputStyleData,
  type OutputStyleScope,
} from './OutputStyleDialog';

export {
  SlashCommandDialog,
  type SlashCommandDialogProps,
  type WorkspaceSlashCommandData,
  type TemplateSlashCommandData,
  type SlashCommandScope,
} from './SlashCommandDialog';

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
