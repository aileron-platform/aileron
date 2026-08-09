import { useCallback, useMemo, useState } from 'react';

export type SettingsListEditorMode = 'create' | 'edit';
export type SettingsListScope = string;

export interface SettingsListControllerOptions<TItem, TSeed = Partial<TItem>> {
  defaultScope?: SettingsListScope;
  getScope?: (item: TItem) => SettingsListScope | undefined;
  getSearchText?: (item: TItem) => Array<string | null | undefined>;
}

export interface SettingsListController<TItem, TSeed = Partial<TItem>> {
  filteredItems: TItem[];
  selectedItem: TItem | null;
  scope: SettingsListScope;
  setScope: (scope: SettingsListScope) => void;
  query: string;
  setQuery: (query: string) => void;
  editorMode: SettingsListEditorMode;
  editorOpen: boolean;
  editorSeed: TSeed | null;
  openCreate: (seed?: TSeed) => void;
  openEdit: (item: TItem) => void;
  closeEditor: () => void;
}

const defaultGetSearchText = <TItem,>(item: TItem): Array<string | null | undefined> => {
  const record = item as Record<string, unknown>;
  return [
    typeof record.name === 'string' ? record.name : undefined,
    typeof record.description === 'string' ? record.description : undefined,
  ];
};

export function useSettingsListController<TItem, TSeed = Partial<TItem>>(
  items: TItem[],
  options: SettingsListControllerOptions<TItem, TSeed> = {},
): SettingsListController<TItem, TSeed> {
  const {
    defaultScope = 'all',
    getScope = (item) => {
      const record = item as Record<string, unknown>;
      return typeof record.scope === 'string' ? record.scope : undefined;
    },
    getSearchText = defaultGetSearchText,
  } = options;

  const [scope, setScope] = useState(defaultScope);
  const [query, setQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState<TItem | null>(null);
  const [editorMode, setEditorMode] = useState<SettingsListEditorMode>('create');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorSeed, setEditorSeed] = useState<TSeed | null>(null);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return items.filter((item) => {
      if (scope !== 'all' && getScope(item) !== scope) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      return getSearchText(item)
        .filter((value): value is string => typeof value === 'string')
        .some((value) => value.toLowerCase().includes(normalizedQuery));
    });
  }, [getScope, getSearchText, items, query, scope]);

  const openCreate = useCallback((seed?: TSeed) => {
    setEditorMode('create');
    setEditorSeed(seed ?? null);
    setSelectedItem(null);
    setEditorOpen(true);
  }, []);

  const openEdit = useCallback((item: TItem) => {
    setEditorMode('edit');
    setEditorSeed(null);
    setSelectedItem(item);
    setEditorOpen(true);
  }, []);

  const closeEditor = useCallback(() => {
    setEditorOpen(false);
    setSelectedItem(null);
    setEditorSeed(null);
  }, []);

  return {
    filteredItems,
    selectedItem,
    scope,
    setScope,
    query,
    setQuery,
    editorMode,
    editorOpen,
    editorSeed,
    openCreate,
    openEdit,
    closeEditor,
  };
}
