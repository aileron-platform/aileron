import type { Query, QueryClient } from '@tanstack/react-query';

const isSensitiveAgentSettingsQuery = (query: Query): boolean => {
  const { queryKey } = query;
  if (queryKey[0] === 'raw-settings') {
    return true;
  }
  return (
    queryKey[0] === 'agent-settings'
    && queryKey[4] === 'mcp'
  );
};

export const clearSensitiveAgentSettingsQueries = (
  queryClient: QueryClient,
): void => {
  const filters = { predicate: isSensitiveAgentSettingsQuery };
  void queryClient.cancelQueries(filters);
  queryClient.removeQueries(filters);
};
