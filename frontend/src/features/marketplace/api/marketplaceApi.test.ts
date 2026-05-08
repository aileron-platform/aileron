import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createPackage,
  cloneRegistry,
  commitRegistryChanges,
  deletePackage,
  exportPackage,
  fetchRegistry,
  generateRegistrySshKey,
  getInstallPreflight,
  getPackage,
  getRegistryCommitFileDiff,
  getRegistryCommitFiles,
  getRegistryCommits,
  getRegistryFileDiff,
  getRegistrySettings,
  getRegistryRepository,
  getRegistryGitStatus,
  getRegistrySshKey,
  importCandidates,
  initializeRegistry,
  initializeRegistryGit,
  installPackage,
  listActivity,
  listPackages,
  pullRegistry,
  pushRegistry,
  savePackage,
  saveRegistrySettings,
  setRegistryRemote,
  scanImportSource,
  stageRegistryFiles,
  unstageRegistryFiles,
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
    apiClientMock.put.mockResolvedValueOnce({ package: { packageId: 'new-plugin' }, revision: 'rev-2', validationResults: [] });
    apiClientMock.delete.mockResolvedValueOnce({ deleted: true });
    apiClientMock.getBlob.mockResolvedValueOnce(new Blob(['zip'], { type: 'application/zip' }));

    await getPackage('claude-code', 'review-assistant');
    await createPackage({
      provider: 'codex',
      packageId: 'new-plugin',
      displayName: 'New Plugin',
      description: 'New package',
    });
    await savePackage({
      provider: 'codex',
      packageId: 'new-plugin',
      revision: 'rev-1',
      listing: { name: 'new-plugin' },
      manifest: { name: 'new-plugin', version: '0.1.0', description: 'New package' },
    });
    await deletePackage({ provider: 'codex', packageId: 'new-plugin', revision: 'rev-1' });
    await exportPackage({ provider: 'gemini', packageId: 'workspace-tools', revision: 'rev-2' });

    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/packages/claude-code/review-assistant');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/packages', {
      provider: 'codex',
      packageId: 'new-plugin',
      displayName: 'New Plugin',
      description: 'New package',
    });
    expect(apiClientMock.put).toHaveBeenCalledWith('/marketplace/packages/codex/new-plugin', {
      provider: 'codex',
      packageId: 'new-plugin',
      revision: 'rev-1',
      listing: { name: 'new-plugin' },
      manifest: { name: 'new-plugin', version: '0.1.0', description: 'New package' },
      readmeMarkdown: undefined,
    });
    expect(apiClientMock.delete).toHaveBeenCalledWith('/marketplace/packages/codex/new-plugin?revision=rev-1');
    expect(apiClientMock.getBlob).toHaveBeenCalledWith('/marketplace/packages/gemini/workspace-tools/export');
  });

  it('uses backend install, preflight, activity, and settings endpoints', async () => {
    apiClientMock.post.mockResolvedValueOnce({ status: 'success' });
    apiClientMock.get.mockResolvedValueOnce({ available: true });
    apiClientMock.get.mockResolvedValueOnce({ items: [] });
    apiClientMock.get.mockResolvedValueOnce({ displayName: 'Registry' });
    apiClientMock.put.mockResolvedValueOnce({ settings: { displayName: 'Registry' } });

    await installPackage({ provider: 'codex', packageId: 'figma-context', revision: 'rev', workspaceId: 'workspace-1' });
    await getInstallPreflight('codex');
    await listActivity(3, 25);
    await getRegistrySettings();
    await getRegistryRepository();
    await initializeRegistry();
    await initializeRegistryGit('git@github.com:example/marketplace.git');
    await cloneRegistry('git@github.com:example/marketplace.git', 'main');
    await setRegistryRemote('git@github.com:example/updated-marketplace.git');
    await saveRegistrySettings({
      name: 'Registry',
      owner: { name: 'Maintainer', email: 'maintainer@example.local' },
      description: 'Registry description',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/install', {
      provider: 'codex',
      packageId: 'figma-context',
      revision: 'rev',
      workspaceId: 'workspace-1',
    });
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/install/preflight?provider=codex');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/activity?page=3&pageSize=25');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/settings');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/repository');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/init');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/git/init', {
      remoteUrl: 'git@github.com:example/marketplace.git',
    });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/clone', {
      remoteUrl: 'git@github.com:example/marketplace.git',
      branch: 'main',
    });
    expect(apiClientMock.put).toHaveBeenCalledWith('/marketplace/registry/remote', {
      remoteUrl: 'git@github.com:example/updated-marketplace.git',
    });
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

  it('uses backend registry Git and SSH endpoints', async () => {
    apiClientMock.get.mockResolvedValue({});
    apiClientMock.post.mockResolvedValue({});

    await getRegistryGitStatus();
    await getRegistryFileDiff('codex/.agents/plugins/marketplace.json', 'INDEX');
    await getRegistryCommits(2, 10);
    await getRegistryCommitFiles('abc123');
    await getRegistryCommitFileDiff('abc123', 'codex/.agents/plugins/marketplace.json');
    await stageRegistryFiles(['codex/.agents/plugins/marketplace.json']);
    await unstageRegistryFiles(['codex/.agents/plugins/marketplace.json']);
    await commitRegistryChanges('Update registry', ['codex/.agents/plugins/marketplace.json']);
    await fetchRegistry();
    await pullRegistry();
    await pushRegistry();
    await getRegistrySshKey();
    await generateRegistrySshKey();

    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/status');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/diff?path=codex%2F.agents%2Fplugins%2Fmarketplace.json&head=INDEX');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/commits?page=2&pageSize=10');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/commits/abc123/files');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/commits/abc123/diff?path=codex%2F.agents%2Fplugins%2Fmarketplace.json');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/stage', { paths: ['codex/.agents/plugins/marketplace.json'] });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/unstage', { paths: ['codex/.agents/plugins/marketplace.json'] });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/commit', {
      message: 'Update registry',
      paths: ['codex/.agents/plugins/marketplace.json'],
    });
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/fetch');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/pull');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/push');
    expect(apiClientMock.get).toHaveBeenCalledWith('/marketplace/registry/ssh-key');
    expect(apiClientMock.post).toHaveBeenCalledWith('/marketplace/registry/ssh-key');
  });
});
