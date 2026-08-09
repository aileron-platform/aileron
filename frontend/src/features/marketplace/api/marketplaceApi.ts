import { apiClient } from '@/shared/api/apiClient';
import { parseFileTree } from '@/shared/components/file-workbench';
import type {
  FileConflictBatchResult,
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
  FileTreeNode,
} from '@/shared/components/file-workbench';
import type {
  MarketplaceActivityListQuery,
  MarketplaceActivityListResult,
  MarketplaceCreateRequest,
  MarketplaceDeleteRequest,
  MarketplaceDeleteResult,
  MarketplaceExportRequest,
  MarketplaceImportCandidate,
  MarketplaceImportResult,
  MarketplaceImportSource,
  MarketplaceImportUploadResult,
  MarketplacePluginCommandResult,
  MarketplacePluginInstallRequest,
  MarketplaceListQuery,
  MarketplaceListResult,
  MarketplacePackageDetail,
  MarketplacePackageSummary,
  MarketplaceProvider,
  MarketplaceRegistryRootMetadataSavePayload,
  MarketplaceRegistrySettings,
  MarketplaceUserCopyApplyRequest,
  MarketplaceUserCopyApplyResult,
  MarketplaceUserCopyPreflightRequest,
  MarketplaceUserCopyPreflightResult,
} from '@/features/marketplace/model/marketplaceTypes';
import type {
  MarketplaceBasicUpdatePayload,
  MarketplaceDocumentMutationPayload,
  MarketplaceDocumentMutationResult,
  MarketplaceDocumentRemovePayload,
  MarketplaceDocumentRenamePayload,
  MarketplaceDocumentResourceType,
  MarketplaceDocumentSummary,
  MarketplacePackageMutationResult,
} from '../model/marketplaceMutation';

interface MarketplaceSettingsSaveResult {
  settings: MarketplaceRegistrySettings;
}

export interface MarketplaceTreeEntry {
  path: string;
  name: string;
  type: 'file' | 'directory';
}

export interface MarketplaceTextFileResource {
  path: string;
  name: string;
  content: string;
}

export interface MarketplaceFileConflictPayload {
  files?: File[];
  sourcePath?: string;
  entryType?: 'file' | 'directory';
  content?: string;
}

export interface MarketplaceSkillFileConflictPayload extends MarketplaceFileConflictPayload {
  revision: string;
}

export interface MarketplaceRootDocumentResource {
  path: string;
  content: string;
}

export interface MarketplaceReadmeResource {
  revision: string;
  path: string | null;
  content: string;
}

export interface MarketplaceHooksResource {
  revision: string;
  sources: MarketplaceHooksSource[];
  hookCapabilities: {
    mode: 'sources';
    groups?: string[];
  };
}

export interface MarketplaceHooksSource {
  sourceId: string;
  sourceType: 'inline' | 'file';
  path: string;
  manifestPointer: string;
  content: string;
  nativeContent?: Record<string, unknown> | null;
  writable: boolean;
  diagnostics: Array<{
    code: string;
    messageKey: string;
    sourceLocator: string;
  }>;
}

export interface MarketplaceMCPServerSummary {
  name: string;
  path: string;
  ownerFilePath: string;
  baseEntryFingerprint: string;
}

export interface MarketplaceMCPServerDetail extends MarketplaceMCPServerSummary {
  server: Record<string, unknown>;
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

export async function listMarketplaceActivity(
  query: MarketplaceActivityListQuery,
): Promise<MarketplaceActivityListResult> {
  const params = new URLSearchParams();
  appendParam(params, 'page', query.page);
  appendParam(params, 'pageSize', query.pageSize);
  appendParam(params, 'workspaceId', query.workspaceId);
  appendParam(params, 'provider', query.provider);
  appendParam(params, 'packageId', query.packageId);
  appendParam(params, 'action', query.action);
  appendParam(params, 'status', query.status);
  return apiClient.get<MarketplaceActivityListResult>(
    `${MARKETPLACE_BASE}/activities?${params.toString()}`,
  );
}

export async function getPackage(provider: MarketplaceProvider, packageId: string): Promise<MarketplacePackageDetail> {
  return apiClient.get<MarketplacePackageDetail>(marketplacePackagePath(provider, packageId));
}

export async function refreshMarketplacePackage(
  provider: MarketplaceProvider,
  packageId: string,
  signal?: AbortSignal,
): Promise<{ refreshed: true }> {
  return apiClient.post<{ refreshed: true }>(
    `${marketplacePackagePath(provider, packageId)}/refresh`,
    undefined,
    { signal },
  );
}

export async function createPackage(request: MarketplaceCreateRequest): Promise<MarketplacePackageSummary> {
  return apiClient.post<MarketplacePackageSummary>(`${MARKETPLACE_BASE}/packages`, request);
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

export async function saveRootDocument(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/root-document`,
    payload,
  );
}

export async function getRootDocument(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<MarketplaceRootDocumentResource> {
  return apiClient.get<MarketplaceRootDocumentResource>(
    `${marketplacePackagePath(provider, packageId)}/root-document`,
  );
}

export async function getMarketplaceReadme(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<MarketplaceReadmeResource> {
  return apiClient.get<MarketplaceReadmeResource>(
    `${marketplacePackagePath(provider, packageId)}/readme`,
  );
}

export async function listDocuments(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
): Promise<MarketplaceDocumentSummary[]> {
  return apiClient.get<MarketplaceDocumentSummary[]>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}`,
  );
}

export async function loadDocument(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
): Promise<MarketplaceDocumentSummary> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceDocumentSummary>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}/content?${query.toString()}`,
  );
}

export async function createDocument(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  payload: MarketplaceDocumentMutationPayload,
): Promise<MarketplaceDocumentMutationResult> {
  return apiClient.post<MarketplaceDocumentMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}`,
    payload,
  );
}

