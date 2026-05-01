import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/shared/constants/routes';
import { WikiGraphExplorer } from './graph/WikiGraphExplorer';
import { DEFAULT_WIKI_PATH } from './graph/graphUtils';

interface KnowledgeBaseGraphTabProps {
  knowledgeBaseId: string;
}

export const KnowledgeBaseGraphTab: React.FC<KnowledgeBaseGraphTabProps> = ({ knowledgeBaseId }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = React.useMemo(() => new URLSearchParams(location.search), [location.search]);
  const selectedPath = searchParams.get('path') || DEFAULT_WIKI_PATH;

  const setSelectedPath = React.useCallback((path: string) => {
    const params = new URLSearchParams(location.search);
    params.set('path', path);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: false });
  }, [location.pathname, location.search, navigate]);

  React.useEffect(() => {
    if (!searchParams.get('path')) {
      const params = new URLSearchParams(location.search);
      params.set('path', DEFAULT_WIKI_PATH);
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
  }, [location.pathname, location.search, navigate, searchParams]);

  return (
    <WikiGraphExplorer
      knowledgeBaseId={knowledgeBaseId}
      selectedPath={selectedPath}
      onSelectedPathChange={setSelectedPath}
      onOpenInWiki={(path) => navigate(`${ROUTES.KNOWLEDGE_BASE_DETAIL_WIKI(knowledgeBaseId)}?path=${encodeURIComponent(path)}`)}
      onSourceOpen={(path) => navigate(`${ROUTES.KNOWLEDGE_BASE_DETAIL_FILES(knowledgeBaseId)}?file=${encodeURIComponent(path)}`)}
    />
  );
};

export default KnowledgeBaseGraphTab;
