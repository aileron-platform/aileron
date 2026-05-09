import { useState } from 'react';

export interface UseResourceSidebarControllerOptions {
  initialQuery?: string;
  initialCollapsed?: boolean;
  initialSelectedId?: string | null;
}

export const useResourceSidebarController = (options: UseResourceSidebarControllerOptions = {}) => {
  const [query, setQuery] = useState(options.initialQuery ?? '');
  const [collapsed, setCollapsed] = useState(options.initialCollapsed ?? false);
  const [selectedId, setSelectedId] = useState<string | null>(options.initialSelectedId ?? null);

  return {
    query,
    setQuery,
    collapsed,
    setCollapsed,
    selectedId,
    setSelectedId,
  };
};

export default useResourceSidebarController;
