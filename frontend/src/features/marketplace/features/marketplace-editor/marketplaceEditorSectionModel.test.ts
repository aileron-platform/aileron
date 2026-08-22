import { describe, expect, it } from 'vitest';
import {
  buildMarketplaceEditorPath,
  resolveMarketplaceEditorSection,
} from './marketplaceEditorSectionModel';

describe('marketplaceEditorSectionModel', () => {
  const agentPluginCapabilities = {
    basic: 'read-write',
    agentsMd: 'unsupported',
    hooks: 'unsupported',
    mcp: 'read-write',
    agents: 'unsupported',
    commands: 'unsupported',
    outputStyle: 'unsupported',
    skills: 'read-write',
    files: 'read-write',
  } as const;

  it('resolves a supported section', () => {
    expect(resolveMarketplaceEditorSection(agentPluginCapabilities, 'skills')).toBe('skills');
  });

  it('falls back to basic for unsupported or unknown sections', () => {
    expect(resolveMarketplaceEditorSection(agentPluginCapabilities, 'policies')).toBe('basic');
    expect(resolveMarketplaceEditorSection(agentPluginCapabilities, 'outputStyle')).toBe('basic');
    expect(resolveMarketplaceEditorSection(agentPluginCapabilities, undefined)).toBe('basic');
    expect(resolveMarketplaceEditorSection(agentPluginCapabilities, 'nope')).toBe('basic');
  });

  it('builds edit paths', () => {
    expect(buildMarketplaceEditorPath({
      targetClient: 'claude-code',
      packageFormat: 'claude-native',
      packageId: 'pkg',
      section: 'skills',
    })).toBe('/marketplace/packages/claude-code/pkg/edit/skills?packageFormat=claude-native');
  });
});
