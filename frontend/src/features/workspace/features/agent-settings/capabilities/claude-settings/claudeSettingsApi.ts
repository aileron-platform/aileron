import { ApiClient } from '@/shared/api/apiClient';
import { parseResourceError, type ResourceError } from '@/shared/components/document-resource';

export type ClaudeSettingsScope = 'local' | 'project' | 'user';

export interface ClaudeRawSettingsResponse {
  scope: ClaudeSettingsScope;
  path?: string;
  content: Record<string, unknown>;
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
    method?: 'GET' | 'PUT';
    body?: unknown;
    headers?: Record<string, string>;
  },
): Promise<T> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;
  const method = options?.method ?? 'GET';

  try {
    if (method === 'GET') return await client.get<T>(fullPath, options?.headers);
    if (method === 'PUT') return await client.put<T>(fullPath, options?.body, options?.headers);
    throw new Error(`Unsupported HTTP method: ${method}`);
  } catch (err) {
    const parsed = parseResourceError(err);
    const error = new Error(parsed.message) as Error & ResourceError;
    if (parsed.errorCode) error.errorCode = parsed.errorCode;
    if (parsed.validationResults) error.validationResults = parsed.validationResults;
    throw error;
  }
};

export const claudeSettingsApi = {
  async getRawSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: ClaudeSettingsScope,
  ): Promise<ClaudeRawSettingsResponse> {
    return apiRequest<ClaudeRawSettingsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/settings/raw?scope=${scope}`,
    );
  },

  async updateRawSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: ClaudeSettingsScope,
    content: Record<string, unknown>,
  ): Promise<ClaudeRawSettingsResponse> {
    return apiRequest<ClaudeRawSettingsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/settings/raw?scope=${scope}`,
      {
        method: 'PUT',
        body: { content },
      },
    );
  },
};
