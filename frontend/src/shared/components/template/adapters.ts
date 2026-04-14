import type { TemplateSlashCommand, TemplateSubAgent, TemplateOutputStyle } from '@/shared/types/templates';
import type { SlashCommandFormValue, SubAgentFormValue, OutputStyleFormValue } from '../../../features/template-management/features/template-editor/formTypes';
import type { SlashCommandData, SubAgentData } from './FileViewer';
import type { OutputStyleData } from './OutputStyleViewer';

// 適配器：將不同的數據類型轉換為共用的 BaseItem 格式

// TemplateSlashCommand -> SlashCommandData
export const adaptTemplateSlashCommand = (cmd: TemplateSlashCommand): SlashCommandData => ({
  id: cmd.id,
  fileName: cmd.fileName,
  description: cmd.description,
  content: cmd.content,
});

// TemplateSubAgent -> SubAgentData
export const adaptTemplateSubAgent = (agent: TemplateSubAgent): SubAgentData => ({
  id: agent.id,
  fileName: agent.fileName,
  description: agent.description,
  content: agent.content,
});

// SlashCommandFormValue -> SlashCommandData
export const adaptSlashCommandFormValue = (cmd: SlashCommandFormValue): SlashCommandData => ({
  id: cmd.localId,
  fileName: cmd.fileName,
  description: cmd.description,
  content: cmd.content,
});

// SubAgentFormValue -> SubAgentData
export const adaptSubAgentFormValue = (agent: SubAgentFormValue): SubAgentData => ({
  id: agent.localId,
  fileName: agent.fileName,
  description: agent.description,
  content: agent.content,
});

// TemplateOutputStyle -> OutputStyleData
export const adaptTemplateOutputStyle = (style: TemplateOutputStyle): OutputStyleData => ({
  id: style.id,
  fileName: style.fileName,
  description: style.description,
  content: style.content,
});

// OutputStyleFormValue -> OutputStyleData
export const adaptOutputStyleFormValue = (style: OutputStyleFormValue): OutputStyleData => ({
  id: style.localId,
  fileName: style.fileName,
  description: style.description,
  content: style.content,
});

// 批量適配器
export const adaptTemplateSlashCommands = (commands: TemplateSlashCommand[]): SlashCommandData[] =>
  commands.map(adaptTemplateSlashCommand);

export const adaptTemplateSubAgents = (agents: TemplateSubAgent[]): SubAgentData[] =>
  agents.map(adaptTemplateSubAgent);

export const adaptTemplateOutputStyles = (styles: TemplateOutputStyle[]): OutputStyleData[] =>
  styles.map(adaptTemplateOutputStyle);

export const adaptSlashCommandFormValues = (commands: SlashCommandFormValue[]): SlashCommandData[] =>
  commands.map(adaptSlashCommandFormValue);

export const adaptSubAgentFormValues = (agents: SubAgentFormValue[]): SubAgentData[] =>
  agents.map(adaptSubAgentFormValue);

export const adaptOutputStyleFormValues = (styles: OutputStyleFormValue[]): OutputStyleData[] =>
  styles.map(adaptOutputStyleFormValue);