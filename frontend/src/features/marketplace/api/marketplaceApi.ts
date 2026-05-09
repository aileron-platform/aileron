import { apiClient } from '@/shared/api/apiClient';
import type {
  MarketplaceActivityRecord,
  MarketplaceCliPreflight,
  MarketplaceCreateRequest,
  MarketplaceDeleteRequest,
  MarketplaceDeleteResult,
  MarketplaceExportRequest,
  MarketplaceImportCandidate,
  MarketplaceImportResult,
  MarketplaceImportSource,
  MarketplaceImportUploadResult,
  MarketplaceInstallRequest,
  MarketplaceInstallResult,
  MarketplaceListQuery,
  MarketplaceListResult,
  MarketplacePackageDetail,
  MarketplacePackageSaveRequest,
  MarketplacePackageSaveResult,
  MarketplacePackageSummary,
  MarketplaceProvider,
  MarketplaceRegistryRootMetadataSavePayload,
  MarketplaceRegistryRepositoryStatus,
  MarketplaceRegistrySettings,
  MarketplaceRegistryGitCommitFiles,
  MarketplaceRegistryGitCommitList,
  MarketplaceRegistryGitDiff,
  MarketplaceRegistryGitOperationResult,
  MarketplaceRegistryGitStatus,
  MarketplaceRegistrySshKey,
} from '@/shared/types/marketplace';

interface MarketplaceActivityListResult {
  items: MarketplaceActivityRecord[];
  total: number;
  page: number;
  pageSize: number;
}

interface MarketplaceSettingsSaveResult {
  settings: MarketplaceRegistrySettings;
}

let lastImportSource: MarketplaceImportSource | null = null;

const MARKETPLACE_BASE = '/marketplace';

const appendParam = (params: URLSearchParams, key: string, value: unknown) => {
  if (value === undefined || value === null || value === '' || value === 'all') return;
  if (Array.isArray(value)) {
    value.forEach(item => appendParam(params, key, item));
    return;
  }
  params.append(key, String(value));
};

const marketplacePackagePath = (provider: MarketplaceProvider, packageId: string) =>
  `${MARKETPLACE_BASE}/packages/${encodeURIComponent(provider)}/${encodeURIComponent(packageId)}`;

export async function listPackages(query: MarketplaceListQuery): Promise<MarketplaceListResult> {
  const params = new URLSearchParams();
  appendParam(params, 'q', query.q);
  appendParam(params, 'provider', query.provider);
  appendParam(params, 'packageType', query.packageType);
  appendParam(params, 'category', query.category);
  appendParam(params, 'features', query.features);
  appendParam(params, 'validationSeverity', query.validationSeverity);
  appendParam(params, 'sourceType', query.sourceType);
  appendParam(params, 'updatedFrom', query.updatedFrom);
  appendParam(params, 'updatedTo', query.updatedTo);
  appendParam(params, 'sort', query.sort);
  appendParam(params, 'direction', query.direction);
  appendParam(params, 'page', query.page);
  appendParam(params, 'pageSize', query.pageSize);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return apiClient.get<MarketplaceListResult>(`${MARKETPLACE_BASE}/packages${suffix}`);
}

export async function refreshPackages(): Promise<MarketplaceListResult> {
  return apiClient.post<MarketplaceListResult>(`${MARKETPLACE_BASE}/packages/refresh`);
}

export async function getPackage(provider: MarketplaceProvider, packageId: string): Promise<MarketplacePackageDetail> {
  return apiClient.get<MarketplacePackageDetail>(marketplacePackagePath(provider, packageId));
}

export async function createPackage(request: MarketplaceCreateRequest): Promise<MarketplacePackageSummary> {
  return apiClient.post<MarketplacePackageSummary>(`${MARKETPLACE_BASE}/packages`, request);
}

export async function savePackage(request: MarketplacePackageSaveRequest): Promise<MarketplacePackageSaveResult> {
  return apiClient.put<MarketplacePackageSaveResult>(
    marketplacePackagePath(request.provider, request.packageId),
    {
      provider: request.provider,
      packageId: request.packageId,
      revision: request.revision,
      listing: request.listing,
      manifest: request.manifest,
      readmeMarkdown: request.readmeMarkdown,
      packageFiles: request.packageFiles,
    },
  );
}

export async function deletePackage(request: MarketplaceDeleteRequest): Promise<MarketplaceDeleteResult> {
  const params = new URLSearchParams({ revision: request.revision });
  return apiClient.delete<MarketplaceDeleteResult>(
    `${marketplacePackagePath(request.provider, request.packageId)}?${params.toString()}`,
  );
}

export async function exportPackage(request: MarketplaceExportRequest): Promise<Blob> {
  const params = new URLSearchParams({ revision: request.revision });
  return apiClient.getBlob(`${marketplacePackagePath(request.provider, request.packageId)}/export?${params.toString()}`);
}

export async function installPackage(request: MarketplaceInstallRequest): Promise<MarketplaceInstallResult> {
  return apiClient.post<MarketplaceInstallResult>(`${MARKETPLACE_BASE}/install`, request);
}

export async function getInstallPreflight(provider: MarketplaceProvider, workspaceId?: string): Promise<MarketplaceCliPreflight> {
  const params = new URLSearchParams({ provider });
  if (workspaceId) params.set('workspaceId', workspaceId);
  return apiClient.get<MarketplaceCliPreflight>(`${MARKETPLACE_BASE}/install/preflight?${params.toString()}`);
}

export async function scanImportSource(source: MarketplaceImportSource): Promise<MarketplaceImportCandidate[]> {
  lastImportSource = source;
  return apiClient.post<MarketplaceImportCandidate[]>(`${MARKETPLACE_BASE}/import/scan`, source);
}