export async function updateDocument(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
  payload: MarketplaceDocumentMutationPayload,
): Promise<MarketplaceDocumentMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplaceDocumentMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}/content?${query.toString()}`,
    payload,
  );
}

export async function renameDocument(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  payload: MarketplaceDocumentRenamePayload,
): Promise<MarketplaceDocumentMutationResult> {
  return apiClient.post<MarketplaceDocumentMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}/move`,
    payload,
  );
}

export async function removeDocument(
  provider: MarketplaceProvider,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
  payload: MarketplaceDocumentRemovePayload,
): Promise<MarketplaceDocumentMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.delete<MarketplaceDocumentMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/${resourceType}/content?${query.toString()}`,
    undefined,
    payload,
  );
}

export async function saveMCPServer(
  provider: MarketplaceProvider,
  packageId: string,
  name: string,
  payload: {
    revision: string;
    server: Record<string, unknown>;
    ownerFilePath: string;
    baseEntryFingerprint: string;
  },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/mcp-servers/${encodeURIComponent(name)}`,
    payload,
  );
}

export async function listMCPServers(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<MarketplaceMCPServerSummary[]> {
  return apiClient.get<MarketplaceMCPServerSummary[]>(
    `${marketplacePackagePath(provider, packageId)}/mcp-servers`,
  );
}

export async function getMCPServer(
  provider: MarketplaceProvider,
  packageId: string,
  name: string,
  ownerFilePath: string,
): Promise<MarketplaceMCPServerDetail> {
  const query = new URLSearchParams({ ownerFilePath });
  return apiClient.get<MarketplaceMCPServerDetail>(
    `${marketplacePackagePath(provider, packageId)}/mcp-servers/${encodeURIComponent(name)}?${query.toString()}`,
  );
}

export async function createMCPServer(
  provider: MarketplaceProvider,
  packageId: string,
  payload: {
    revision: string;
    name: string;
    server: Record<string, unknown>;
  },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/mcp-servers`,
    payload,
  );
}

export async function deleteMCPServer(
  provider: MarketplaceProvider,
  packageId: string,
  name: string,
  payload: {
    revision: string;
    ownerFilePath: string;
    baseEntryFingerprint: string;
  },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.delete<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/mcp-servers/${encodeURIComponent(name)}`,
    undefined,
    payload,
  );
}

export async function updateBasic(
  provider: MarketplaceProvider,
  packageId: string,
  payload: MarketplaceBasicUpdatePayload,
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/basic`,
    payload,
  );
}

export async function updateHooks(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; sourceId?: string | null; content: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/hooks`,
    payload,
  );
}

export async function getHooks(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<MarketplaceHooksResource> {
  return apiClient.get<MarketplaceHooksResource>(
    `${marketplacePackagePath(provider, packageId)}/hooks`,
  );
}

export async function listSkillTree(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<FileTreeNode[]> {
  const data = await apiClient.get<unknown>(
    `${marketplacePackagePath(provider, packageId)}/skills/tree`,
  );
  return parseFileTree(data);
}

export async function loadSkillFile(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
): Promise<MarketplaceTextFileResource> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceTextFileResource>(
    `${marketplacePackagePath(provider, packageId)}/skills/content?${query.toString()}`,
  );
}

export async function saveSkillFile(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/skills/content?${query.toString()}`,
    payload,
  );
}

export async function createSkillEntry(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; path: string; type: 'file' | 'directory'; content?: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/skills`,
    payload,
  );
}

export async function deleteSkillEntry(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
  revision: string,
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path, revision });
  return apiClient.delete<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/skills?${query.toString()}`,
  );
}

export async function moveSkillEntry(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; previousPath: string; nextPath: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/skills/move`,
    payload,
  );
}

export async function listPackageFilesTree(
  provider: MarketplaceProvider,
  packageId: string,
): Promise<FileTreeNode[]> {
  const data = await apiClient.get<unknown>(
    `${marketplacePackagePath(provider, packageId)}/files/tree`,
  );
  return parseFileTree(data);
}

export async function loadPackageFile(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
): Promise<MarketplaceTextFileResource> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceTextFileResource>(
    `${marketplacePackagePath(provider, packageId)}/files/content?${query.toString()}`,
  );
}

