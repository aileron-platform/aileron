import type { AgenticToolId } from '../model/threadCapabilitiesModel';

export const agentIconSrcByTool: Record<AgenticToolId, string> = {
  claude: '/marketplace/providers/claude-code.png',
  codex: '/marketplace/providers/codex.png',
  opencode: '/marketplace/providers/opencode.png',
};
