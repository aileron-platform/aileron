import { describe, expect, it } from 'vitest';
import {
  buildMcpImportResultEntries,
  getMcpImportScopes,
  validateMcpImportFile,
} from './mcpImportDialogModel';

describe('mcpImportDialogModel', () => {
  it('filters unsupported scopes and keeps the shared scope order', () => {
    expect(getMcpImportScopes(['plugin', 'local', 'project'])).toEqual(['project', 'local']);
    expect(getMcpImportScopes(undefined)).toEqual(['project', 'user', 'local']);
  });

  it('validates json file extension and max size', () => {
    expect(validateMcpImportFile(new File(['{}'], 'servers.json'))).toBeNull();
    expect(validateMcpImportFile(new File(['{}'], 'servers.txt'))).toBe('invalidFile');
    expect(validateMcpImportFile(new File([new Uint8Array((5 * 1024 * 1024) + 1)], 'servers.json')))
      .toBe('fileTooLarge');
  });

  it('flattens import result entries by status order', () => {
    expect(buildMcpImportResultEntries({
      created: ['alpha'],
      updated: ['beta'],
      skipped: ['gamma'],
    })).toEqual([
      { name: 'alpha', status: 'created' },
      { name: 'beta', status: 'updated' },
      { name: 'gamma', status: 'skipped' },
    ]);
  });
});
