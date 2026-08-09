import { describe, expect, it } from 'vitest';
import {
  buildMarketplaceEditorPath,
  resolveMarketplaceEditorSection,
} from './marketplaceEditorSectionModel';

describe('marketplaceEditorSectionModel', () => {
  it('resolves a supported section', () => {
    expect(resolveMarketplaceEditorSection('claude-code', 'skills')).toBe('skills');
  });

  it('falls back to basic for unsupported or unknown sections', () => {
    expect(resolveMarketplaceEditorSection('claude-code', 'policies')).toBe('basic');
    expect(resolveMarketplaceEditorSection('codex', 'outputStyle')).toBe('basic');
    expect(resolveMarketplaceEditorSection('claude-code', undefined)).toBe('basic');
    expect(resolveMarketplaceEditorSection('claude-code', 'nope')).toBe('basic');
  });

  it('builds edit paths', () => {
    expect(buildMarketplaceEditorPath({
      provider: 'claude-code',
      packageId: 'pkg',
      section: 'skills',
    })).toBe('/marketplace/packages/claude-code/pkg/edit/skills');
  });
});
