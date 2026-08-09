import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { HookDialog } from './HookDialog';
import {
  createHookDialogTestLabels,
  createHookDialogTestOptions,
} from './__tests__/HookDialog.fixtures';
import type { HookDialogData } from './model/hookDialogModel';

const baseHook = (eventName: string): HookDialogData => ({
  id: `project:${eventName}`,
  scope: 'project',
  eventName,
  matchers: [{ matcher: '', hooks: [{ type: 'command', command: 'echo hi' }] }],
});

describe('HookDialog matcher hints', () => {
  it('does not resolve matcher help for events without matcher support', () => {
    const matcherPatternHelp = vi.fn(() => ['Matcher help']);

    render(
      <HookDialog
        provider="claude-code"
        open
        mode="edit"
        hook={baseHook('Stop')}
        labels={createHookDialogTestLabels(matcherPatternHelp)}
        options={createHookDialogTestOptions()}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(matcherPatternHelp).not.toHaveBeenCalledWith('Stop');
    expect(screen.getByText('Matcher is unsupported.')).toBeInTheDocument();
  });

  it('resolves matcher help for events that support a matcher', () => {
    const matcherPatternHelp = vi.fn(() => ['Tool matcher help']);

    render(
      <HookDialog
        provider="claude-code"
        open
        mode="edit"
        hook={baseHook('PreToolUse')}
        labels={createHookDialogTestLabels(matcherPatternHelp)}
        options={createHookDialogTestOptions()}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(matcherPatternHelp).toHaveBeenCalledWith('PreToolUse');
    expect(screen.getByText('Tool matcher help')).toBeInTheDocument();
  });
});
