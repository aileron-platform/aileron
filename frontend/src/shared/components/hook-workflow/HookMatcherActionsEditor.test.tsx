import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HookMatcherActionsEditor,
  type HookMatcherActionsLabels,
} from './HookMatcherActionsEditor';
import type { HookActionConfig, HookMatcher } from './model/hookTypes';

const labels: HookMatcherActionsLabels = {
  matcherSectionTitle: 'Matchers',
  matcherAdd: 'Add matcher',
  matcherPatternLabel: 'Pattern',
  matcherPatternPlaceholder: 'Pattern placeholder',
  matcherPatternHelp: ['Pattern help'],
  matcherRemove: 'Remove matcher',
  executionSectionTitle: 'Executions',
  executionAdd: 'Add execution',
  executionTypeLabel: 'Execution type',
  executionTypeOptions: [
    { value: 'command', label: 'Command type' },
    { value: 'http', label: 'HTTP type' },
    { value: 'mcp_tool', label: 'MCP tool type' },
    { value: 'prompt', label: 'Prompt type' },
    { value: 'agent', label: 'Agent type' },
  ],
  executionTimeoutLabel: 'Timeout',
  executionTimeoutPlaceholder: 'Timeout placeholder',
  executionTimeoutHelp: 'Timeout help',
  executionConditionLabel: 'Condition',
  executionConditionPlaceholder: 'Condition placeholder',
  executionConditionHelp: 'Condition help',
  executionCommandLabel: 'Command',
  executionCommandPlaceholder: 'Command placeholder',
  executionCommandHelp: 'Command help',
  executionUrlLabel: 'URL',
  executionUrlPlaceholder: 'URL placeholder',
  executionUrlHelp: 'URL help',
  executionHeadersLabel: 'Headers',
  executionHeadersHelp: 'Headers help',
  executionHeaderKeyPlaceholder: 'Header key placeholder',
  executionHeaderValuePlaceholder: 'Header value placeholder',
  executionHeadersAdd: 'Add header',
  executionHeadersRemove: 'Remove header',
  executionAllowedEnvVarsLabel: 'Allowed environment variables',
  executionAllowedEnvVarsPlaceholder: 'Allowed environment variables placeholder',
  executionAllowedEnvVarsHelp: 'Allowed environment variables help',
  executionServerLabel: 'Server',
  executionServerPlaceholder: 'Server placeholder',
  executionServerHelp: 'Server help',
  executionToolLabel: 'Tool',
  executionToolPlaceholder: 'Tool placeholder',
  executionToolHelp: 'Tool help',
  executionInputLabel: 'Input',
  executionInputPlaceholder: 'Input placeholder',
  executionInputHelp: 'Input help',
  executionPromptLabel: 'Prompt',
  executionPromptPlaceholder: 'Prompt placeholder',
  executionPromptHelp: 'Prompt help',
  executionModelLabel: 'Model',
  executionModelPlaceholder: 'Model placeholder',
  executionModelHelp: 'Model help',
  executionAsyncLabel: 'Async',
  executionAsyncRewakeLabel: 'Async rewake',
  executionShellLabel: 'Shell',
  executionShellPlaceholder: 'Shell placeholder',
  executionShellHelp: 'Shell help',
  executionShellOptions: [
    { value: 'bash', label: 'Bash' },
    { value: 'powershell', label: 'PowerShell' },
  ],
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

const renderControlledEditor = (
  initialMatchers: HookMatcher[],
  options: {
    provider?: 'claude-code' | 'codex';
    eventName?: string;
  } = {},
) => {
  const Harness: React.FC = () => {
    const [value, setValue] = React.useState(initialMatchers);
    return (
      <>
        <HookMatcherActionsEditor
          matchers={value}
          labels={labels}
          provider={options.provider}
          eventName={options.eventName}
          onChange={setValue}
        />
        <output data-testid="matcher-state">{JSON.stringify(value)}</output>
      </>
    );
  };

  return render(<Harness />);
};

describe('HookMatcherActionsEditor', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
  });

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

  it('uses injected factories for new matcher and execution rows', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={labels}
        createEmptyMatcher={() => ({
          matcher: 'Bash',
          hooks: [{ type: 'command', command: 'echo injected', timeout: 60, shell: 'bash' }],
        })}
        createEmptyExecution={() => ({
          type: 'command',
          command: 'opencode run check',
          timeout: 60000,
        })}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Add matcher' }));

    expect(onChange).toHaveBeenCalledWith([
      matchers[0],
      {
        matcher: 'Bash',
        hooks: [{ type: 'command', command: 'echo injected', timeout: 60, shell: 'bash' }],
      },
    ]);

    onChange.mockClear();
    await user.click(screen.getByRole('button', { name: 'Add execution' }));

    expect(onChange).toHaveBeenCalledWith([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: 'echo test', timeout: 30 },
          { type: 'command', command: 'opencode run check', timeout: 60000 },
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

  it('renders action metadata fields for providers that support them', () => {
    const onChange = vi.fn();

    render(
      <HookMatcherActionsEditor
        matchers={matchers}
        labels={metadataLabels}
        provider="claude-code"
        onChange={onChange}
      />,
    );

    expect(screen.getByPlaceholderText('Name placeholder')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Description placeholder')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it.each<{
    action: HookActionConfig;
    visiblePlaceholders: string[];
  }>([
    {
      action: { type: 'command', command: 'echo test', timeout: 600 },
      visiblePlaceholders: ['Command placeholder'],
    },
    {
      action: {
        type: 'http',
        url: 'https://example.test/hook',
        headers: {},
        allowedEnvVars: [],
        timeout: 30,
      },
      visiblePlaceholders: [
        'URL placeholder',
        'Header key placeholder',
        'Header value placeholder',
        'Allowed environment variables placeholder',
      ],
    },
    {
      action: {
        type: 'mcp_tool',
        server: 'tools',
        tool: 'review',
        input: {},
        timeout: 60,
      },
      visiblePlaceholders: ['Server placeholder', 'Tool placeholder', 'Input placeholder'],
    },
    {
      action: { type: 'prompt', prompt: 'Review this change', model: 'sonnet', timeout: 30 },
      visiblePlaceholders: ['Prompt placeholder', 'Model placeholder'],
    },
    {
      action: { type: 'agent', prompt: 'Run the task', model: 'sonnet', timeout: 60 },
      visiblePlaceholders: ['Prompt placeholder', 'Model placeholder'],
    },
  ])('renders only the fields supported by the $action.type action', ({ action, visiblePlaceholders }) => {
    const actionPlaceholders = [
      'Command placeholder',
      'URL placeholder',
      'Header key placeholder',
      'Header value placeholder',
      'Allowed environment variables placeholder',
      'Server placeholder',
      'Tool placeholder',
      'Input placeholder',
      'Prompt placeholder',
      'Model placeholder',
    ];

    render(
      <HookMatcherActionsEditor
        matchers={[{ matcher: '*', hooks: [action] }]}
        labels={labels}
        provider="claude-code"
        eventName="Stop"
        onChange={vi.fn()}
      />,
    );

    visiblePlaceholders.forEach((placeholder) => {
      expect(screen.getByPlaceholderText(placeholder)).toBeInTheDocument();
    });
    actionPlaceholders
      .filter((placeholder) => !visiblePlaceholders.includes(placeholder))
      .forEach((placeholder) => {
        expect(screen.queryByPlaceholderText(placeholder)).not.toBeInTheDocument();
      });
  });

  it('adds, edits, and removes HTTP headers through the matcher callback', async () => {
    const user = userEvent.setup();
    renderControlledEditor([
      {
        matcher: '*',
        hooks: [{
          type: 'http',
          url: 'https://example.test/hook',
          headers: { Authorization: 'Bearer old' },
          allowedEnvVars: [],
          timeout: 30,
        }],
      },
    ], { provider: 'claude-code' });

    fireEvent.change(screen.getByPlaceholderText('Header value placeholder'), {
      target: { value: 'Bearer new' },
    });
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"Authorization":"Bearer new"');

    await user.click(screen.getByRole('button', { name: 'Add header' }));
    const headerKeyInputs = screen.getAllByPlaceholderText('Header key placeholder');
    fireEvent.change(headerKeyInputs[1], { target: { value: 'X-Test' } });
    const headerValueInputs = screen.getAllByPlaceholderText('Header value placeholder');
    fireEvent.change(headerValueInputs[1], { target: { value: 'enabled' } });
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"X-Test":"enabled"');

    await user.click(screen.getAllByRole('button', { name: 'Remove header' })[1]);
    expect(screen.getByTestId('matcher-state')).not.toHaveTextContent('"X-Test"');
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"Authorization":"Bearer new"');
  });

  it('keeps Claude condition, async coupling, and shell callbacks unchanged', async () => {
    const user = userEvent.setup();
    renderControlledEditor([
      {
        matcher: 'Bash',
        hooks: [{
          type: 'command',
          command: 'echo test',
          timeout: 600,
          shell: 'bash',
          async: false,
          asyncRewake: false,
        }],
      },
    ], { provider: 'claude-code', eventName: 'PreToolUse' });

    fireEvent.change(screen.getByPlaceholderText('Condition placeholder'), {
      target: { value: 'tool == "Bash"' },
    });
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"if":"tool == \\"Bash\\""');

    await user.click(screen.getByLabelText('Async rewake'));
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"async":true');
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"asyncRewake":true');

    await user.click(screen.getByLabelText('Async'));
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"async":false');
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"asyncRewake":false');

    const shellSelect = screen.getAllByRole('combobox')[1];
    await user.click(shellSelect);
    await user.click(await screen.findByRole('option', { name: 'PowerShell' }));
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('"shell":"powershell"');
  });

  it('removes the selected action while preserving the remaining action', async () => {
    const user = userEvent.setup();
    renderControlledEditor([
      {
        matcher: '*',
        hooks: [
          { type: 'command', command: 'echo first', timeout: 30 },
          { type: 'command', command: 'echo second', timeout: 30 },
        ],
      },
    ]);

    await user.click(screen.getAllByRole('button', { name: 'Remove execution' })[0]);

    expect(screen.getByTestId('matcher-state')).not.toHaveTextContent('echo first');
    expect(screen.getByTestId('matcher-state')).toHaveTextContent('echo second');
  });
});
