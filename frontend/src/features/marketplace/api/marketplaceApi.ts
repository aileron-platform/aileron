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
  MarketplaceActivityDetail,
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
  MarketplacePackageFormat,
  MarketplacePackageFormatOption,
  MarketplaceTargetClient,
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
  server: Record<string, unknown>;
  ownerFilePath: string;
  baseEntryFingerprint: string;
}

export type MarketplaceMCPServerDetail = MarketplaceMCPServerSummary;

const MARKETPLACE_BASE = '/marketplace';

const appendParam = (params: URLSearchParams, key: string, value: unknown) => {
  if (value === undefined || value === null || value === '' || value === 'all') return;
  if (Array.isArray(value)) {
    value.forEach(item => appendParam(params, key, item));
    return;
  }
  params.append(key, String(value));
};

const marketplacePackagePath = (
  targetClient: MarketplaceTargetClient,
  packageId: string,
  suffix = '',
  params = new URLSearchParams(),
  explicitPackageFormat?: MarketplacePackageFormat,
) => {
  const routeFormat = typeof window === 'undefined'
    ? null
    : new URLSearchParams(window.location.search).get('packageFormat');
  const packageFormat = explicitPackageFormat
    ?? (routeFormat as MarketplacePackageFormat | null)
    ?? (targetClient === 'codex' ? 'codex-native' : 'claude-native');
  params.set('packageFormat', packageFormat);
  return `${MARKETPLACE_BASE}/packages/${encodeURIComponent(targetClient)}/${encodeURIComponent(packageId)}${suffix}?${params.toString()}`;
};

export async function listPackages(query: MarketplaceListQuery): Promise<MarketplaceListResult> {
  const params = new URLSearchParams();
  appendParam(params, 'q', query.q);
  appendParam(params, 'targetClient', query.targetClient);
  appendParam(params, 'packageType', query.packageType);
  appendParam(params, 'category', query.category);
  appendParam(params, 'features', query.features);
  appendParam(params, 'validationSeverity', query.validationSeverity);
  appendParam(params, 'updatedFrom', query.updatedFrom);
  appendParam(params, 'updatedTo', query.updatedTo);
  appendParam(params, 'sort', query.sort);
  appendParam(params, 'direction', query.direction);
  appendParam(params, 'page', query.page);
  appendParam(params, 'pageSize', query.pageSize);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return apiClient.get<MarketplaceListResult>(`${MARKETPLACE_BASE}/packages${suffix}`);
}

export async function listPackageFormatOptions(): Promise<MarketplacePackageFormatOption[]> {
  return apiClient.get<MarketplacePackageFormatOption[]>(`${MARKETPLACE_BASE}/package-formats`);
}

export async function listMarketplaceActivity(
  query: MarketplaceActivityListQuery,
): Promise<MarketplaceActivityListResult> {
  const params = new URLSearchParams();
  appendParam(params, 'page', query.page);
  appendParam(params, 'pageSize', query.pageSize);
  appendParam(params, 'workspaceId', query.workspaceId);
  appendParam(params, 'packageFormat', query.packageFormat);
  appendParam(params, 'targetClient', query.targetClient);
  appendParam(params, 'packageId', query.packageId);
  appendParam(params, 'action', query.action);
  appendParam(params, 'status', query.status);
  return apiClient.get<MarketplaceActivityListResult>(
    `${MARKETPLACE_BASE}/activities?${params.toString()}`,
  );
}

export async function getMarketplaceActivityDetail(
  activityId: string,
): Promise<MarketplaceActivityDetail> {
  return apiClient.get<MarketplaceActivityDetail>(
    `${MARKETPLACE_BASE}/activities/${encodeURIComponent(activityId)}`,
  );
}

export async function getPackage(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  packageFormat?: MarketplacePackageFormat,
): Promise<MarketplacePackageDetail> {
  return apiClient.get<MarketplacePackageDetail>(
    marketplacePackagePath(targetClient, packageId, '', new URLSearchParams(), packageFormat),
  );
}

export async function refreshMarketplacePackage(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  packageFormat?: MarketplacePackageFormat,
  signal?: AbortSignal,
): Promise<{ refreshed: true }> {
  return apiClient.post<{ refreshed: true }>(
    marketplacePackagePath(
      targetClient,
      packageId,
      `/refresh`,
      new URLSearchParams(),
      packageFormat,
    ),
    undefined,
    { signal },
  );
}

