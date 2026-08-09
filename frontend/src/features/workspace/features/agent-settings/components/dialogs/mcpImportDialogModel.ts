import { sortAgentSettingsScopeValues } from '../AgentSettingsSourceControls';

export type McpImportScope = 'project' | 'user' | 'local';
export type McpImportFileError = 'invalidFile' | 'fileTooLarge';
export type McpImportResultStatus = 'created' | 'updated' | 'skipped';

export interface McpImportResult {
  created: string[];
  updated: string[];
  skipped: string[];
}

export interface McpImportResultEntry {
  name: string;
  status: McpImportResultStatus;
}

const DEFAULT_IMPORT_SCOPES: McpImportScope[] = ['project', 'user', 'local'];
const MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024;

export const getMcpImportScopes = (availableScopes?: readonly string[]): McpImportScope[] => (
  availableScopes
    ? sortAgentSettingsScopeValues(
      availableScopes.filter((scope): scope is McpImportScope => (
        scope === 'project' || scope === 'user' || scope === 'local'
      )),
    )
    : DEFAULT_IMPORT_SCOPES
);

export const validateMcpImportFile = (file: File): McpImportFileError | null => {
  if (!file.name.endsWith('.json')) {
    return 'invalidFile';
  }
  if (file.size > MAX_IMPORT_FILE_SIZE_BYTES) {
    return 'fileTooLarge';
  }
  return null;
};

export const buildMcpImportResultEntries = (result: McpImportResult): McpImportResultEntry[] => [
  ...result.created.map((name) => ({ name, status: 'created' as const })),
  ...result.updated.map((name) => ({ name, status: 'updated' as const })),
  ...result.skipped.map((name) => ({ name, status: 'skipped' as const })),
];
