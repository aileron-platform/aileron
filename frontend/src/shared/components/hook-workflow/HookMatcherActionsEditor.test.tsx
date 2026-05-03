import { render, screen } from '@/__tests__/utils/render';
import { fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  HookMatcherActionsEditor,
  type HookMatcher,
  type HookMatcherActionsLabels,
} from './HookMatcherActionsEditor';

const labels: HookMatcherActionsLabels = {
  matcherSectionTitle: 'Matchers',
  matcherAdd: 'Add matcher',
  matcherPatternLabel: 'Pattern',
  matcherPatternPlaceholder: 'Pattern placeholder',
  matcherPatternHelp: ['Pattern help'],
  matcherRemove: 'Remove matcher',
  executionSectionTitle: 'Executions',
  executionAdd: 'Add execution',
  executionTimeoutLabel: 'Timeout',
  executionTimeoutPlaceholder: 'Timeout placeholder',
  executionTimeoutHelp: 'Timeout help',
  executionCommandLabel: 'Command',
  executionCommandPlaceholder: 'Command placeholder',
  executionCommandHelp: 'Command help',
  executionRemove: 'Remove execution',
};

const codexLabels: HookMatcherActionsLabels = {
  ...labels,
  executionStatusMessageLabel: 'Status message',
  executionStatusMessagePlaceholder: 'Status placeholder',
  executionStatusMessageHelp: 'Status help',
};

const metadataLabels: HookMatcherActionsLabels = {
  ...labels,
  executionNameLabel: 'Hook name',
  executionNamePlaceholder: 'Name placeholder',
  executionNameHelp: 'Name help',
  executionDescriptionLabel: 'Description',
  executionDescriptionPlaceholder: 'Description placeholder',
  executionDescriptionHelp: 'Description help',
};

const matchers: HookMatcher[] = [
  {
    matcher: '*',
    hooks: [{ type: 'command', command: 'echo test', timeout: 30 }],
  },
];

describe('HookMatcherActionsEditor', () => {
  it('adds matcher and hook execution rows without owning feature payloads', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={labels}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Add matcher' }));

    expect(onChange).toHaveBeenCalledWith([
      matchers[0],
      { matcher: '', hooks: [{ type: 'command', command: '', timeout: 30 }] },
    ]);

    onChange.mockClear();
    await user.click(screen.getByRole('button', { name: 'Add execution' }));

    expect(onChange).toHaveBeenCalledWith([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: 'echo test', timeout: 30 },
          { type: 'command', command: '', timeout: 30 },
        ],
      },
    ]);
  });

  it('updates matcher, timeout, and command fields through shared row mutations', () => {
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={labels}
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Pattern placeholder'), {
      target: { value: 'Bash' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: 'Bash',
        hooks: [{ type: 'command', command: 'echo test', timeout: 30 }],
      },
    ]);

    onChange.mockClear();
    fireEvent.change(screen.getByPlaceholderText('Timeout placeholder'), {
      target: { value: '45' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: '*',
        hooks: [{ type: 'command', command: 'echo test', timeout: 45 }],
      },
    ]);

    onChange.mockClear();
    fireEvent.change(screen.getByPlaceholderText('Command placeholder'), {
      target: { value: 'echo done' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: '*',
        hooks: [{ type: 'command', command: 'echo done', timeout: 30 }],
      },
    ]);

  });

  it('updates status message only when the caller enables the Codex-specific field', () => {
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={codexLabels}
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Status placeholder'), {
      target: { value: 'Running hook' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: '*',
        hooks: [{ type: 'command', command: 'echo test', timeout: 30, statusMessage: 'Running hook' }],
      },
    ]);
  });

  it('updates action metadata only when the caller enables metadata fields', () => {
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={metadataLabels}
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Name placeholder'), {
      target: { value: 'security-check' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: '*',
        hooks: [{ type: 'command', command: 'echo test', timeout: 30, name: 'security-check' }],
      },
    ]);

    onChange.mockClear();
    fireEvent.change(screen.getByPlaceholderText('Description placeholder'), {
      target: { value: 'Check commands before execution' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        matcher: '*',
        hooks: [
          {
            type: 'command',
            command: 'echo test',
            timeout: 30,
            description: 'Check commands before execution',
          },
        ],
      },
    ]);
  });
});
