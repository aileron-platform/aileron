import React from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';

export type MCPTransport = 'stdio' | 'sse' | 'http';

export interface MCPKeyValueRow {
  id: string;
  key: string;
  value: string;
}

export interface MCPTransportFieldsLabels {
  commandLabel: string;
  commandPlaceholder: string;
  argsLabel: string;
  argsAdd: string;
  argsEmpty: string;
  argsPlaceholder: (index: number) => string;
  urlLabel: string;
  urlPlaceholder: string;
  urlHint: string;
  headersLabel: string;
  headersAdd: string;
  headersKeyPlaceholder: string;
  headersValuePlaceholder: string;
  headersEmpty: string;
  headersHint?: string;
  envLabel: string;
  envAdd: string;
  envKeyPlaceholder: string;
  envValuePlaceholder: string;
  envEmpty: string;
}

export interface MCPTransportFieldsEditorProps {
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
  submitting?: boolean;
  labels: MCPTransportFieldsLabels;
  onCommandChange: (command: string) => void;
  onArgsChange: (args: string[]) => void;
  onUrlChange: (url: string) => void;
  onEnvChange: (env: MCPKeyValueRow[]) => void;
  onHeadersChange: (headers: MCPKeyValueRow[]) => void;
}

let keyValueRowCounter = 0;

export const createMCPKeyValueRow = (key = '', value = ''): MCPKeyValueRow => ({
  id: `mcp-kv-row-${keyValueRowCounter++}`,
  key,
  value,
});

export const createMCPKeyValueRows = (record?: Record<string, string>): MCPKeyValueRow[] =>
  Object.entries(record ?? {}).map(([key, value]) => createMCPKeyValueRow(key, value));

export const parseMCPArgsText = (text: string): string[] =>
  text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

export const toMCPKeyValueRecord = (rows: MCPKeyValueRow[]): Record<string, string> =>
  Object.fromEntries(
    rows
      .map(({ key, value }) => [key.trim(), value] as const)
      .filter(([key]) => key.length > 0),
  );

export const MCPTransportFieldsEditor: React.FC<MCPTransportFieldsEditorProps> = ({
  transport,
  command,
  args,
  url,
  env,
  headers,
  submitting = false,
  labels,
  onCommandChange,
  onArgsChange,
  onUrlChange,
  onEnvChange,
  onHeadersChange,
}) => {
  const updateRow = (
    rows: MCPKeyValueRow[],
    rowId: string,
    field: 'key' | 'value',
    value: string,
  ): MCPKeyValueRow[] =>
    rows.map((row) => (row.id === rowId ? { ...row, [field]: value } : row));

  return (
    <>
      {transport === 'stdio' ? (
        <>
          <div className="space-y-2">
            <Label>{labels.commandLabel}</Label>
            <Input
              value={command}
              onChange={(event) => onCommandChange(event.target.value)}
              placeholder={labels.commandPlaceholder}
              className="font-mono"
              required
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{labels.argsLabel}</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onArgsChange([...args, ''])}
                disabled={submitting}
              >
                <Plus className="mr-1 h-4 w-4" />
                {labels.argsAdd}
              </Button>
            </div>
            <div className="space-y-2">
              {args.map((arg, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    value={arg}
                    onChange={(event) => {
                      onArgsChange(args.map((currentArg, currentIndex) => (
                        currentIndex === index ? event.target.value : currentArg
                      )));
                    }}
                    placeholder={labels.argsPlaceholder(index + 1)}
                    className="font-mono"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onArgsChange(args.filter((_, currentIndex) => currentIndex !== index))}
                    disabled={submitting}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              {args.length === 0 ? (
                <p className="text-sm text-muted-foreground">{labels.argsEmpty}</p>
              ) : null}
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="space-y-2">
            <Label>{labels.urlLabel}</Label>
            <Input
              value={url}
              onChange={(event) => onUrlChange(event.target.value)}
              placeholder={labels.urlPlaceholder}
              className="font-mono"
              required
            />
            <p className="text-xs text-muted-foreground">{labels.urlHint}</p>
          </div>

          <MCPKeyValueRowsEditor
            rows={headers}
            separator=":"
            label={labels.headersLabel}
            addLabel={labels.headersAdd}
            keyPlaceholder={labels.headersKeyPlaceholder}
            valuePlaceholder={labels.headersValuePlaceholder}
            emptyLabel={labels.headersEmpty}
            hint={labels.headersHint}
            submitting={submitting}
            onChange={onHeadersChange}
            updateRow={updateRow}
          />
        </>
      )}

      <MCPKeyValueRowsEditor
        rows={env}
        separator="="
        label={labels.envLabel}
        addLabel={labels.envAdd}
        keyPlaceholder={labels.envKeyPlaceholder}
        valuePlaceholder={labels.envValuePlaceholder}
        emptyLabel={labels.envEmpty}
        submitting={submitting}
        onChange={onEnvChange}
        updateRow={updateRow}
      />
    </>
  );
};

interface MCPKeyValueRowsEditorProps {
  rows: MCPKeyValueRow[];
  separator: ':' | '=';
  label: string;
  addLabel: string;
  keyPlaceholder: string;
  valuePlaceholder: string;
  emptyLabel: string;
  hint?: string;
  submitting: boolean;
  updateRow: (
    rows: MCPKeyValueRow[],
    rowId: string,
    field: 'key' | 'value',
    value: string,
  ) => MCPKeyValueRow[];
  onChange: (rows: MCPKeyValueRow[]) => void;
}

const MCPKeyValueRowsEditor: React.FC<MCPKeyValueRowsEditorProps> = ({
  rows,
  separator,
  label,
  addLabel,
  keyPlaceholder,
  valuePlaceholder,
  emptyLabel,
  hint,
  submitting,
  updateRow,
  onChange,
}) => (
  <div className="space-y-2">
    <div className="flex items-center justify-between">
      <Label>{label}</Label>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...rows, createMCPKeyValueRow()])}
        disabled={submitting}
      >
        <Plus className="mr-1 h-4 w-4" />
        {addLabel}
      </Button>
    </div>
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.id} className="flex items-center gap-2">
          <Input
            value={row.key}
            onChange={(event) => onChange(updateRow(rows, row.id, 'key', event.target.value))}
            placeholder={keyPlaceholder}
            className="flex-1 font-mono"
          />
          <span className="text-muted-foreground">{separator}</span>
          <Input
            value={row.value}
            onChange={(event) => onChange(updateRow(rows, row.id, 'value', event.target.value))}
            placeholder={valuePlaceholder}
            className="flex-1 font-mono"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange(rows.filter((currentRow) => currentRow.id !== row.id))}
            disabled={submitting}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">{emptyLabel}</p> : null}
    </div>
    {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
  </div>
);
