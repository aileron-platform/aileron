import type { AgentMessage, AgentTask, ContentBlock, SystemCompleteBlock } from './agentSessionTypes';

export interface SessionResultPreviewPayload {
  markdownContent: string;
  rawContent?: Record<string, unknown>;
}

function getRawContentMarkdown(raw?: Record<string, unknown> | null): string {
  if (!raw) return '';
  const content = (raw as { content?: unknown }).content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((entry: unknown) => {
        if (typeof entry === 'string') return entry;
        if (entry && typeof entry === 'object' && 'text' in entry && typeof entry.text === 'string') {
          return entry.text;
        }
        return JSON.stringify(entry, null, 2);
      })
      .join('\n\n');
  }
  return JSON.stringify(raw, null, 2);
}

function buildPreviewMarkdown(contentBlocks?: ContentBlock[]): string {
  if (!contentBlocks || contentBlocks.length === 0) return '';

  const segments: string[] = [];
  contentBlocks.forEach((block) => {
    if (block.type === 'text') {
      const text = typeof block.text === 'string' ? block.text.trim() : '';
      if (text) {
        segments.push(text);
      }
      return;
    }

    if (block.type === 'thinking') {
      return;
    }

    if (block.type === 'system_complete') {
      const systemBlock = block as SystemCompleteBlock;
      if (systemBlock.result?.trim()) {
        segments.push(systemBlock.result.trim());
      }
      if (systemBlock.message?.trim()) {
        segments.push(systemBlock.message.trim());
      }
      if (systemBlock.metadata && Object.keys(systemBlock.metadata).length > 0) {
        segments.push(['```json', JSON.stringify(systemBlock.metadata, null, 2), '```'].join('\n'));
      }
    }
  });

  return segments.join('\n\n').trim();
}

function mergePreviewRawContent(
  message: AgentMessage,
  task?: AgentTask,
): Record<string, unknown> | undefined {
  const rawSdkMessage = message.raw_sdk_message ?? undefined;
  const rawSdkResponse = task?.raw_sdk_response ?? undefined;
  const metadata = message.metadata ?? undefined;
  const tokenUsage = task?.token_usage ?? undefined;
  const model = task?.model ?? metadata?.model ?? undefined;
  const durationMs = task?.duration_ms ?? undefined;
  const contextCompacted = task?.context_compacted ?? undefined;

  const merged: Record<string, unknown> = {
    ...(rawSdkResponse ?? {}),
    ...(rawSdkMessage ?? {}),
  };

  if (tokenUsage) {
    merged.token_usage = tokenUsage;
  }
  if (typeof durationMs === 'number') {
    merged.duration_ms = durationMs;
  }
  if (typeof contextCompacted === 'boolean') {
    merged.context_compacted = contextCompacted;
  }
  if (model) {
    merged.model = model;
  }
  if (metadata) {
    const existingMetadata = merged.metadata;
    merged.metadata = {
      ...(existingMetadata && typeof existingMetadata === 'object' ? existingMetadata as Record<string, unknown> : {}),
      ...metadata,
    };
  }

  return Object.keys(merged).length > 0 ? merged : undefined;
}

export function buildSessionResultPreviewPayload(
  message: AgentMessage,
  tasks: AgentTask[],
): SessionResultPreviewPayload | null {
  const markdownContent =
    buildPreviewMarkdown(message.content_blocks) || getRawContentMarkdown(message.raw_sdk_message);

  if (!markdownContent) {
    return null;
  }

  const task = tasks.find((entry) => entry.task_id && entry.task_id === message.task_id);

  return {
    markdownContent,
    rawContent: mergePreviewRawContent(message, task),
  };
}
