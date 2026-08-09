import { apiClient } from '@/shared/api/apiClient';

export interface BrowserExtensionPairingAssertionResponse {
  assertion: string;
  runtimeInstanceId: string;
}

export const workspaceBrowserExtensionApi = {
  async createPairingAssertion(
    workspaceId: string
  ): Promise<BrowserExtensionPairingAssertionResponse> {
    return await apiClient.post<BrowserExtensionPairingAssertionResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/browser-extension-pairing-assertions`
    );
  },
};
