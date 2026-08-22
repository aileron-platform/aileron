import { ApiClient, apiClient } from '@/shared/api/apiClient';
import type { QueryClient } from '@tanstack/react-query';
import { parseFileTree, sortTreeNodes } from '@/shared/components/file-workbench';
import type {
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileDownloadOptions,
  FileOperationRequest,
  FileOperationResponse,
  FileTreeDataAdapter,
  FileTreeNode,
  FileUploadOptions,
  FileConflictBatchResult,
  FileConflictExecutionFields,
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
  FileConflictWorkflowTransport,
} from '@/shared/components/file-workbench';
import type { AgentFileCollection, AgentSelectedFile } from '../model/documents';
import type { CodexFileListResponse, CodexFileSummary } from '../api/agentSettingsApi';
import { isReadOnlyAgentScope, toCodexFileScope } from '../agentSettingsScopeModel';
import { agentSettingsQueryKeys } from '../api/agentSettingsQueryKeys';

export type AgentFileTreeScope = AgentSelectedFile['scope'];
export type AgentFileTreeVisibleScope = AgentFileTreeScope | 'all';

export interface AgentFileConflictPayload {
  files: File[];
  sourcePath?: string;
  entryType?: 'file' | 'directory';
  content?: string;
}

export interface AgentFileTreeDataAdapterOptions {
  workspaceId: string;
  apiPrefix: 'claude-code' | 'codex' | 'opencode';
  scope: AgentFileTreeVisibleScope;
  scopes?: AgentFileTreeScope[];
  scopeLabels?: Partial<Record<AgentFileTreeScope, string>>;
  collection: AgentFileCollection;
  runtimeBaseUrl?: string | null;
  queryClient?: QueryClient;
}