export async function createPackage(request: MarketplaceCreateRequest): Promise<MarketplacePackageSummary> {
  return apiClient.post<MarketplacePackageSummary>(`${MARKETPLACE_BASE}/packages`, request);
}

export async function deletePackage(request: MarketplaceDeleteRequest): Promise<MarketplaceDeleteResult> {
  return apiClient.delete<MarketplaceDeleteResult>(
    marketplacePackagePath(
      request.targetClient,
      request.packageId,
      '',
      new URLSearchParams(),
      request.packageFormat,
    ),
  );
}

export async function exportPackage(request: MarketplaceExportRequest): Promise<Blob> {
  const params = new URLSearchParams({ revision: request.revision });
  return apiClient.getBlob(marketplacePackagePath(
    request.targetClient,
    request.packageId,
    '/export',
    params,
    request.packageFormat,
  ));
}

export async function saveRootDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/root-document`),
    payload,
  );
}

export async function getRootDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<MarketplaceRootDocumentResource> {
  return apiClient.get<MarketplaceRootDocumentResource>(
    marketplacePackagePath(targetClient, packageId, `/root-document`),
  );
}

export async function getMarketplaceReadme(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<MarketplaceReadmeResource> {
  return apiClient.get<MarketplaceReadmeResource>(
    marketplacePackagePath(targetClient, packageId, `/readme`),
  );
}

export async function listDocuments(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
): Promise<MarketplaceDocumentSummary[]> {
  return apiClient.get<MarketplaceDocumentSummary[]>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}`),
  );
}

export async function loadDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
): Promise<MarketplaceDocumentSummary> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceDocumentSummary>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}/content`, query),
  );
}

export async function createDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  payload: MarketplaceDocumentMutationPayload,
): Promise<MarketplaceDocumentMutationResult> {
  return apiClient.post<MarketplaceDocumentMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}`),
    payload,
  );
}

export async function updateDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
  payload: MarketplaceDocumentMutationPayload,
): Promise<MarketplaceDocumentMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplaceDocumentMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}/content`, query),
    payload,
  );
}

export async function renameDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  payload: MarketplaceDocumentRenamePayload,
): Promise<MarketplaceDocumentMutationResult> {
  return apiClient.post<MarketplaceDocumentMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}/move`),
    payload,
  );
}

export async function removeDocument(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  resourceType: MarketplaceDocumentResourceType,
  path: string,
  payload: MarketplaceDocumentRemovePayload,
): Promise<MarketplaceDocumentMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.delete<MarketplaceDocumentMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/${resourceType}/content`, query),
    undefined,
    payload,
  );
}

export async function saveMCPServer(
  targetClient: MarketplaceTargetClient,
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
    marketplacePackagePath(targetClient, packageId, `/mcp-servers/${encodeURIComponent(name)}`),
    payload,
  );
}

export async function listMCPServers(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<MarketplaceMCPServerSummary[]> {
  return apiClient.get<MarketplaceMCPServerSummary[]>(
    marketplacePackagePath(targetClient, packageId, `/mcp-servers`),
  );
}

export async function getMCPServer(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  name: string,
  ownerFilePath: string,
): Promise<MarketplaceMCPServerDetail> {
  const query = new URLSearchParams({ ownerFilePath });
  return apiClient.get<MarketplaceMCPServerDetail>(
    marketplacePackagePath(targetClient, packageId, `/mcp-servers/${encodeURIComponent(name)}`, query),
  );
}

export async function createMCPServer(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: {
    revision: string;
    name: string;
    server: Record<string, unknown>;
  },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/mcp-servers`),
    payload,
  );
}

export async function deleteMCPServer(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  name: string,
  payload: {
    revision: string;
    ownerFilePath: string;
    baseEntryFingerprint: string;
  },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.delete<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/mcp-servers/${encodeURIComponent(name)}`),
    undefined,
    payload,
  );
}

export async function updateBasic(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: MarketplaceBasicUpdatePayload,
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/basic`),
    payload,
  );
}

