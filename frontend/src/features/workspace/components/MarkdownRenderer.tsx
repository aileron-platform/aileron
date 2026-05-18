import React, { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { parseWorkspaceFileHref } from '@/shared/components/markdown/markdownLinkUtils';
import { useWorkspaceOptional } from '@/features/workspace/providers/WorkspaceContext';

interface MarkdownRendererProps {
  content: string;
}

const FILE_MANAGEMENT_ROUTE = '/workspaces/file-management';

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const workspace = useWorkspaceOptional();
  const navigate = useNavigate();
  const openFileInTab = workspace?.openFileInTab;

  const handleLinkClick = useCallback(
    (href: string, event: React.MouseEvent<HTMLAnchorElement>) => {
      if (!openFileInTab) {
        return;
      }
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const origin = typeof window === 'undefined' ? '' : window.location.origin;
      const target = parseWorkspaceFileHref(href, origin);
      if (!target) {
        return;
      }
      event.preventDefault();
      openFileInTab(target.filePath, undefined, 'file-management');
      if (workspace?.state.currentFeature !== 'file-management') {
        navigate(FILE_MANAGEMENT_ROUTE);
      }
    },
    [navigate, openFileInTab, workspace?.state.currentFeature],
  );

  return <MarkdownContent content={content} variant="chat" onLinkClick={handleLinkClick} />;
};
