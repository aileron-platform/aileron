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

export const applyAiChatHandoff = (
  current: string,
  request: AiChatHandoffInput,
  agenticTool: AgenticToolId,
): string => {
  const content = request.skillName
    ? `${agenticTool === 'codex' ? '$' : '/'}${request.skillName}\n\n${request.content}`
    : request.content;
  return request.mode === 'append' ? `${current}${content}` : content;
};
