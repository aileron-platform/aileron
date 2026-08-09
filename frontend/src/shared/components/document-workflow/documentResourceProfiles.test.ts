import { describe, expect, it } from 'vitest';
import {
  normalizeDocumentFileName,
  normalizeDocumentMetadata,
  resolveDocumentExtension,
} from './documentResourceProfiles';

describe('documentResourceProfiles', () => {
  it('resolves markdown extensions for slash commands and output styles', () => {
    expect(resolveDocumentExtension('slashCommand', 'markdown')).toBe('.md');
    expect(resolveDocumentExtension('outputStyle', 'markdown')).toBe('.md');
  });

  it('resolves subagent extension from content format', () => {
    expect(resolveDocumentExtension('subagent', 'toml')).toBe('.toml');
    expect(resolveDocumentExtension('subagent', 'markdown')).toBe('.md');
  });

  it('normalizes missing and wrong extensions while preserving directories', () => {
    expect(normalizeDocumentFileName('test', 'slashCommand', 'markdown')).toBe('test.md');
    expect(normalizeDocumentFileName('test.toml', 'slashCommand', 'markdown')).toBe('test.md');
    expect(normalizeDocumentFileName('team/test.md', 'subagent', 'toml')).toBe('team/test.toml');
    expect(normalizeDocumentFileName('team/test', 'subagent', 'toml')).toBe('team/test.toml');
  });

  it('canonicalizes relative paths before applying the extension', () => {
    expect(normalizeDocumentFileName('/team//agent.md', 'subagent', 'toml')).toBe('team/agent.toml');
    expect(normalizeDocumentFileName('team/', 'slashCommand', 'markdown')).toBe('');
  });

  it('rejects extension-only file names after normalization', () => {
    expect(normalizeDocumentFileName('.toml', 'slashCommand', 'markdown')).toBe('');
    expect(normalizeDocumentFileName('.md', 'subagent', 'toml')).toBe('');
    expect(normalizeDocumentFileName('team/.md', 'slashCommand', 'markdown')).toBe('');
    expect(normalizeDocumentFileName('/team//.toml', 'subagent', 'toml')).toBe('');
  });

  it('normalizes metadata fileName and path together', () => {
    expect(normalizeDocumentMetadata(
      { fileName: 'agent.md', path: 'team/agent.md', scope: 'project' },
      'subagent',
      'toml',
    )).toEqual({
      fileName: 'agent.toml',
      path: 'team/agent.toml',
      scope: 'project',
    });
  });

  it('keeps metadata path basename aligned with the normalized fileName', () => {
    expect(normalizeDocumentMetadata(
      { fileName: 'agent.md', path: 'team/old-agent.md', scope: 'project' },
      'subagent',
      'toml',
    )).toEqual({
      fileName: 'agent.toml',
      path: 'team/agent.toml',
      scope: 'project',
    });
  });

  it('uses only the normalized fileName basename for metadata paths', () => {
    expect(normalizeDocumentMetadata(
      { fileName: 'team/agent.md', path: 'team/old-agent.md', scope: 'project' },
      'subagent',
      'toml',
    )).toEqual({
      fileName: 'agent.toml',
      path: 'team/agent.toml',
      scope: 'project',
    });
  });

  it('preserves the fileName directory as path when metadata path is missing', () => {
    expect(normalizeDocumentMetadata(
      { fileName: 'team/agent.md', scope: 'project' },
      'subagent',
      'toml',
    )).toEqual({
      fileName: 'agent.toml',
      path: 'team/agent.toml',
      scope: 'project',
    });
  });

  it('clears metadata path when normalized fileName is empty', () => {
    expect(normalizeDocumentMetadata(
      { fileName: 'team/', path: 'team/old.md', scope: 'project' },
      'slashCommand',
      'markdown',
    )).toEqual({
      fileName: '',
      path: '',
      scope: 'project',
    });
  });
});
