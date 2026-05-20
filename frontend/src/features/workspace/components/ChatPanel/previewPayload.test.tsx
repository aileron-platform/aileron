import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';

import { buildSessionResultPreviewPayload } from './previewPayload';
import type { AgentMessage, AgentTask } from './agentSessionTypes';
import { UsageStats } from '../../features/canvas/UsageStats';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const baseMessage: AgentMessage = {
  message_id: 'msg-1',
  session_id: 'session-1',
  task_id: 'task-1',
  created_at: '2026-04-14T00:00:00Z',
  index: 0,
  role: 'assistant',
  type: 'assistant',
  content_blocks: [
    {
      type: 'text',
      text: 'First completed answer',
    },
  ],
  metadata: {
    model: 'claude-sonnet',
  },
};

describe('buildSessionResultPreviewPayload', () => {
  it('hydrates preview stats from task raw response on the first open path', () => {
    const task: AgentTask = {
      task_id: 'task-1',
      session_id: 'session-1',
      created_at: '2026-04-14T00:00:00Z',
      created_by: 'user',
      status: 'completed',
      raw_sdk_response: {
        usage: {
          input_tokens: 10,
          output_tokens: 5,
          total_tokens: 15,
        },
        total_cost_usd: 0.0042,
      },
      duration_ms: 1200,
      model: 'claude-sonnet',
      token_usage: null,
    };

    const payload = buildSessionResultPreviewPayload(baseMessage, [task]);

    expect(payload).not.toBeNull();
    expect(payload?.markdownContent).toBe('First completed answer');
    expect(payload?.rawContent).toMatchObject({
      usage: {
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
      },
      total_cost_usd: 0.0042,
      duration_ms: 1200,
      model: 'claude-sonnet',
      metadata: {
        model: 'claude-sonnet',
      },
    });

    render(<UsageStats rawContent={payload?.rawContent} />);

    expect(screen.getByText('workspace.canvas.usage.stats')).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('passes compacted context status into usage stats', () => {
    const task: AgentTask = {
      task_id: 'task-1',
      session_id: 'session-1',
      created_at: '2026-04-14T00:00:00Z',
      created_by: 'user',
      status: 'completed',
      raw_sdk_response: {
        type: 'codex',
        context_compactions: [{ item_id: 'compact-1' }],
      },
      context_compacted: true,
      token_usage: {
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
      },
    };

    const payload = buildSessionResultPreviewPayload(baseMessage, [task]);

    expect(payload?.rawContent).toMatchObject({
      context_compacted: true,
      context_compactions: [{ item_id: 'compact-1' }],
    });

    render(<UsageStats rawContent={payload?.rawContent} />);

    expect(screen.getByText('workspace.canvas.usage.contextCompacted')).toBeInTheDocument();
  });

  it('keeps markdown preview available when usage metadata is genuinely absent', () => {
    const payload = buildSessionResultPreviewPayload(baseMessage, []);

    expect(payload).toEqual({
      markdownContent: 'First completed answer',
      rawContent: {
        model: 'claude-sonnet',
        metadata: {
          model: 'claude-sonnet',
        },
      },
    });
  });
});