const agentFileEndpoints = {
  getTree: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/tree?scope=${scope}&includeHidden=true`,
  getContent: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
  create: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}?scope=${scope}`,
  update: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
  delete: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string, recursive: boolean) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}?path=${encodeURIComponent(path)}&scope=${scope}&recursive=${recursive}`,
  move: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/move?scope=${scope}`,
  upload: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/upload`,
  extract: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/extract`,
  conflicts: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/conflicts/preflight?scope=${encodeURIComponent(scope)}`,
};

export class AgentFileTreeDataAdapter implements FileTreeDataAdapter {
  private readonly client: ApiClient;
  private readonly codexPluginIds = new Map<string, string>();

  constructor(private readonly options: AgentFileTreeDataAdapterOptions) {
    if (!options.workspaceId) {
      throw new Error('Missing Workspace ID');
    }

    this.client = options.runtimeBaseUrl
      ? new ApiClient({
        baseUrl: `${options.runtimeBaseUrl}/api/v1`,
        unauthorizedBehavior: 'propagate',
        executionAudience: 'workspace-runtime',
      })
      : apiClient;
  }

  async getTree(): Promise<FileTreeNode[]> {
    const runtimeBaseUrl = this.options.runtimeBaseUrl ?? '';
    const load = ({ signal }: { signal?: AbortSignal } = {}) => this.loadTree(signal);
    if (!this.options.queryClient || !runtimeBaseUrl) {
      return load();
    }
    return this.options.queryClient.fetchQuery({
      queryKey: agentSettingsQueryKeys.collection({
        runtimeBaseUrl,
        workspaceId: this.options.workspaceId,
        provider: this.options.apiPrefix,
        capability: this.options.collection,
        scope: this.options.scope,
      }),
      queryFn: load,
      staleTime: 5 * 60 * 1000,
    });
  }

  private async loadTree(signal?: AbortSignal): Promise<FileTreeNode[]> {
    const { workspaceId, apiPrefix, collection, scope, scopes = [], scopeLabels = {} } = this.options;
    if (scope === 'all') {
      if (apiPrefix === 'codex') {
        const nodes = await this.getCodexTree(
          workspaceId,
          collection,
          'all',
          signal,
        );
        return groupNodesByScope(nodes, scopes, scopeLabels);
      }
      if (apiPrefix === 'claude-code') {
        const nodes = await this.getScopedTree(
          workspaceId,
          apiPrefix,
          collection,
          'all',
          signal,
        );
        return groupNodesByScope(nodes, scopes, scopeLabels);
      }
      const trees = await Promise.all(scopes.map(async (scopeValue) => ({
        scope: scopeValue,
        nodes: await this.getScopedTree(
          workspaceId,
          apiPrefix,
          collection,
          scopeValue,
          signal,
        ),
      })));
      return trees
        .filter(({ nodes }) => nodes.length > 0)
        .map(({ scope: scopeValue, nodes }) => ({
          id: `scope:${scopeValue}`,
          name: scopeLabels[scopeValue] ?? scopeValue,
          path: `scope:${scopeValue}`,
          type: 'directory',
          scope: scopeValue,
          writable: false,
          hasChildren: nodes.length > 0,
          children: prefixScopeNodes(scopeValue, nodes),
        }));
    }
    if (apiPrefix === 'codex') {
      return this.getCodexTree(workspaceId, collection, scope, signal);
    }
    return this.getScopedTree(
      workspaceId,
      apiPrefix,
      collection,
      scope,
      signal,
    );
  }

  async getChildren(): Promise<FileTreeNode[]> {
    return [];
  }

  async getContent(path: string): Promise<string> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all') {
      throw new Error('Cannot read content from the aggregate scope');
    }
    if (apiPrefix === 'codex') {
      const codexScope = toCodexFileScope(scope);
      const query = new URLSearchParams({ scope: codexScope, path });
      const pluginId = this.codexPluginIds.get(path);
      if (pluginId) {
        query.set('pluginId', pluginId);
      }
      const response = await this.client.get<{ content?: string }>(
        `/workspaces/${workspaceId}/codex/${collection}/file?${query.toString()}`,
      );
      return response.content ?? '';
    }
    const response = await this.client.get<{ data?: { content?: string } }>(
      agentFileEndpoints.getContent(workspaceId, apiPrefix, collection, path, scope),
    );
    return response.data?.content ?? '';
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all') {
      throw new Error('Cannot create files in the aggregate scope');
    }
    if (apiPrefix === 'codex') {
      assertWritableAgentFileScope(scope);
      const codexScope = toCodexFileScope(scope);
      const normalizedPath = request.path.replace(/^\/+/, '');
      if (collection === 'skills') {
        const type = request.isDirectory ? 'directory' : 'file';
        const url = `/workspaces/${workspaceId}/codex/skills?scope=${encodeURIComponent(codexScope)}&path=${encodeURIComponent(normalizedPath)}&type=${type}`;
        if (request.isDirectory) {
          await this.client.post(url);
        } else {
          await this.client.post(url, { content: request.content ?? '' });
        }
      } else {
        await this.client.put(`/workspaces/${workspaceId}/codex/${collection}/file?scope=${codexScope}`, {
          path: normalizedPath,
          content: request.content ?? '',
        });
      }
      await this.invalidateCollection();
      return { success: true };
    }
    const baseUrl = agentFileEndpoints.create(workspaceId, apiPrefix, collection, scope);
    const url = `${baseUrl}&path=${encodeURIComponent(request.path)}&type=${request.isDirectory ? 'directory' : 'file'}${
      request.isDirectory || !request.content ? '' : `&content=${encodeURIComponent(request.content)}`
    }`;
    const response = await this.client.post<FileOperationResponse>(url);
    await this.invalidateCollection();
    return response;
  }

  async update(path: string, content: string): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all') {
      throw new Error('Cannot update files in the aggregate scope');
    }
    if (apiPrefix === 'codex') {
      assertWritableAgentFileScope(scope);
      const codexScope = toCodexFileScope(scope);
      await this.client.put(`/workspaces/${workspaceId}/codex/${collection}/file?scope=${codexScope}`, {
        path: path.replace(/^\/+/, ''),
        content,
      });
      await this.invalidateCollection();
      return { success: true };
    }
    const baseUrl = agentFileEndpoints.update(workspaceId, apiPrefix, collection, path, scope);
    const response = await this.client.put<FileOperationResponse>(
      `${baseUrl}&content=${encodeURIComponent(content)}`,
    );
    await this.invalidateCollection();
    return response;
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all') {
      throw new Error('Cannot delete files in the aggregate scope');
    }
    if (apiPrefix === 'codex') {
      assertWritableAgentFileScope(scope);
      const codexScope = toCodexFileScope(scope);
      await this.client.delete(`/workspaces/${workspaceId}/codex/${collection}/file?scope=${codexScope}&path=${encodeURIComponent(path.replace(/^\/+/, ''))}`);
      await this.invalidateCollection();
      return { success: true };
    }
    const response = await this.client.delete<FileOperationResponse>(
      agentFileEndpoints.delete(
        workspaceId,
        apiPrefix,
        collection,
        path,
        scope,
        recursive,
      ),
    );
    await this.invalidateCollection();
    return response;
  }

  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const results: BatchDeleteResponse = {
      success: true,
      deleted: [],
      failed: [],
      total: request.paths.length,
      successCount: 0,
      failedCount: 0,
    };

    for (const path of request.paths) {
      try {
        await this.delete(path, true);
        results.deleted.push(path);
        results.successCount += 1;
      } catch (error) {
        results.failed.push({
          path,
          error: error instanceof Error ? error.message : 'Delete failed',
        });
        results.failedCount += 1;
      }
    }

    results.success = results.failedCount === 0;
    return results;
  }

  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.postMove(sourcePath, targetPath);
  }

  async upload(options: FileUploadOptions): Promise<FileConflictBatchResult> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all' || isReadOnlyAgentScope(scope)) {
      throw new Error('READONLY_SCOPE');
    }
    const formData = new FormData();
    formData.append('targetPath', options.targetPath || '/');
    formData.append('scope', scope);
    formData.append('defaultStrategy', 'cancel');
    formData.append('resolutions', JSON.stringify([]));
    options.files.forEach(file => formData.append('files', file));

    const response = await this.client.post<FileConflictBatchResult>(
      agentFileEndpoints.upload(workspaceId, apiPrefix, collection),
      formData,
    );
    await this.invalidateCollection();
    return response;
  }

  createConflictTransport(): FileConflictWorkflowTransport<AgentFileConflictPayload> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const preflight = async (
      request: FileConflictPreflightRequest,
      requestOptions: { signal: AbortSignal },
    ): Promise<FileConflictPreflightResponse> => this.client.post(
      agentFileEndpoints.conflicts(workspaceId, apiPrefix, collection, scope),
      request,
      requestOptions,
    );

    const execute = async (
      request: FileConflictExecutionRequest<AgentFileConflictPayload>,
      requestOptions: { signal: AbortSignal },
    ): Promise<FileConflictBatchResult> => {
      if (request.operation === 'upload') {
        const formData = new FormData();
        formData.append('targetPath', request.targetPath || '/');
        formData.append('scope', scope);
        formData.append('defaultStrategy', request.defaultStrategy);
        formData.append('resolutions', JSON.stringify(request.resolutions));
        request.payload.files.forEach(file => formData.append('files', file));
        const response = await this.client.post<FileConflictBatchResult>(
          agentFileEndpoints.upload(workspaceId, apiPrefix, collection),
          formData,
          requestOptions,
        );
        await this.invalidateCollection();
        return response;
      }

      if (request.operation === 'extract') {
        const response = await this.client.post<FileConflictBatchResult>(
          agentFileEndpoints.extract(workspaceId, apiPrefix, collection),
          {
            archivePath: request.archivePath,
            targetPath: request.targetPath,
            scope,
            defaultStrategy: request.defaultStrategy,
            resolutions: request.resolutions,
          },
          requestOptions,
        );
        await this.invalidateCollection();
        return response;
      }

      throw new Error('Unsupported agent file conflict operation');
    };

    return { preflight, execute };
  }

  async download(_options: FileDownloadOptions): Promise<void> {
    throw new Error('Agent file collections do not support download');
  }

  async extractArchive(options: FileConflictExecutionFields & {
    archivePath: string;
    targetPath: string;
  }): Promise<FileConflictBatchResult> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all' || isReadOnlyAgentScope(scope)) {
      throw new Error('READONLY_SCOPE');
    }
    const response = await this.client.post<FileConflictBatchResult>(
      agentFileEndpoints.extract(workspaceId, apiPrefix, collection),
      {
        archivePath: options.archivePath,
        targetPath: options.targetPath,
        scope,
        defaultStrategy: options.defaultStrategy,
        resolutions: options.resolutions,
      },
    );
    await this.invalidateCollection();
    return response;
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    if (scope === 'all') {
      throw new Error('Cannot move files in the aggregate scope');
    }
    if (apiPrefix === 'codex') {
      return this.getContent(sourcePath)
        .then((content) => this.create({
          type: 'create',
          path: targetPath.replace(/^\/+/, ''),
          content,
          isDirectory: false,
        }))
        .then(async (response) => {
          await this.delete(sourcePath);
          return response;
        });
    }
    const baseUrl = agentFileEndpoints.move(workspaceId, apiPrefix, collection, scope);
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('sourcePath', sourcePath);
    url.searchParams.set('destPath', targetPath);
    url.searchParams.set('sourceScope', scope);
    url.searchParams.set('destScope', scope);
    url.searchParams.set('overwrite', 'false');
    return this.client.post(url.pathname + url.search);
  }

  private async getCodexTree(
    workspaceId: string,
    collection: AgentFileCollection,
    scope: AgentFileTreeScope | 'all',
    signal?: AbortSignal,
  ): Promise<FileTreeNode[]> {
    const codexScope = scope === 'all' ? 'all' : toCodexFileScope(scope);
    const path =
      `/workspaces/${workspaceId}/codex/${collection}/files?scope=${codexScope}`;
    const response = signal
      ? await this.client.get<CodexFileListResponse>(path, { signal })
      : await this.client.get<CodexFileListResponse>(path);
    const summaries = response.files.filter((file) => (
      scope === 'all'
      || (scope === 'plugin' ? file.source === 'plugin' : file.source === scope)
    ));
    this.codexPluginIds.clear();
    for (const summary of summaries) {
      const pluginId = summary.metadata?.pluginId;
      if (summary.source === 'plugin' && typeof pluginId === 'string') {
        this.codexPluginIds.set(summary.path, pluginId);
      }
    }
    if (scope === 'all') {
      return (['project', 'user', 'plugin'] as AgentFileTreeScope[])
        .flatMap((sourceScope) => buildTreeFromCodexSummaries(
          summaries.filter((summary) => summary.source === sourceScope),
        ).map((node) => ({ ...node, scope: sourceScope })));
    }
    return buildTreeFromCodexSummaries(summaries);
  }

  private async getScopedTree(
    workspaceId: string,
    apiPrefix: AgentFileTreeDataAdapterOptions['apiPrefix'],
    collection: AgentFileCollection,
    scope: AgentFileTreeScope | 'all',
    signal?: AbortSignal,
  ): Promise<FileTreeNode[]> {
    const path = agentFileEndpoints.getTree(
      workspaceId,
      apiPrefix,
      collection,
      scope,
    );
    const response = signal
      ? await this.client.get<unknown>(path, { signal })
      : await this.client.get<unknown>(path);
    return parseFileTree(response);
  }

  private async invalidateCollection(): Promise<void> {
    if (!this.options.queryClient) return;
    await this.options.queryClient.invalidateQueries({
      queryKey: agentSettingsQueryKeys.provider(
        this.options.runtimeBaseUrl ?? '',
        this.options.workspaceId,
        this.options.apiPrefix,
      ),
    });
  }
}

const prefixScopeNodes = (scope: AgentFileTreeScope, nodes: FileTreeNode[]): FileTreeNode[] =>
  nodes.map((node) => {
    const displayPath = `${scope}/${node.path.replace(/^\/+/, '')}`;
    return {
      ...node,
      id: `${scope}:${node.id || node.path}`,
      path: displayPath,
      scope: (node.scope as AgentFileTreeScope | undefined) ?? scope,
      metadata: {
        ...node.metadata,
        sourcePath: node.path,
        sourceScope: (node.scope as AgentFileTreeScope | undefined) ?? scope,
      },
      children: node.children ? prefixScopeNodes(scope, node.children) : undefined,
    };
  });

const groupNodesByScope = (
  nodes: FileTreeNode[],
  scopes: AgentFileTreeScope[],
  scopeLabels: Partial<Record<AgentFileTreeScope, string>>,
): FileTreeNode[] => scopes.flatMap((scope) => {
  const scopedNodes = nodes.filter((node) => node.scope === scope);
  if (scopedNodes.length === 0) return [];
  return [{
    id: `scope:${scope}`,
    name: scopeLabels[scope] ?? scope,
    path: `scope:${scope}`,
    type: 'directory' as const,
    scope,
    writable: false,
    hasChildren: true,
    children: prefixScopeNodes(scope, scopedNodes),
  }];
});

const assertWritableAgentFileScope = (scope: AgentFileTreeScope): void => {
  if (isReadOnlyAgentScope(scope)) {
    throw new Error('Cannot write files in a read-only scope');
  }
};

const buildTreeFromCodexSummaries = (summaries: CodexFileSummary[]): FileTreeNode[] => {
  const roots: FileTreeNode[] = [];
  const directories = new Map<string, FileTreeNode>();

  const ensureDirectory = (path: string): FileTreeNode => {
    const cleanPath = path.replace(/^\/+|\/+$/g, '');
    const existing = directories.get(cleanPath);
    if (existing) return existing;
    const name = cleanPath.split('/').pop() || cleanPath;
    const node: FileTreeNode = {
      id: cleanPath,
      name,
      path: cleanPath,
      type: 'directory',
      children: [],
      hasChildren: true,
    };
    directories.set(cleanPath, node);
    const parentPath = cleanPath.split('/').slice(0, -1).join('/');
    if (parentPath) {
      ensureDirectory(parentPath).children?.push(node);
    } else {
      roots.push(node);
    }
    return node;
  };

  for (const summary of summaries) {
    const cleanPath = summary.path.replace(/^\/+/, '');
    const parts = cleanPath.split('/').filter(Boolean);
    const fileName = parts.pop() || summary.name;
    const parentPath = parts.join('/');
    const node: FileTreeNode = {
      id: cleanPath,
      name: fileName,
      path: cleanPath,
      type: 'file',
      size: summary.sizeBytes,
      scope: summary.source === 'user' || summary.source === 'project' || summary.source === 'plugin'
        ? summary.source
        : 'plugin',
      writable: !summary.readOnly,
      extension: fileName.includes('.') ? fileName.split('.').pop() : undefined,
      metadata: summary.metadata,
      pluginId: typeof summary.metadata?.pluginId === 'string' ? summary.metadata.pluginId : undefined,
      pluginName: typeof summary.metadata?.pluginName === 'string' ? summary.metadata.pluginName : undefined,
      marketplaceName: typeof summary.metadata?.marketplaceName === 'string' ? summary.metadata.marketplaceName : undefined,
    };
    if (parentPath) {
      ensureDirectory(parentPath).children?.push(node);
    } else {
      roots.push(node);
    }
  }

  return sortTreeNodes(roots);
};

export const createAgentFileTreeDataAdapter = (
  options: AgentFileTreeDataAdapterOptions,
): AgentFileTreeDataAdapter => new AgentFileTreeDataAdapter(options);
