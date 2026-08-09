import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  MarketplacePluginCommandResult,
  MarketplaceUserCopyApplyResult,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import type { MarketplacePackageMutationResult } from '../model/marketplaceMutation';
import {
  createPackageFileEntry,
  createPackage,
  createMCPServer,
  createSkillEntry,
  deletePackageFileEntry,
  deletePackage,
  deleteMCPServer,
  deleteSkillEntry,
  exportPackage,
  getMCPServer,
  installMarketplacePlugin,
  createMarketplaceUserCopy,
  listMarketplaceActivity,
  preflightMarketplaceUserCopy,
  listPackageFilesTree,
  getPackage,
  getRegistrySettings,
  importCandidates,
  loadPackageFile,
  loadSkillFile,
  listPackages,
  listSkillTree,
  movePackageFileEntry,
  moveSkillEntry,
  savePackageFile,
  saveMCPServer,
  saveRegistrySettings,
  saveRootDocument,
  saveSkillFile,
  scanImportSource,
  preflightMarketplaceSkillFileConflicts,
  executeMarketplaceSkillFileConflictOperation,
  uploadImportSource,
} from './marketplaceApi';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  getBlob: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

const mutationResult = (
  path: string,
  revision: string,
): MarketplacePackageMutationResult => ({
  success: true,
  path,
  revision,
  ownerFilePath: null,
  baseEntryFingerprint: null,
});

