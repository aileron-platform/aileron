import { describe, expect, it } from 'vitest';
import {
  countMarketplaceFileNodes,
  getMarketplaceEditorTabLabelKey,
  getMarketplacePackageRoot,
  visibleMarketplaceEditorTabs,
} from './marketplaceEditorTabsModel';
import type { FileTreeNode } from '@/shared/components/file-workbench';

describe('marketplaceEditorTabsModel', () => {
  it('derives visible editor tabs from package-format capabilities', () => {
    const capabilities = {
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

    expect(visibleMarketplaceEditorTabs(capabilities)).toEqual(['basic', 'mcp', 'skills', 'files']);
  });

  it('resolves targetClient-specific tab label keys through i18n keys', () => {
    expect(getMarketplaceEditorTabLabelKey('claude-code', 'agentsMd')).toBe('marketplace.editor.tabs.claudeMd');
    expect(getMarketplaceEditorTabLabelKey('codex', 'commands')).toBe('marketplace.editor.tabs.slashCommand');
    expect(getMarketplaceEditorTabLabelKey('codex', 'skills')).toBe('marketplace.editor.tabs.skills');
  });

  it('builds package roots without template-center paths', () => {
    expect(getMarketplacePackageRoot('codex', 'reviewer')).toBe('codex/plugins/reviewer');
    expect(getMarketplacePackageRoot('claude-code', 'reviewer')).toBe('claude-code/plugins/reviewer');
  });

  it('counts nested package file nodes', () => {
    const nodes: FileTreeNode[] = [
      {
        id: 'root',
        name: 'root',
        path: '/root',
        type: 'folder',
        children: [
          { id: 'readme', name: 'README.md', path: '/root/README.md', type: 'file' },
          {
            id: 'skills',
            name: 'skills',
            path: '/root/skills',
            type: 'folder',
            children: [
              { id: 'skill', name: 'SKILL.md', path: '/root/skills/SKILL.md', type: 'file' },
            ],
          },
        ],
      },
    ];

    expect(countMarketplaceFileNodes(nodes)).toBe(2);
  });
});
