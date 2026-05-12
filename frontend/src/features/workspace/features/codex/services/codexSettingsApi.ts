import { ApiClient } from '@/shared/api/apiClient';

export type CodexConfigLayer = 'user' | 'project';

export interface CodexRawConfigResponse {
  workspaceId?: string;
  layer: CodexConfigLayer;
  path?: string;
  content: string;
}

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => new ApiClient({ baseUrl: runtimeBaseUrl });

const apiRequest = async <T>(
  runtimeBaseUrl: string,
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    headers?: Record<string, string>;
  },
): Promise<T> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;
  const method = options?.method ?? 'GET';

  switch (method) {
    case 'GET':
      return client.get<T>(fullPath, options?.headers);
    case 'POST':
      return client.post<T>(fullPath, options?.body, options?.headers);
    case 'PUT':
      return client.put<T>(fullPath, options?.body, options?.headers);
    case 'PATCH':
      return client.patch<T>(fullPath, options?.body, options?.headers);
    case 'DELETE':
      return client.delete<T>(fullPath, options?.headers);
    default:
      throw new Error(`Unsupported HTTP method: ${method}`);
  }
};

export const codexSettingsApi = {
  async getRawConfig(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: CodexConfigLayer,
  ): Promise<CodexRawConfigResponse> {
    return apiRequest<CodexRawConfigResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config?layer=${layer}`,
    );
  },

  async updateRawConfig(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: CodexConfigLayer,
    content: string,
  ): Promise<CodexRawConfigResponse> {
    return apiRequest<CodexRawConfigResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config?layer=${layer}`,
      { method: 'PUT', body: { content } },
    );
  },

  async saveConfigSection(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: CodexConfigLayer,
    section: string,
    data: Record<string, unknown>,
  ): Promise<unknown> {
    return apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/config/${section}?layer=${layer}`,
      { method: 'PUT', body: { data } },
    );
  },
};
