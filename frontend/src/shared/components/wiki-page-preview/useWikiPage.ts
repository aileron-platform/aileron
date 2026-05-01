import React from 'react';
import { apiClient } from '@/shared/api/apiClient';
import type { KnowledgeBaseWikiPageResponse } from '@/shared/types/knowledgeBase';

export function useWikiPage(kbId: string, path: string | null) {
  const [data, setData] = React.useState<KnowledgeBaseWikiPageResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);

  React.useEffect(() => {
    if (!path) {
      setData(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void apiClient.get<KnowledgeBaseWikiPageResponse>(
      `/knowledge-bases/${kbId}/wiki/page?path=${encodeURIComponent(path)}`,
    )
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError : new Error(String(loadError)));
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [kbId, path]);

  return { data, isLoading, error };
}
