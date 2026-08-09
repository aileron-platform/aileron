export const AGENTIC_TOOLS = ['claude-code', 'codex', 'opencode'] as const;

export type AgenticTool = typeof AGENTIC_TOOLS[number];

const AGENTIC_TOOL_SET = new Set<string>(AGENTIC_TOOLS);

export const DEFAULT_AGENTIC_TOOLS: AgenticTool[] = ['claude-code'];

export const isAgenticTool = (value: string): value is AgenticTool =>
  AGENTIC_TOOL_SET.has(value);

export const normalizeAgenticTools = (
  value: readonly string[] | null | undefined,
): AgenticTool[] => {
  const tools = value?.filter(isAgenticTool) ?? [];
  const unique = Array.from(new Set(tools));
  const sorted = AGENTIC_TOOLS.filter(tool => unique.includes(tool));
  return sorted.length > 0 ? sorted : [...DEFAULT_AGENTIC_TOOLS];
};
