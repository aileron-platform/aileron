import { buildSkillInvocation } from '@/shared/types/slashCommands';
import type { AgenticToolId } from './threadCapabilitiesModel';

export type AiChatHandoffDelivery = 'draft' | 'submit';

export interface AiChatHandoffInput {
  content: string;
  delivery: AiChatHandoffDelivery;
  mode?: 'append' | 'replace';
  skillName?: string;
}

export interface AiChatHandoffRequest extends AiChatHandoffInput {
  id: string;
  workspaceId: string;
}

const apiPrefixByTool: Record<AgenticToolId, string> = {
  claude: 'claude-code',
  codex: 'codex',
  opencode: 'opencode',
};

export const applyAiChatHandoff = (
  current: string,
  request: AiChatHandoffInput,
  agenticTool: AgenticToolId,
): string => {
  const content = request.skillName
    ? `${buildSkillInvocation(apiPrefixByTool[agenticTool], request.skillName)}\n\n${request.content}`
    : request.content;
  return request.mode === 'append' ? `${current}${content}` : content;
};
