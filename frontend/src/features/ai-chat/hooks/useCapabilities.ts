import { useQuery } from '@tanstack/react-query';
import { aiChatCapabilitiesQueryKey } from '../api/threadQueryKeys';
import { requireThreadApi, useThreadApi } from './useThreadApi';

export const useCapabilities = (workspaceId: string) => {
  const api = useThreadApi();
  return useQuery({
    queryKey: aiChatCapabilitiesQueryKey(workspaceId),
    queryFn: () => requireThreadApi(api).getCapabilities(workspaceId),
    enabled: workspaceId.length > 0 && api !== null,
  });
};
