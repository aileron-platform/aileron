import type {
  ThreadExecutionMetadata,
  ThreadTurnMetadata,
  ThreadTurnStatus,
  TimelineMessageItem,
} from '../../model/threadTimelineModel';

export type UiToolStatus =
  | 'pending'
  | 'awaiting_input'
  | 'completed'
  | 'error'
  | 'interrupted'
  | 'canceled'
  | 'aborted_by_execution_error'
  | 'result_missing';

export interface UiToolResult {
  messageId: string;
  isError: boolean;
  preview: string;
  byteLength: number;
  lineCount: number | null;
  truncated: boolean;
  mediaType: string;
}

export interface UiToolPart {
  kind: 'tool';
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  status: UiToolStatus;
  result?: UiToolResult;
  parts: UiMessagePart[];
}

export type UiMessagePart =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'attachment'; name: string; mimeType: string; attachmentType: 'image' | 'pdf' | 'text-file' | 'file' }
  | {
      kind: 'system_init';
      agentResumeId: string | null;
      model: string | null;
      cwd: string | null;
      tools: string[];
      slashCommands?: string[];
      outputStyle?: string | null;
      agents?: string[];
      skills?: string[];
      plugins?: string[];
      mcpServers: { name: string; status: string | null }[];
    }
  | UiToolPart;

export interface UiMessage {
  id: string;
  role: 'user' | 'agent' | 'system' | 'error' | 'init';
  parts: UiMessagePart[];
  createdAt: string;
}

export interface UiTimelineGroup {
  id: string;
  sequence: number;
  version: number;
  status: ThreadTurnStatus;
  messages: UiMessage[];
  gitDiffMessages: Extract<TimelineMessageItem, { type: 'git_diff' }>[];
}

const missingResultStatus = (
  turn: ThreadTurnMetadata,
  executionId: string,
  executions: ThreadExecutionMetadata[],
): UiToolStatus => {
  if (turn.status === 'running') return 'pending';
  if (turn.status === 'waiting_for_input') return 'awaiting_input';
  const execution = executions.find((item) => item.id === executionId);
  if (execution?.status === 'canceled') return 'canceled';
  if (execution?.status === 'stopped') return 'interrupted';
  if (execution?.status === 'error') return 'aborted_by_execution_error';
  return 'result_missing';
};

const toolPartFrom = (
  turn: ThreadTurnMetadata,
  message: Extract<TimelineMessageItem, { type: 'tool' }>,
  executions: ThreadExecutionMetadata[],
  children: Map<string, Extract<TimelineMessageItem, { type: 'tool' }>[]>,
  visited: Set<string> = new Set(),
): UiToolPart => {
  const nextVisited = new Set(visited).add(message.id);
  const parts = (children.get(message.id) ?? [])
    .filter((child) => !nextVisited.has(child.id))
    .map((child) => toolPartFrom(turn, child, executions, children, nextVisited));
  const result = message.providerResult;
  const answered = message.interactionAnswer !== null;
  return {
    kind: 'tool',
    id: message.id,
    name: message.call.name,
    parameters: message.call.parameters,
    status: result
      ? result.isError ? 'error' : 'completed'
      : answered ? 'completed' : missingResultStatus(turn, message.turnExecutionId, executions),
    ...(result ? { result } : {}),
    parts,
  };
};

const contentParts = (
  message: Extract<TimelineMessageItem, { type: 'user' | 'agent_text' | 'thinking' }>,
): UiMessagePart[] => message.content.parts.map((part) => {
  if (part.type !== 'text') {
    return {
      kind: 'attachment',
      name: part.name,
      mimeType: part.mimeType,
      attachmentType: part.type,
    };
  }
  return message.type === 'thinking'
    ? { kind: 'thinking', text: part.text }
    : { kind: 'text', text: part.text };
});

export const toTimelinePresentation = (
  items: TimelineMessageItem[],
  turn: ThreadTurnMetadata,
  executions: ThreadExecutionMetadata[],
): UiTimelineGroup => {
  const ordered = [...items].sort((left, right) => left.sequence - right.sequence);
  const children = new Map<string, Extract<TimelineMessageItem, { type: 'tool' }>[] >();
  const loadedToolIds = new Set(
    ordered.filter((message) => message.type === 'tool').map((message) => message.id),
  );
  ordered.forEach((message) => {
    if (
      message.type !== 'tool'
      || message.parentItemId === null
      || !loadedToolIds.has(message.parentItemId)
    ) return;
    children.set(message.parentItemId, [...(children.get(message.parentItemId) ?? []), message]);
  });
  const messages: UiMessage[] = [];
  let agentBuffer: UiMessage | null = null;
  const flushAgent = () => {
    if (agentBuffer) messages.push(agentBuffer);
    agentBuffer = null;
  };

  ordered.forEach((message) => {
    if (message.type === 'git_diff') return;
    if (
      message.type === 'tool'
      && message.parentItemId !== null
      && loadedToolIds.has(message.parentItemId)
    ) return;
    if (message.type === 'system' || message.type === 'error') {
      flushAgent();
      messages.push({
        id: message.id,
        role: message.type,
        parts: [{ kind: 'text', text: message.content.text }],
        createdAt: message.createdAt,
      });
      return;
    }
    if (message.type === 'system_init') {
      flushAgent();
      messages.push({ id: message.id, role: 'init', parts: [{ kind: 'system_init', ...message.content }], createdAt: message.createdAt });
      return;
    }
    if (message.type === 'user') {
      flushAgent();
      messages.push({ id: message.id, role: 'user', parts: contentParts(message), createdAt: message.createdAt });
      return;
    }
    const parts = message.type === 'tool'
      ? [toolPartFrom(turn, message, executions, children)]
      : contentParts(message);
    if (!agentBuffer) {
      agentBuffer = { id: message.id, role: 'agent', parts, createdAt: message.createdAt };
    } else {
      agentBuffer.parts.push(...parts);
    }
  });
  flushAgent();

  return {
    id: turn.id,
    sequence: turn.sequence,
    version: turn.version,
    status: turn.status,
    messages,
    gitDiffMessages: ordered.filter(
      (message): message is Extract<TimelineMessageItem, { type: 'git_diff' }> => message.type === 'git_diff',
    ),
  };
};
