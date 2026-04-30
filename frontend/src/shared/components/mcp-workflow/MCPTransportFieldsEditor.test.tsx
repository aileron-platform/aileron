import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  MCPTransportFieldsEditor,
  createMCPKeyValueRow,
  parseMCPArgsText,
  parseMCPKeyValueText,
  toMCPKeyValueRecord,
  toMCPKeyValueText,
  type MCPKeyValueRow,
  type MCPTransportFieldsLabels,
} from './MCPTransportFieldsEditor';

const labels: MCPTransportFieldsLabels = {
  commandLabel: 'Command',
  commandPlaceholder: 'Command placeholder',
  argsLabel: 'Arguments',
  argsAdd: 'Add argument',
  argsEmpty: 'No arguments',
  argsPlaceholder: (index) => `Argument ${index}`,
  urlLabel: 'URL',
  urlPlaceholder: 'URL placeholder',
  urlHint: 'URL hint',
  headersLabel: 'Headers',
  headersAdd: 'Add header',
  headersKeyPlaceholder: 'Header key',
  headersValuePlaceholder: 'Header value',
  headersEmpty: 'No headers',
  headersHint: 'Headers hint',
  envLabel: 'Environment',
  envAdd: 'Add environment',
  envKeyPlaceholder: 'Environment key',
  envValuePlaceholder: 'Environment value',
  envEmpty: 'No environment',
};

interface HarnessProps {
  initialEnv?: MCPKeyValueRow[];
  initialHeaders?: MCPKeyValueRow[];
  transport?: 'stdio' | 'sse' | 'http';
}

const Harness: React.FC<HarnessProps> = ({
  initialEnv = [],
  initialHeaders = [],
  transport = 'stdio',
}) => {
  const [command, setCommand] = React.useState('npx');
  const [args, setArgs] = React.useState<string[]>([]);
  const [url, setUrl] = React.useState('https://example.com/mcp');
  const [env, setEnv] = React.useState(initialEnv);
  const [headers, setHeaders] = React.useState(initialHeaders);

  return (
    <MCPTransportFieldsEditor
      transport={transport}
      command={command}
      args={args}
      url={url}
      env={env}
      headers={headers}
      labels={labels}
      onCommandChange={setCommand}
      onArgsChange={setArgs}
      onUrlChange={setUrl}
      onEnvChange={setEnv}
      onHeadersChange={setHeaders}
    />
  );
};

describe('MCPTransportFieldsEditor', () => {
  it('parses and serializes args and key-value text without owner schemas', () => {
    expect(parseMCPArgsText('\n--stdio\n  --debug  \n')).toEqual(['--stdio', '--debug']);

    expect(parseMCPKeyValueText('Authorization: Bearer token:extra\nX-Test: yes', ':')).toEqual({
      Authorization: 'Bearer token:extra',
      'X-Test': 'yes',
    });

    expect(parseMCPKeyValueText('FOO=bar=baz\nEMPTY=\n=ignored', '=')).toEqual({
      FOO: 'bar=baz',
      EMPTY: '',
    });

    expect(toMCPKeyValueRecord([
      createMCPKeyValueRow(' FOO ', 'bar'),
      createMCPKeyValueRow('', 'ignored'),
    ])).toEqual({ FOO: 'bar' });

    expect(toMCPKeyValueText({ Authorization: 'Bearer token', Empty: '' }, ': ')).toBe(
      'Authorization: Bearer token',
    );
  });

  it('keeps environment input focus while updating a controlled row', async () => {
    const user = userEvent.setup();

    render(<Harness initialEnv={[createMCPKeyValueRow('FOO', 'bar')]} />);

    const envKeyInput = screen.getByDisplayValue('FOO');

    await user.click(envKeyInput);
    await user.type(envKeyInput, 'BAR');

    expect(envKeyInput).toHaveValue('FOOBAR');
    expect(document.activeElement).toBe(envKeyInput);
  });

  it('adds and updates HTTP header rows through shared row state', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <MCPTransportFieldsEditor
        transport="http"
        command=""
        args={[]}
        url="https://example.com/mcp"
        env={[]}
        headers={[]}
        labels={labels}
        onCommandChange={vi.fn()}
        onArgsChange={vi.fn()}
        onUrlChange={vi.fn()}
        onEnvChange={vi.fn()}
        onHeadersChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Add header' }));

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ key: '', value: '' }),
    ]);
  });
});
