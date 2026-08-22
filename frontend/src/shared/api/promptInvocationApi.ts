import { ApiClient } from '@/shared/api/apiClient';
import type {
  PromptInvocationCatalog,
  PromptInvocationTool,
} from '@/shared/types/promptInvocations';

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => (
  new ApiClient({
    baseUrl: runtimeBaseUrl,
    unauthorizedBehavior: 'propagate',
    executionAudience: 'workspace-runtime',
  })
);

export const promptInvocationApi = {
  async list(
    runtimeBaseUrl: string,
    workspaceId: string,
    agenticTool: PromptInvocationTool,
  ): Promise<PromptInvocationCatalog> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return client.get<PromptInvocationCatalog>(
      `/api/v1/workspaces/${workspaceId}/cli-settings/${agenticTool}/prompt-invocations`,
    );
  },
};
