import { describe, expect, it, vi } from 'vitest';
import { createMarketplaceFileWorkbenchAdapter } from './marketplaceFileWorkbenchAdapter';
import type { MarketplacePackageFile } from '@/shared/types/marketplace';

const textFile = (path: string, content = path): MarketplacePackageFile => ({
  path,
  content,
  binary: false,
  mimeType: 'text/plain',
  size: content.length,
});

describe('marketplaceFileWorkbenchAdapter', () => {
  it('reads and writes package file content through the draft package file list', async () => {
    let files = [textFile('README.md', '# Demo')];
    const onPackageFilesChange = vi.fn((nextFiles: MarketplacePackageFile[]) => {
      files = nextFiles;
    });
    const adapter = createMarketplaceFileWorkbenchAdapter({
      provider: 'codex',
      packageId: 'demo-plugin',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      getPackageFiles: () => files,
      onPackageFilesChange,
    });

    await expect(adapter.read('/codex/plugins/demo-plugin/README.md')).resolves.toBe('# Demo');
    await adapter.write('/codex/plugins/demo-plugin/README.md', '# Updated');

    expect(onPackageFilesChange).toHaveBeenCalledWith([
      expect.objectContaining({
        path: 'README.md',
        content: '# Updated',
        size: 9,
      }),
    ]);
  });

  it('creates, renames, and deletes files using FileTreeDataAdapter-compatible methods', async () => {
    let files = [textFile('README.md', '# Demo')];
    const adapter = createMarketplaceFileWorkbenchAdapter({
      provider: 'codex',
      packageId: 'demo-plugin',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      getPackageFiles: () => files,
      onPackageFilesChange: nextFiles => {
        files = nextFiles;
      },
    });

    await adapter.create({
      type: 'create',
      path: '/codex/plugins/demo-plugin/notes.md',
      content: '# Notes',
      isDirectory: false,
    });
    expect(files).toEqual(expect.arrayContaining([expect.objectContaining({ path: 'notes.md' })]));

    await adapter.rename('/codex/plugins/demo-plugin/notes.md', '/codex/plugins/demo-plugin/archive.md');
    expect(files).toEqual(expect.arrayContaining([expect.objectContaining({ path: 'archive.md' })]));

    await adapter.delete('/codex/plugins/demo-plugin/archive.md');
    expect(files).not.toEqual(expect.arrayContaining([expect.objectContaining({ path: 'archive.md' })]));
  });

  it('loads package root children through the FileTreeDataAdapter getChildren method', async () => {
    const adapter = createMarketplaceFileWorkbenchAdapter({
      provider: 'codex',
      packageId: 'demo-plugin',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      getPackageFiles: () => [textFile('README.md', '# Demo')],
      onPackageFilesChange: vi.fn(),
    });

    await expect(adapter.getChildren('/codex/plugins/demo-plugin')).resolves.toEqual([
      expect.objectContaining({
        name: 'README.md',
        path: '/codex/plugins/demo-plugin/README.md',
      }),
    ]);
  });

  it('blocks batch delete when the adapter is read-only', async () => {
    let files = [textFile('README.md', '# Demo')];
    const onPackageFilesChange = vi.fn((nextFiles: MarketplacePackageFile[]) => {
      files = nextFiles;
    });
    const adapter = createMarketplaceFileWorkbenchAdapter({
      provider: 'codex',
      packageId: 'demo-plugin',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      getPackageFiles: () => files,
      onPackageFilesChange,
      readOnly: true,
    });

    await expect(adapter.batchDelete({ paths: ['/codex/plugins/demo-plugin/README.md'] }))
      .rejects.toThrow('marketplace.fileTree.error.readOnly');
    expect(onPackageFilesChange).not.toHaveBeenCalled();
    expect(files).toEqual([textFile('README.md', '# Demo')]);
  });

  it('exposes read-only lifecycle errors as i18n keys', async () => {
    const adapter = createMarketplaceFileWorkbenchAdapter({
      provider: 'codex',
      packageId: 'demo-plugin',
      packageRoot: 'codex/plugins/demo-plugin',
      displayName: 'Demo plugin',
      getPackageFiles: () => [textFile('README.md', '# Demo')],
      onPackageFilesChange: vi.fn(),
      readOnly: true,
    });

    await expect(adapter.write('/codex/plugins/demo-plugin/README.md', '# Updated'))
      .rejects.toThrow('marketplace.fileTree.error.readOnly');
    expect(adapter.isReadOnly({
      id: '/codex/plugins/demo-plugin/README.md',
      name: 'README.md',
      path: '/codex/plugins/demo-plugin/README.md',
      type: 'file',
    })).toBe(true);
  });
});