export async function savePackageFile(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/files/content?${query.toString()}`,
    payload,
  );
}

export async function createPackageFileEntry(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; path: string; type: 'file' | 'directory'; content?: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/files`,
    payload,
  );
}

export async function deletePackageFileEntry(
  provider: MarketplaceProvider,
  packageId: string,
  path: string,
  revision: string,
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path, revision });
  return apiClient.delete<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/files?${query.toString()}`,
  );
}

export async function movePackageFileEntry(
  provider: MarketplaceProvider,
  packageId: string,
  payload: { revision: string; previousPath: string; nextPath: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    `${marketplacePackagePath(provider, packageId)}/files/move`,
    payload,
  );
}

export async function preflightMarketplaceFileConflicts(
  provider: MarketplaceProvider,
  packageId: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal },
): Promise<FileConflictPreflightResponse> {
  return apiClient.post<FileConflictPreflightResponse>(
    `${marketplacePackagePath(provider, packageId)}/files/conflicts/preflight`,
    request,
    options,
  );
}

export async function executeMarketplaceFileConflictOperation(
  provider: MarketplaceProvider,
  packageId: string,
  request: FileConflictExecutionRequest<MarketplaceFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> {
  const path = `${marketplacePackagePath(provider, packageId)}/files/${request.operation}`;
  if (request.operation === 'upload') {
    const formData = new FormData();
    formData.append('targetPath', request.targetPath);
    formData.append('defaultStrategy', request.defaultStrategy);
    formData.append('resolutions', JSON.stringify(request.resolutions));
    for (const file of request.payload.files ?? []) formData.append('files', file);
    return apiClient.post<FileConflictBatchResult>(path, formData, options);
  }
  const body = request.operation === 'paste'
    ? {
        targetPath: request.targetPath,
        sources: request.sources,
        defaultStrategy: request.defaultStrategy,
        resolutions: request.resolutions,
      }
    : {
        archivePath: request.archivePath,
        targetPath: request.targetPath,
        defaultStrategy: request.defaultStrategy,
        resolutions: request.resolutions,
      };
  return apiClient.post<FileConflictBatchResult>(path, body, options);
}

export async function preflightMarketplaceSkillFileConflicts(
  provider: MarketplaceProvider,
  packageId: string,
  revision: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal },
): Promise<FileConflictPreflightResponse> {
  return apiClient.post<FileConflictPreflightResponse>(
    `${marketplacePackagePath(provider, packageId)}/skills/conflicts/preflight`,
    { ...request, revision },
    options,
  );
}

export async function executeMarketplaceSkillFileConflictOperation(
  provider: MarketplaceProvider,
  packageId: string,
  request: FileConflictExecutionRequest<MarketplaceSkillFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> {
  if (request.operation === 'paste') throw new Error('MARKETPLACE_SKILL_PASTE_UNSUPPORTED');
  const path = `${marketplacePackagePath(provider, packageId)}/skills/${request.operation}`;
  if (request.operation === 'upload') {
    const formData = new FormData();
    formData.append('revision', request.payload.revision);
    formData.append('targetPath', request.targetPath);
    formData.append('defaultStrategy', request.defaultStrategy);
    formData.append('resolutions', JSON.stringify(request.resolutions));
    for (const file of request.payload.files ?? []) formData.append('files', file);
    return apiClient.post<FileConflictBatchResult>(path, formData, options);
  }
  return apiClient.post<FileConflictBatchResult>(path, {
    revision: request.payload.revision,
    archivePath: request.archivePath,
    targetPath: request.targetPath,
    defaultStrategy: request.defaultStrategy,
    resolutions: request.resolutions,
  }, options);
}

export async function installMarketplacePlugin(
  request: MarketplacePluginInstallRequest,
): Promise<MarketplacePluginCommandResult> {
  return apiClient.post<MarketplacePluginCommandResult>(
    `${MARKETPLACE_BASE}/plugins/install`,
    request,
  );
}

export async function preflightMarketplaceUserCopy(
  request: MarketplaceUserCopyPreflightRequest,
  signal?: AbortSignal,
): Promise<MarketplaceUserCopyPreflightResult> {
  const path = `${MARKETPLACE_BASE}/user-copies/preflight`;
  return signal
    ? apiClient.post<MarketplaceUserCopyPreflightResult>(
      path,
      request,
      { signal },
    )
    : apiClient.post<MarketplaceUserCopyPreflightResult>(path, request);
}

export async function createMarketplaceUserCopy(
  request: MarketplaceUserCopyApplyRequest,
): Promise<MarketplaceUserCopyApplyResult> {
  return apiClient.post<MarketplaceUserCopyApplyResult>(
    `${MARKETPLACE_BASE}/user-copies`,
    request,
  );
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

export async function saveRegistrySettings(
  payload: MarketplaceRegistryRootMetadataSavePayload,
): Promise<MarketplaceSettingsSaveResult> {
  return apiClient.put<MarketplaceSettingsSaveResult>(`${MARKETPLACE_BASE}/settings`, payload);
}
