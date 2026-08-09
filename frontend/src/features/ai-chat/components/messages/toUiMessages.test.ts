import { describe, expect, it } from 'vitest';
import type { ThreadTurnMetadata, TimelineMessageItem } from '../../model/threadTimelineModel';
import { toTimelinePresentation } from './toUiMessages';

const turn: ThreadTurnMetadata = {
  id: 'turn-1', sequence: 1, version: 1, status: 'running', errorCode: null,
  errorInfo: null, createdAt: '2026-07-15T00:00:00Z', completedAt: null,
};

const tool = (providerResult: Extract<TimelineMessageItem, { type: 'tool' }>['providerResult']) => ({
  id: 'call-1', sequence: 2, itemVersion: providerResult ? 3 : 2,
  turnId: turn.id, turnExecutionId: 'execution-1', type: 'tool' as const,
  parentItemId: null, content: null, call: { name: 'Bash', parameters: { command: 'pwd' } },
  providerResult, interactionAnswer: null, createdAt: '2026-07-15T00:00:01Z',
});

describe('toTimelinePresentation', () => {
  it('places an older think item before its paired use and result', () => {
    const thinking: TimelineMessageItem = {
      id: 'think-1', sequence: 1, itemVersion: 1, turnId: turn.id,
      turnExecutionId: 'execution-1', type: 'thinking', parentItemId: null,
      content: { parts: [{ type: 'text', text: '**Checking**' }] },
      createdAt: '2026-07-15T00:00:00Z',
    };
    const result = { messageId: 'result-1', isError: false, preview: 'ok', byteLength: 2, lineCount: 1, truncated: false, mediaType: 'text/plain' };
    const presentation = toTimelinePresentation([tool(result), thinking], turn, []);
    expect(presentation.messages[0]?.parts.map((part) => part.kind)).toEqual(['thinking', 'tool']);
    const toolPart = presentation.messages[0]?.parts[1];
    expect(toolPart?.kind === 'tool' ? toolPart.result?.preview : null).toBe('ok');
  });

  it('does not mark a completed tool without a result as successful', () => {
    const presentation = toTimelinePresentation([tool(null)], { ...turn, status: 'complete' }, []);
    const part = presentation.messages[0]?.parts[0];
    expect(part?.kind === 'tool' ? part.status : null).toBe('result_missing');
  });
});
