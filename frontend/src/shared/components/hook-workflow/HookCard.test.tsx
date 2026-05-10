import React from 'react';
import { render, screen, within } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HookCard } from './HookCard';
import type { HookCardMatcher } from './HookCard';

const tMock = vi.fn((key: string, values?: Record<string, unknown>) => {
  if (values?.count !== undefined) return `${key}:${values.count}`;
  if (values?.value !== undefined) return `${key}:${values.value}`;
  return key;
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

const renderCard = (matchers: HookCardMatcher[], options: Partial<React.ComponentProps<typeof HookCard>> = {}) => render(
  <HookCard
    provider="claude-code"
    hook={{
      event: 'PreToolUse',
      description: 'Runs before a tool call',
      matchers,
    }}
    i18nKeyPrefix="custom.test"
    actionPreviewLimit={3}
    {...options}
  />,
);

describe('HookCard', () => {
  beforeEach(() => {
    tMock.mockClear();
  });

  it('renders all matchers, action summaries, and actual summary counts', () => {
    renderCard([
      {
        matcher: 'Bash',
        hooks: [
          { type: 'command', command: 'echo one', timeout: 10 },
          { type: 'command', command: 'echo two', timeout: 20 },
          { type: 'command', command: 'echo three', timeout: 30 },
        ],
      },
      {
        matcher: 'Write',
        hooks: [
          { type: 'command', command: 'write one', timeout: 40 },
          { type: 'command', command: 'write two', timeout: 50 },
          { type: 'command', command: 'write three', timeout: 60 },
        ],
      },
    ]);

    expect(screen.getAllByTestId('hook-card-matcher')).toHaveLength(2);
    expect(screen.getAllByTestId('hook-card-action')).toHaveLength(6);
    expect(screen.getByText('echo one')).toBeInTheDocument();
    expect(screen.getByText('write three')).toBeInTheDocument();
    expect(screen.getByText('custom.test.summary.matchers:2')).toBeInTheDocument();
    expect(screen.getByText('custom.test.summary.commands:6')).toBeInTheDocument();
  });

  it('does not repeat the event name inside each matcher row', () => {
    renderCard([
      {
        event: 'PreToolUse',
        matcher: 'Bash',
        hooks: [{ type: 'command', command: 'echo one' }],
      },
    ]);

    expect(screen.getAllByText('PreToolUse')).toHaveLength(1);
  });

  it('renders type-specific summaries and complete complex fields', () => {
    const input = { branch: 'main', files: ['a.ts', 'b.ts'] };

    renderCard([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: 'echo hi' },
          {
            type: 'http',
            url: 'https://example.com/hook',
            headers: { 'X-Auth': 'abc123', 'X-Trace': 'trace-xyz' },
            allowedEnvVars: ['CI', 'TOKEN', 'BUILD_ID'],
          },
          { type: 'mcp_tool', server: 'git', tool: 'commit', input },
          { type: 'prompt', prompt: 'Review the change before commit', model: 'claude-opus-4-7' },
        ],
      },
    ], { actionPreviewLimit: 4 });

    expect(screen.getByText('echo hi')).toBeInTheDocument();
    expect(screen.getByText('https://example.com/hook')).toBeInTheDocument();
    expect(screen.getByText('git.commit')).toBeInTheDocument();
    expect(screen.getByText('Review the change before commit')).toBeInTheDocument();
    expect(screen.getByText('X-Auth: abc123')).toBeInTheDocument();
    expect(screen.getByText('X-Trace: trace-xyz')).toBeInTheDocument();
    expect(screen.getByText('CI')).toBeInTheDocument();
    expect(screen.getByText('TOKEN')).toBeInTheDocument();
    expect(screen.getByText('BUILD_ID')).toBeInTheDocument();
    expect(screen.getByText((_content, element) => (
      element?.tagName.toLowerCase() === 'code'
      && element.textContent === JSON.stringify(input, null, 2)
    ))).toBeInTheDocument();
    expect(screen.getByText('claude-opus-4-7')).toBeInTheDocument();
  });

  it('gates unsupported provider fields', () => {
    renderCard([
      {
        matcher: '*',
        sequential: true,
        hooks: [{ type: 'command', command: 'codex hook' }],
      },
    ], { provider: 'codex', i18nKeyPrefix: 'workspace.agentSettings.codex.hooks.card' });

    expect(screen.queryByText('workspace.agentSettings.codex.hooks.card.sequential')).not.toBeInTheDocument();
  });

  it('truncates long prompts to 80 characters', () => {
    const prompt = 'x'.repeat(120);

    renderCard([
      {
        matcher: '*',
        hooks: [{ type: 'prompt', prompt }],
      },
    ]);

    expect(screen.getByText(`${'x'.repeat(80)}...`)).toBeInTheDocument();
  });

  it('renders empty command and url fallbacks', () => {
    renderCard([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: '   ' },
          { type: 'http', url: '   ' },
        ],
      },
    ]);

    expect(screen.getByText('custom.test.emptyCommand')).toBeInTheDocument();
    expect(screen.getByText('custom.test.emptyUrl')).toBeInTheDocument();
  });

  it('uses the injected i18n prefix for component labels', () => {
    renderCard([
      {
        matcher: '*',
        hooks: [{ type: 'command', command: 'echo prefix', timeout: 1 }],
      },
    ]);

    const calledKeys = tMock.mock.calls.map(([key]) => key);
    expect(calledKeys).toContain('custom.test.matchersTitle');
    expect(calledKeys).toContain('custom.test.matcherLabel');
    expect(calledKeys).toContain('custom.test.actionsCount');
    expect(calledKeys).toContain('custom.test.timeoutSeconds');
    expect(calledKeys).toContain('custom.test.summary.matchers');
    expect(calledKeys).not.toContain(expect.stringMatching(/^marketplace\./));
    expect(calledKeys).not.toContain(expect.stringMatching(/^workspace\./));
  });

  it('folds actions beyond the preview limit', () => {
    renderCard([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: 'echo one' },
          { type: 'command', command: 'echo two' },
          { type: 'command', command: 'echo three' },
        ],
      },
    ], { actionPreviewLimit: 2 });

    const matcher = screen.getByTestId('hook-card-matcher');
    expect(within(matcher).getAllByTestId('hook-card-action')).toHaveLength(2);
    expect(screen.getByText('custom.test.moreActions:1')).toBeInTheDocument();
  });
});
