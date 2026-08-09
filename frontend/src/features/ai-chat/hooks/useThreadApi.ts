import { useMemo } from 'react';
import { useAiChatIntegration } from '../contexts/AiChatIntegrationContext';
import { getThreadApi, ThreadApiError, type ThreadApi } from '../api/threadApi';

export const requireThreadApi = (api: ThreadApi | null): ThreadApi => {
  if (!api) {
    throw new ThreadApiError('runtime_unavailable');
  }
  return api;
};

export const useThreadApi = (runtimeBaseUrlOverride?: string | null): ThreadApi | null => {
  const integration = useAiChatIntegration();
  const runtimeBaseUrl = runtimeBaseUrlOverride
    ?? integration.runtimeBaseUrl
    ?? null;
  return useMemo(
    () => runtimeBaseUrl
      ? getThreadApi(runtimeBaseUrl)
      : null,
    [runtimeBaseUrl],
  );
};