describe('marketplaceApi backend boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('passes package listing filters to the backend query string', async () => {
    apiClientMock.get.mockResolvedValueOnce({ items: [], total: 0, page: 2, pageSize: 20, totalPages: 0 });

    await listPackages({
      q: 'figma',
      provider: 'codex',
      packageType: 'plugin',
      category: 'design',
      features: ['mcp', 'skills'],
      validationSeverity: 'warning',
      sourceType: 'imported',
      updatedFrom: '2026-05-01T00:00:00.000Z',
      updatedTo: '2026-05-07T00:00:00.000Z',
      sort: 'displayName',
      direction: 'asc',
      page: 2,
      pageSize: 20,
    });

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/marketplace/packages?q=figma&provider=codex&packageType=plugin&category=design&features=mcp&features=skills&validationSeverity=warning&sourceType=imported&updatedFrom=2026-05-01T00%3A00%3A00.000Z&updatedTo=2026-05-07T00%3A00%3A00.000Z&sort=displayName&direction=asc&page=2&pageSize=20',
    );
  });

  it('uses provider-native package endpoints', async () => {
    apiClientMock.get.mockResolvedValueOnce({ packageId: 'review-assistant' });
    apiClientMock.post.mockResolvedValueOnce({ packageId: 'new-plugin' });
    apiClientMock.delete.mockResolvedValueOnce({ deleted: true });
    apiClientMock.getBlob.mockResolvedValueOnce(new Blob(['zip'], { type: 'application/zip' }));

    await getPackage('claude-code', 'review-assistant');
    await createPackage({
      provider: 'codex',
      packageId: 'new-plugin',
      displayName: 'New Plugin',
      description: 'New package',
    });
    await deletePackage({ provider: 'codex', packageId: 'new-plugin', revision: 'rev-1' });
    await exportPackage({ provider: 'claude-code', packageId: 'workspace-tools', revision: 'rev-2' });

    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/packages/claude-code/review-assistant');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages', {
      provider: 'codex',
      packageId: 'new-plugin',
      displayName: 'New Plugin',
      description: 'New package',
    });
    expect(apiClientMock.delete).toHaveBeenCalledWith('/marketplace/packages/codex/new-plugin?revision=rev-1');
    expect(apiClientMock.getBlob).toHaveBeenCalledWith('/marketplace/packages/claude-code/workspace-tools/export?revision=rev-2');
  });

  it('uses one-shot plugin install, user-copy, activity, and settings endpoints', async () => {
    const installResponse: MarketplacePluginCommandResult = {
      status: 'installed',
      provider: 'codex',
      packageId: 'figma-context',
      marketplaceId: 'team-tools',
      workspaceId: 'workspace-1',
      operationId: 'a'.repeat(32),
      stage: 'completed',
      exitCode: 0,
      cliMessage: 'Installed',
      stdout: null,
      stderr: null,
      truncated: false,
    };
    const userCopyPreflightResponse: MarketplaceUserCopyPreflightResult = {
      status: 'confirmation-required',
      provider: 'codex',
      packageId: 'figma-context',
      workspaceId: 'workspace-1',
      sourceDigest: 'source',
      profileDigest: 'profile',
      materializationDigest: 'materialization',
      resources: [],
      conflicts: [],
      blockingIssues: [],
    };
    const userCopyResponse: MarketplaceUserCopyApplyResult = {
      status: 'completed',
      operationId: 'copy-1',
      provider: 'codex',
      packageId: 'figma-context',
      workspaceId: 'workspace-1',
      createdCount: 1,
      mergedCount: 2,
      unchangedCount: 3,
      overwrittenCount: 4,
    };
    apiClientMock.post
      .mockResolvedValueOnce(installResponse)
      .mockResolvedValueOnce(userCopyPreflightResponse)
      .mockResolvedValueOnce(userCopyResponse);
    apiClientMock.get
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ displayName: 'Registry' });
    apiClientMock.put.mockResolvedValueOnce({ settings: { displayName: 'Registry' } });

    const installRequest = {
      provider: 'codex' as const,
      packageId: 'figma-context',
      revision: 'rev',
      workspaceId: 'workspace-1',
    };
    const installResult = await installMarketplacePlugin(installRequest);
    const userCopyPreflight = await preflightMarketplaceUserCopy(installRequest);
    const userCopyResult = await createMarketplaceUserCopy({
      ...installRequest,
      expectedSourceDigest: 'source',
      expectedMaterializationDigest: 'materialization',
      overwriteApprovals: [{
        targetIdentity: 'skill:figma',
        expectedRevision: 'target-r1',
      }],
    });
    await listMarketplaceActivity({
      page: 2,
      pageSize: 25,
      workspaceId: 'workspace-1',
      provider: 'codex',
      packageId: 'figma-context',
      action: 'install',
      status: 'succeeded',
    });
    await getRegistrySettings();
    await saveRegistrySettings({
      name: 'Registry',
      owner: { name: 'Maintainer', email: 'maintainer@example.local' },
      description: 'Registry description',
    });

    expect(installResult).toBe(installResponse);
    expect(userCopyPreflight).toBe(userCopyPreflightResponse);
    expect(userCopyResult).toBe(userCopyResponse);
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/marketplace/plugins/install',
      installRequest,
    );
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/marketplace/user-copies/preflight',
      installRequest,
    );
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/marketplace/user-copies',
      {
        ...installRequest,
        expectedSourceDigest: 'source',
        expectedMaterializationDigest: 'materialization',
        overwriteApprovals: [{
          targetIdentity: 'skill:figma',
          expectedRevision: 'target-r1',
        }],
      },
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/marketplace/activities?page=2&pageSize=25&workspaceId=workspace-1&provider=codex&packageId=figma-context&action=install&status=succeeded',
    );
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/settings');
    expect(apiClientMock.put).toHaveBeenCalledWith('/marketplace/settings', {
      name: 'Registry',
      owner: { name: 'Maintainer', email: 'maintainer@example.local' },
      description: 'Registry description',
    });
  });

  it('sends scanned import source with selected candidates', async () => {
    const source = { provider: 'codex' as const, sourceKind: 'git' as const, source: 'git@example.com:org/repo.git' };
    const candidates = [{
      id: 'codex:figma',
      provider: 'codex' as const,
      packageId: 'figma-context',
      displayName: 'Figma Context',
      sourcePath: '/tmp/source/figma-context',
      duplicate: false,
      duplicateAction: 'skip' as const,
      variantStatus: 'new-family' as const,
      variants: [],
      validationSeverity: 'none' as const,
      validationResults: [],
    }];
    apiClientMock.post.mockResolvedValueOnce(candidates);
    apiClientMock.post.mockResolvedValueOnce({ imported: [], skipped: [], failed: [], warnings: [] });

    await scanImportSource(source);
    await importCandidates(candidates);

    expect(apiClientMock.post).toHaveBeenNthCalledWith(1, '/marketplace/import/scan', source);
    expect(apiClientMock.post).toHaveBeenNthCalledWith(2, '/marketplace/import', { source, candidates });
  });

  it('uploads a local import archive as form data', async () => {
    apiClientMock.post.mockResolvedValueOnce({
      source: { provider: 'codex', sourceKind: 'local', source: '/managed/import-source' },
      fileName: 'marketplace.zip',
    });
    const file = new File(['zip'], 'marketplace.zip', { type: 'application/zip' });

    await uploadImportSource('codex', file);

    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/import/upload', expect.any(FormData));
    const formData = apiClientMock.post.mock.calls[0][1] as FormData;
    expect(formData.get('provider')).toBe('codex');
    expect(formData.get('file')).toBe(file);
  });

  it('uses the managed skill conflict routes with revision and exact batch fields', async () => {
    const signal = new AbortController().signal;
    const request = { operation: 'upload' as const, targetPath: 'skills', sources: [{ sourcePath: 'SKILL.md', entryType: 'file' as const }], archivePath: null };
    apiClientMock.post.mockResolvedValueOnce({ conflicts: [], total: 1 });
    await preflightMarketplaceSkillFileConflicts('codex', 'toolkit', 'rev-1', request, { signal });
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/marketplace/packages/codex/toolkit/skills/conflicts/preflight',
      { ...request, revision: 'rev-1' },
      { signal },
    );

    apiClientMock.post.mockResolvedValueOnce({ items: [], total: 1, succeeded: 1, skipped: 0, failed: 0 });
    await executeMarketplaceSkillFileConflictOperation('codex', 'toolkit', {
      ...request,
      defaultStrategy: 'cancel',
      resolutions: [],
      payload: { revision: 'rev-1', files: [new File(['skill'], 'SKILL.md')] },
    }, { signal });
    const [path, formData, options] = apiClientMock.post.mock.calls[1] as [string, FormData, { signal: AbortSignal }];
    expect(path).toBe('/marketplace/packages/codex/toolkit/skills/upload');
    expect(formData.get('revision')).toBe('rev-1');
    expect(formData.get('defaultStrategy')).toBe('cancel');
    expect(formData.get('resolutions')).toBe('[]');
    expect(options).toEqual({ signal });
  });

  it('saves root document through package scoped endpoint', async () => {
    apiClientMock.put.mockResolvedValueOnce(mutationResult('AGENTS.md', 'rev2'));

    await saveRootDocument('codex', 'demo', { revision: 'rev1', content: '# Rules' });

    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/root-document',
      { revision: 'rev1', content: '# Rules' },
    );
  });

  it('uses canonical source tokens for MCP server reads and updates', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      name: 'team/server one',
      path: '.mcp.json',
      server: { command: 'node' },
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    });
    apiClientMock.put.mockResolvedValueOnce(mutationResult('.mcp.json', 'rev2'));

    await getMCPServer('codex', 'demo', 'team/server one', '.mcp.json');
    await saveMCPServer('codex', 'demo', 'team/server one', {
      revision: 'rev1',
      server: { command: 'node' },
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    });

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/mcp-servers/team%2Fserver%20one?ownerFilePath=.mcp.json',
    );
    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/mcp-servers/team%2Fserver%20one',
      {
        revision: 'rev1',
        server: { command: 'node' },
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'entry-fp',
      },
    );
  });

  it('creates and deletes MCP servers through package scoped endpoints', async () => {
    apiClientMock.post.mockResolvedValueOnce(
      mutationResult('.mcp.json#local', 'rev2'),
    );
    apiClientMock.delete.mockResolvedValueOnce(
      mutationResult('.mcp.json#local', 'rev3'),
    );

    await createMCPServer('codex', 'demo', {
      revision: 'rev1',
      name: 'local',
      server: { command: 'node' },
    });
    await deleteMCPServer('codex', 'demo', 'local server', {
      revision: 'rev2',
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/mcp-servers',
      { revision: 'rev1', name: 'local', server: { command: 'node' } },
    );
    expect(apiClientMock.delete).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/mcp-servers/local%20server',
      undefined,
      {
        revision: 'rev2',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'entry-fp',
      },
    );
  });

  it('uses package-scoped skills and files resource endpoints', async () => {
    apiClientMock.get.mockResolvedValue({});
    apiClientMock.post.mockResolvedValue(mutationResult('resource', 'rev-next'));
    apiClientMock.put.mockResolvedValue(mutationResult('resource', 'rev-next'));
    apiClientMock.delete.mockResolvedValue(mutationResult('resource', 'rev-next'));

    await listSkillTree('codex', 'demo');
    await loadSkillFile('codex', 'demo', 'skills/example/SKILL.md');
    await saveSkillFile('codex', 'demo', 'skills/example/SKILL.md', {
      revision: 'rev1',
      content: '# Skill',
    });
    await createSkillEntry('codex', 'demo', {
      revision: 'rev1',
      path: 'skills/example/notes.md',
      type: 'file',
      content: 'note',
    });
    await moveSkillEntry('codex', 'demo', {
      revision: 'rev1',
      previousPath: 'skills/example/notes.md',
      nextPath: 'skills/example/renamed.md',
    });
    await deleteSkillEntry('codex', 'demo', 'skills/example/notes.md', 'rev2');

    await listPackageFilesTree('codex', 'demo');
    await loadPackageFile('codex', 'demo', 'docs/readme.md');
    await savePackageFile('codex', 'demo', 'docs/readme.md', {
      revision: 'rev3',
      content: '# Readme',
    });
    await createPackageFileEntry('codex', 'demo', {
      revision: 'rev3',
      path: 'docs/guide.md',
      type: 'file',
      content: 'guide',
    });
    await movePackageFileEntry('codex', 'demo', {
      revision: 'rev3',
      previousPath: 'docs/guide.md',
      nextPath: 'docs/archive.md',
    });
    await deletePackageFileEntry('codex', 'demo', 'docs/guide.md', 'rev4');

    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/packages/codex/demo/skills/tree');
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/skills/content?path=skills%2Fexample%2FSKILL.md',
    );
    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/skills/content?path=skills%2Fexample%2FSKILL.md',
      { revision: 'rev1', content: '# Skill' },
    );
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages/codex/demo/skills', {
      revision: 'rev1',
      path: 'skills/example/notes.md',
      type: 'file',
      content: 'note',
    });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages/codex/demo/skills/move', {
      revision: 'rev1',
      previousPath: 'skills/example/notes.md',
      nextPath: 'skills/example/renamed.md',
    });
    expect(apiClientMock.delete).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/skills?path=skills%2Fexample%2Fnotes.md&revision=rev2',
    );

    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/packages/codex/demo/files/tree');
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/files/content?path=docs%2Freadme.md',
    );
    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/files/content?path=docs%2Freadme.md',
      { revision: 'rev3', content: '# Readme' },
    );
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages/codex/demo/files', {
      revision: 'rev3',
      path: 'docs/guide.md',
      type: 'file',
      content: 'guide',
    });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages/codex/demo/files/move', {
      revision: 'rev3',
      previousPath: 'docs/guide.md',
      nextPath: 'docs/archive.md',
    });
    expect(apiClientMock.delete).toHaveBeenCalledWith(
      '/marketplace/packages/codex/demo/files?path=docs%2Fguide.md&revision=rev4',
    );
  });
});
