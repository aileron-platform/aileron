import { describe, expect, it } from 'vitest';

import { buildPermissionToolDecision } from './ChatPanel';
import type { ToolDecisionOption } from './agentSessionTypes';

const options: ToolDecisionOption[] = [
  { option_id: 'allow_once', name: 'Allow once', kind: 'allow_once', scope: 'once' },
  { option_id: 'allow_session', name: 'Allow for session', kind: 'allow_always', scope: 'session' },
  { option_id: 'reject_once', name: 'Reject', kind: 'reject_once', scope: 'once' },
];

describe('ChatPanel permission decision handling', () => {
  it('builds a session-scoped Codex permission decision with the allow_always option', () => {
    expect(
      buildPermissionToolDecision({
        requestId: 'request-1',
        taskId: 'task-1',
        allow: true,
        scope: 'session',
        options,
      }),
    ).toEqual({
      request_id: 'request-1',
      task_id: 'task-1',
      decision_type: 'permission',
      outcome: 'selected',
      option_id: 'allow_session',
      scope: 'session',
      decided_by: 'user',
    });
  });
});
