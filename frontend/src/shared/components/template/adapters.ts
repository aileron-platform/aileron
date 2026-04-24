import type { TemplateCommand, TemplateAgent, TemplateOutputStyle } from '@/shared/types/templates';
import type { CommandFormValue, AgentFormValue, OutputStyleFormValue } from '../../../features/template-management/features/template-editor/formTypes';
import type { CommandData, AgentData } from './FileViewer';
import type { OutputStyleData } from './OutputStyleViewer';

// 適配器：將不同的數據類型轉換為共用的 BaseItem 格式

// TemplateCommand -> CommandData
export const adaptTemplateCommand = (cmd: TemplateCommand): CommandData => ({
  id: cmd.id,
  fileName: cmd.fileName,
  description: cmd.description,
  content: cmd.content,
});

// TemplateAgent -> AgentData
export const adaptTemplateAgent = (agent: TemplateAgent): AgentData => ({
  id: agent.id,
  fileName: agent.fileName,
  description: agent.description,
  content: agent.content,
});

// CommandFormValue -> CommandData
export const adaptCommandFormValue = (cmd: CommandFormValue): CommandData => ({
  id: cmd.localId,
  fileName: cmd.fileName,
  description: cmd.description,
  content: cmd.content,
});

// AgentFormValue -> AgentData
export const adaptAgentFormValue = (agent: AgentFormValue): AgentData => ({
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
export const adaptTemplateCommands = (commands: TemplateCommand[]): CommandData[] =>
  commands.map(adaptTemplateCommand);

export const adaptTemplateAgents = (agents: TemplateAgent[]): AgentData[] =>
  agents.map(adaptTemplateAgent);

export const adaptTemplateOutputStyles = (styles: TemplateOutputStyle[]): OutputStyleData[] =>
  styles.map(adaptTemplateOutputStyle);

export const adaptCommandFormValues = (commands: CommandFormValue[]): CommandData[] =>
  commands.map(adaptCommandFormValue);

export const adaptAgentFormValues = (agents: AgentFormValue[]): AgentData[] =>
  agents.map(adaptAgentFormValue);

export const adaptOutputStyleFormValues = (styles: OutputStyleFormValue[]): OutputStyleData[] =>
  styles.map(adaptOutputStyleFormValue);