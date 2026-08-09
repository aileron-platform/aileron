import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '@/shared/components/file-workbench';
import {
  buildSettingsFileTreeContextMenuFeatures,
  toSettingsFileSelection,
} from './settingsFileTreeWorkflowModel';

describe('settingsFileTreeWorkflowModel', () => {
  it('maps file tree node source metadata into the selected settings file', () => {
    const node: FileTreeNode = {
      id: '/prompts/plugin.md',
      name: 'plugin.md',
      path: '/prompts/plugin.md',
      type: 'file',
      scope: 'plugin',
      pluginId: 'demo@local',
      pluginName: 'Demo Plugin',
      marketplaceName: 'Local Marketplace',
      metadata: {
        sourcePath: 'plugin/prompts/plugin.md',
        sourceScope: 'plugin',
      },
    };

    expect(toSettingsFileSelection(node, 'project')).toEqual({
      path: 'plugin/prompts/plugin.md',
      scope: 'plugin',
      pluginId: 'demo@local',
      pluginName: 'Demo Plugin',
      marketplaceName: 'Local Marketplace',
    });
  });

  it('builds read-only context menu capabilities without write actions', () => {
    expect(buildSettingsFileTreeContextMenuFeatures(true)).toEqual({
      view: true,
      upload: false,
      createFile: false,
      createFolder: false,
      extractArchive: false,
      copy: false,
      copyPath: false,
      paste: false,
      rename: false,
      delete: false,
    });
  });

  it('builds writable context menu capabilities with file operations enabled', () => {
    expect(buildSettingsFileTreeContextMenuFeatures(false)).toEqual({
      view: false,
      upload: true,
      createFile: true,
      createFolder: true,
      extractArchive: true,
      copy: false,
      copyPath: true,
      paste: false,
      rename: true,
      delete: true,
    });
  });
});