export async function uploadImportSource(provider: MarketplaceProvider, file: File): Promise<MarketplaceImportUploadResult> {
  const formData = new FormData();
  formData.append('provider', provider);
  formData.append('file', file);
  const result = await apiClient.post<MarketplaceImportUploadResult>(`${MARKETPLACE_BASE}/import/upload`, formData);
  lastImportSource = result.source;
  return result;
}

export async function importCandidates(candidates: MarketplaceImportCandidate[]): Promise<MarketplaceImportResult> {
  if (!lastImportSource) {
    throw new Error('marketplace.import.errors.sourceRequired');
  }
  return apiClient.post<MarketplaceImportResult>(`${MARKETPLACE_BASE}/import`, {
    source: lastImportSource,
    candidates,
  });
}

export async function getRegistrySettings(): Promise<MarketplaceRegistrySettings> {
  return apiClient.get<MarketplaceRegistrySettings>(`${MARKETPLACE_BASE}/settings`);
}

export async function getRegistryRepository(): Promise<MarketplaceRegistryRepositoryStatus> {
  return apiClient.get<MarketplaceRegistryRepositoryStatus>(`${MARKETPLACE_BASE}/registry/repository`);
}

export async function saveRegistrySettings(
  payload: MarketplaceRegistryRootMetadataSavePayload,
): Promise<MarketplaceSettingsSaveResult> {
  return apiClient.put<MarketplaceSettingsSaveResult>(`${MARKETPLACE_BASE}/settings`, payload);
}

export async function initializeRegistry(): Promise<unknown> {
  return apiClient.post<unknown>(`${MARKETPLACE_BASE}/registry/init`);
}

export async function initializeRegistryGit(remoteUrl?: string): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(
    `${MARKETPLACE_BASE}/registry/git/init`,
    remoteUrl ? { remoteUrl } : undefined,
  );
}

export async function cloneRegistry(remoteUrl: string, branch?: string): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(
    `${MARKETPLACE_BASE}/registry/clone`,
    { remoteUrl, branch },
  );
}

export async function setRegistryRemote(remoteUrl: string): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.put<MarketplaceRegistryGitOperationResult>(
    `${MARKETPLACE_BASE}/registry/remote`,
    { remoteUrl },
  );
}

export async function listActivity(page = 1, pageSize = 50): Promise<MarketplaceActivityListResult> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  return apiClient.get<MarketplaceActivityListResult>(`${MARKETPLACE_BASE}/activity?${params.toString()}`);
}

export async function getRegistryGitStatus(): Promise<MarketplaceRegistryGitStatus> {
  return apiClient.get<MarketplaceRegistryGitStatus>(`${MARKETPLACE_BASE}/registry/status`);
}

export async function getRegistryFileDiff(path: string, head: 'WORKTREE' | 'INDEX' = 'WORKTREE'): Promise<MarketplaceRegistryGitDiff> {
  const params = new URLSearchParams({ path, head });
  return apiClient.get<MarketplaceRegistryGitDiff>(`${MARKETPLACE_BASE}/registry/diff?${params.toString()}`);
}

export async function getRegistryCommitFileDiff(commitId: string, path: string): Promise<MarketplaceRegistryGitDiff> {
  const params = new URLSearchParams({ path });
  return apiClient.get<MarketplaceRegistryGitDiff>(
    `${MARKETPLACE_BASE}/registry/commits/${encodeURIComponent(commitId)}/diff?${params.toString()}`,
  );
}

export async function getRegistryCommits(page = 1, pageSize = 20): Promise<MarketplaceRegistryGitCommitList> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  return apiClient.get<MarketplaceRegistryGitCommitList>(`${MARKETPLACE_BASE}/registry/commits?${params.toString()}`);
}

export async function getRegistryCommitFiles(commitId: string): Promise<MarketplaceRegistryGitCommitFiles> {
  return apiClient.get<MarketplaceRegistryGitCommitFiles>(
    `${MARKETPLACE_BASE}/registry/commits/${encodeURIComponent(commitId)}/files`,
  );
}

export async function stageRegistryFiles(paths: string[]): Promise<MarketplaceRegistryGitStatus> {
  return apiClient.post<MarketplaceRegistryGitStatus>(`${MARKETPLACE_BASE}/registry/stage`, { paths });
}

export async function unstageRegistryFiles(paths: string[]): Promise<MarketplaceRegistryGitStatus> {
  return apiClient.post<MarketplaceRegistryGitStatus>(`${MARKETPLACE_BASE}/registry/unstage`, { paths });
}

export async function commitRegistryChanges(message: string, paths?: string[]): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(`${MARKETPLACE_BASE}/registry/commit`, { message, paths });
}

export async function fetchRegistry(): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(`${MARKETPLACE_BASE}/registry/fetch`);
}

export async function pullRegistry(): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(`${MARKETPLACE_BASE}/registry/pull`);
}

export async function pushRegistry(): Promise<MarketplaceRegistryGitOperationResult> {
  return apiClient.post<MarketplaceRegistryGitOperationResult>(`${MARKETPLACE_BASE}/registry/push`);
}

export async function getRegistrySshKey(): Promise<MarketplaceRegistrySshKey> {
  return apiClient.get<MarketplaceRegistrySshKey>(`${MARKETPLACE_BASE}/registry/ssh-key`);
}

export async function generateRegistrySshKey(): Promise<MarketplaceRegistrySshKey> {
  return apiClient.post<MarketplaceRegistrySshKey>(`${MARKETPLACE_BASE}/registry/ssh-key`);
}