export async function updateHooks(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; sourceId?: string | null; content: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.put<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/hooks`),
    payload,
  );
}

export async function getHooks(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<MarketplaceHooksResource> {
  return apiClient.get<MarketplaceHooksResource>(
    marketplacePackagePath(targetClient, packageId, `/hooks`),
  );
}

export async function listSkillTree(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<FileTreeNode[]> {
  const data = await apiClient.get<unknown>(
    marketplacePackagePath(targetClient, packageId, `/skills/tree`),
  );
  return parseFileTree(data);
}

export async function loadSkillFile(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
): Promise<MarketplaceTextFileResource> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceTextFileResource>(
    marketplacePackagePath(targetClient, packageId, `/skills/content`, query),
  );
}

export async function saveSkillFile(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/skills/content`, query),
    payload,
  );
}

export async function createSkillEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; path: string; type: 'file' | 'directory'; content?: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/skills`),
    payload,
  );
}

export async function deleteSkillEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
  revision: string,
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path, revision });
  return apiClient.delete<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/skills`, query),
  );
}

export async function moveSkillEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; previousPath: string; nextPath: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/skills/move`),
    payload,
  );
}

export async function listPackageFilesTree(
  targetClient: MarketplaceTargetClient,
  packageId: string,
): Promise<FileTreeNode[]> {
  const data = await apiClient.get<unknown>(
    marketplacePackagePath(targetClient, packageId, `/files/tree`),
  );
  return parseFileTree(data);
}

export async function loadPackageFile(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
): Promise<MarketplaceTextFileResource> {
  const query = new URLSearchParams({ path });
  return apiClient.get<MarketplaceTextFileResource>(
    marketplacePackagePath(targetClient, packageId, `/files/content`, query),
  );
}

export async function savePackageFile(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
  payload: { revision: string; content: string },
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path });
  return apiClient.put<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/files/content`, query),
    payload,
  );
}

export async function createPackageFileEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; path: string; type: 'file' | 'directory'; content?: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/files`),
    payload,
  );
}

export async function deletePackageFileEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  path: string,
  revision: string,
): Promise<MarketplacePackageMutationResult> {
  const query = new URLSearchParams({ path, revision });
  return apiClient.delete<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/files`, query),
  );
}

export async function movePackageFileEntry(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  payload: { revision: string; previousPath: string; nextPath: string },
): Promise<MarketplacePackageMutationResult> {
  return apiClient.post<MarketplacePackageMutationResult>(
    marketplacePackagePath(targetClient, packageId, `/files/move`),
    payload,
  );
}

export async function preflightMarketplaceFileConflicts(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal },
): Promise<FileConflictPreflightResponse> {
  return apiClient.post<FileConflictPreflightResponse>(
    marketplacePackagePath(targetClient, packageId, `/files/conflicts/preflight`),
    request,
    options,
  );
}

export async function executeMarketplaceFileConflictOperation(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  request: FileConflictExecutionRequest<MarketplaceFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> {
  const path = marketplacePackagePath(targetClient, packageId, `/files/${request.operation}`);
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
  targetClient: MarketplaceTargetClient,
  packageId: string,
  revision: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal },
): Promise<FileConflictPreflightResponse> {
  return apiClient.post<FileConflictPreflightResponse>(
    marketplacePackagePath(targetClient, packageId, `/skills/conflicts/preflight`),
    { ...request, revision },
    options,
  );
}

export async function executeMarketplaceSkillFileConflictOperation(
  targetClient: MarketplaceTargetClient,
  packageId: string,
  request: FileConflictExecutionRequest<MarketplaceSkillFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> {
  if (request.operation === 'paste') throw new Error('MARKETPLACE_SKILL_PASTE_UNSUPPORTED');
  const path = marketplacePackagePath(targetClient, packageId, `/skills/${request.operation}`);
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
  return apiClient.post<MarketplaceImportCandidate[]>(`${MARKETPLACE_BASE}/imports/scan`, source);
}

export async function uploadImportSource(targetClient: MarketplaceTargetClient, file: File): Promise<MarketplaceImportUploadResult> {
  const formData = new FormData();
  formData.append('targetClient', targetClient);
  formData.append('file', file);
  return apiClient.post<MarketplaceImportUploadResult>(`${MARKETPLACE_BASE}/imports/upload`, formData);
}

export async function importCandidates(
  source: MarketplaceImportSource,
  candidates: MarketplaceImportCandidate[],
): Promise<MarketplaceImportResult> {
  return apiClient.post<MarketplaceImportResult>(`${MARKETPLACE_BASE}/imports`, {
    source,
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
