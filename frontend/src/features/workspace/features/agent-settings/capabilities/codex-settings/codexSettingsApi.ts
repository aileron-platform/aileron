import { ApiClient } from '@/shared/api/apiClient';
import { parseResourceError, type ResourceError } from '@/shared/components/document-resource';

export type CodexConfigLayer = 'user' | 'project';

export interface CodexRawConfigResponse {
  workspaceId?: string;
  scope: CodexConfigLayer;
  path?: string;
  content: string;
  exists?: boolean;
  revision?: string;
}

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => new ApiClient({
  baseUrl: runtimeBaseUrl,
  unauthorizedBehavior: 'propagate',
  executionAudience: 'workspace-runtime',
});

const apiRequest = async <T>(
  runtimeBaseUrl: string,
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<T> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;
  const method = options?.method ?? 'GET';

  try {
    switch (method) {
      case 'GET':
        return await client.get<T>(fullPath, { headers: options?.headers, signal: options?.signal });
      case 'POST':
        return await client.post<T>(fullPath, options?.body, options?.headers);
      case 'PUT':
        return await client.put<T>(fullPath, options?.body, options?.headers);
      case 'PATCH':
        return await client.patch<T>(fullPath, options?.body, options?.headers);
      case 'DELETE':
        return await client.delete<T>(fullPath, options?.headers);
      default:
        throw new Error(`Unsupported HTTP method: ${method}`);
    }
  } catch (err) {
    const parsed = parseResourceError(err);
    const error = new Error(parsed.message) as Error & ResourceError;
    if (parsed.errorCode) error.errorCode = parsed.errorCode;
    if (parsed.validationResults) error.validationResults = parsed.validationResults;
    throw error;
  }
};

export const codexSettingsApi = {
  async getRawConfig(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: CodexConfigLayer,
    options?: { signal?: AbortSignal },
  ): Promise<CodexRawConfigResponse> {
    return apiRequest<CodexRawConfigResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config?scope=${scope}`,
      { signal: options?.signal },
    );
  },

  async updateRawConfig(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: CodexConfigLayer,
    content: string,
  ): Promise<CodexRawConfigResponse> {
    return apiRequest<CodexRawConfigResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config?scope=${scope}`,
      { method: 'PUT', body: { content } },
    );
  },

  async saveConfigSection(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: CodexConfigLayer,
    section: string,
    data: Record<string, unknown>,
  ): Promise<unknown> {
    return apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config/${section}?scope=${scope}`,
      { method: 'PUT', body: { data } },
    );
  },
};
