export type TransportType = 'stdio' | 'http' | 'sse';
export type ScopeType = 'project' | 'user' | 'local';

export interface TransportOption {
  value: TransportType;
  labelKey: string;
  descriptionKey: string;
}

export const MCP_TRANSPORT_OPTIONS: TransportOption[] = [
  {
    value: 'stdio',
    labelKey: 'template.editor.mcp.dialog.transport.options.stdio.label',
    descriptionKey: 'template.editor.mcp.dialog.transport.options.stdio.description'
  },
  {
    value: 'http',
    labelKey: 'template.editor.mcp.dialog.transport.options.http.label',
    descriptionKey: 'template.editor.mcp.dialog.transport.options.http.description'
  },
  {
    value: 'sse',
    labelKey: 'template.editor.mcp.dialog.transport.options.sse.label',
    descriptionKey: 'template.editor.mcp.dialog.transport.options.sse.description'
  }
];

export const MCP_SCOPE_OPTIONS = [
  {
    value: 'project' as ScopeType,
    label: '專案',
    description: '僅在當前專案中可用'
  },
  {
    value: 'user' as ScopeType,
    label: '使用者',
    description: '在使用者層級全域可用'
  },
  {
    value: 'local' as ScopeType,
    label: '本地',
    description: '僅在本地環境可用'
  }
];