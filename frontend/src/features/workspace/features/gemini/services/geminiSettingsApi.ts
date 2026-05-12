import { ApiClient } from '@/shared/api/apiClient';

export type GeminiSettingsScope = 'user' | 'project';

export interface GeminiRawSettingsResponse {
  content: Record<string, unknown>;
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

export const geminiSettingsApi = {
  async getRawSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: GeminiSettingsScope,
  ): Promise<GeminiRawSettingsResponse> {
    return apiRequest<GeminiRawSettingsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/gemini/settings/raw?scope=${scope}`,
    );
  },

  async updateRawSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: GeminiSettingsScope,
    content: Record<string, unknown>,
  ): Promise<GeminiRawSettingsResponse> {
    return apiRequest<GeminiRawSettingsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/gemini/settings/raw?scope=${scope}`,
      { method: 'PUT', body: { content } },
    );
  },
};
