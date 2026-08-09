import { useCallback, useEffect, useState } from 'react';
import type { WorkspaceFeature } from '../../providers/workspaceStateTypes';

interface UseWorkspaceDocumentSelectionOptions {
  currentFeature: WorkspaceFeature;
  agentToolSubView: string;
}

export const useWorkspaceDocumentSelection = ({
  currentFeature,
  agentToolSubView,
}: UseWorkspaceDocumentSelectionOptions) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [selectionBlocked, setSelectionBlocked] = useState(false);

  const handleSelect = useCallback((id: string | null) => {
    if (isDirty) {
      setSelectionBlocked(true);
      return;
    }
    setSelectionBlocked(false);
    setSelectedId(id);
  }, [isDirty]);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
    if (!dirty) {
      setSelectionBlocked(false);
    }
  }, []);

  useEffect(() => {
    setSelectedId(null);
    setIsDirty(false);
    setSelectionBlocked(false);
  }, [currentFeature, agentToolSubView]);

  return {
    selectedId,
    selectionBlocked,
    handleSelect,
    handleDirtyChange,
  };
};
