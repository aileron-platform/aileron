import React from 'react';

import { downloadBlob } from '../../utils/downloadBlob';
import {
  getMarketplaceItemFileName,
  marketplaceEditorItemDescription,
  type MarketplaceEditorResourceItem,
  type MarketplaceResourceFormat,
} from './marketplaceEditorResourceItems';

export interface MarketplaceMarkdownSidebarItem {
  id: string;
  label: string;
  description: string;
  contentLength: number;
  searchText: string;
}

export interface MarketplaceMarkdownEditorTranslate {
  (key: string, values?: Record<string, unknown>): string;
}

interface UseMarketplaceMarkdownEditorStateArgs {
  format: MarketplaceResourceFormat;
  items: MarketplaceEditorResourceItem[];
  commitVersion: number;
  discardVersion: number;
  t: MarketplaceMarkdownEditorTranslate;
  onDirty: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

export interface UseMarketplaceMarkdownEditorStateResult {
  search: string;
  setSearch: React.Dispatch<React.SetStateAction<string>>;
  renameItem: MarketplaceEditorResourceItem | null;
  setRenameItem: React.Dispatch<React.SetStateAction<MarketplaceEditorResourceItem | null>>;
  createDialogOpen: boolean;
  setCreateDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  sidebarItems: MarketplaceMarkdownSidebarItem[];
  dirtyItemIds: Set<string>;
  filteredItems: MarketplaceEditorResourceItem[];
  selectedItem: MarketplaceEditorResourceItem | null;
  selectedContent: string;
  isSelectedDirty: boolean;
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  handleSelectPrevious: () => void;
  handleSelectNext: () => void;
  handleSelectItem: (id: string) => void;
  handleCreate: (value: { path: string; content: string }) => void;
  handleRenameSubmit: (nextPath: string) => void;
  handleContentChange: (value: string) => void;
  handleCopy: () => Promise<void>;
  handleDownload: () => void;
}

const materializeItems = (
  nextItems: MarketplaceEditorResourceItem[],
  nextDrafts: Record<string, string>,
): MarketplaceEditorResourceItem[] => (
  nextItems.map(item => ({
    ...item,
    content: nextDrafts[item.id] ?? item.content,
  }))
);

const marketplaceDefaultItemId = () => `local-${Math.random().toString(36).slice(2, 10)}`;

export const useMarketplaceMarkdownEditorState = ({
  format,
  items,
  commitVersion,
  discardVersion,
  t,
  onDirty,
  onItemsChange,
}: UseMarketplaceMarkdownEditorStateArgs): UseMarketplaceMarkdownEditorStateResult => {
  const [baseItems, setBaseItems] = React.useState(items);
  const [localItems, setLocalItems] = React.useState(items);
  const [selectedId, setSelectedId] = React.useState(items[0]?.id ?? null);
  const [search, setSearch] = React.useState('');
  const [renameItem, setRenameItem] = React.useState<MarketplaceEditorResourceItem | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [drafts, setDrafts] = React.useState<Record<string, string>>(
    () => Object.fromEntries(items.map(item => [item.id, item.content])),
  );
  const didMountRef = React.useRef(false);
  const baseItemsRef = React.useRef(baseItems);
  const localItemsRef = React.useRef(localItems);
  const draftsRef = React.useRef(drafts);

  React.useEffect(() => {
    baseItemsRef.current = baseItems;
  }, [baseItems]);

  React.useEffect(() => {
    localItemsRef.current = localItems;
  }, [localItems]);

  React.useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  const emitItemsChange = React.useCallback((
    nextItems: MarketplaceEditorResourceItem[],
    nextDrafts: Record<string, string>,
  ) => {
    onItemsChange?.(materializeItems(nextItems, nextDrafts));
  }, [onItemsChange]);

  React.useEffect(() => {
    setBaseItems(items);
    setLocalItems(items);
    setDrafts(Object.fromEntries(items.map(item => [item.id, item.content])));
    setSelectedId(items[0]?.id ?? null);
  }, [items]);

  React.useEffect(() => {
    if (!didMountRef.current) return;
    const nextLocalItems = localItemsRef.current;
    const nextDrafts = draftsRef.current;
    setBaseItems(nextLocalItems.map(item => ({
      ...item,
      content: nextDrafts[item.id] ?? item.content,
    })));
    setLocalItems(prev => prev.map(item => ({
      ...item,
      content: nextDrafts[item.id] ?? item.content,
    })));
  }, [commitVersion]);

  React.useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    const nextBaseItems = baseItemsRef.current;
    setLocalItems(nextBaseItems);
    setDrafts(Object.fromEntries(nextBaseItems.map(item => [item.id, item.content])));
    setSelectedId(prev => (prev && nextBaseItems.some(item => item.id === prev) ? prev : nextBaseItems[0]?.id ?? null));
  }, [discardVersion]);

  const dirtyItemIds = React.useMemo(() => {
    const baseById = new Map(baseItems.map(item => [item.id, item]));
    return new Set(localItems.filter(item => {
      const baseItem = baseById.get(item.id);
      if (!baseItem) return true;
      return baseItem.path !== item.path || baseItem.content !== (drafts[item.id] ?? item.content);
    }).map(item => item.id));
  }, [baseItems, drafts, localItems]);

  const filteredItems = React.useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return localItems;
    return localItems.filter(item => (
      getMarketplaceItemFileName(item).toLowerCase().includes(query) ||
      marketplaceEditorItemDescription(item, t).toLowerCase().includes(query) ||
      (drafts[item.id] ?? item.content).toLowerCase().includes(query)
    ));
  }, [drafts, localItems, search, t]);

  const sidebarItems = React.useMemo<MarketplaceMarkdownSidebarItem[]>(
    () => localItems.map((item) => {
      const content = drafts[item.id] ?? item.content;
      return {
        id: item.id,
        label: getMarketplaceItemFileName(item),
        description: marketplaceEditorItemDescription(item, t),
        contentLength: content.length,
        searchText: [
          getMarketplaceItemFileName(item),
          marketplaceEditorItemDescription(item, t),
          content,
          item.path,
        ].join(' '),
      };
    }),
    [drafts, localItems, t],
  );

  React.useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredItems.some(item => item.id === selectedId)) {
      setSelectedId(filteredItems[0].id);
    }
  }, [filteredItems, selectedId]);

  const selectedItem = filteredItems.find(item => item.id === selectedId) ?? null;
  const currentIndex = selectedItem ? filteredItems.findIndex(item => item.id === selectedItem.id) : -1;
  const canNavigatePrevious = currentIndex > 0;
  const canNavigateNext = currentIndex >= 0 && currentIndex < filteredItems.length - 1;
  const selectedContent = selectedItem ? (drafts[selectedItem.id] ?? selectedItem.content) : '';
  const isSelectedDirty = selectedItem ? dirtyItemIds.has(selectedItem.id) : false;

  const handleSelectPrevious = React.useCallback(() => {
    if (currentIndex <= 0) return;
    setSelectedId(filteredItems[currentIndex - 1].id);
  }, [currentIndex, filteredItems]);

  const handleSelectNext = React.useCallback(() => {
    if (currentIndex < 0 || currentIndex >= filteredItems.length - 1) return;
    setSelectedId(filteredItems[currentIndex + 1].id);
  }, [currentIndex, filteredItems]);

  const handleSelectItem = React.useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleCopy = React.useCallback(async () => {
    if (!selectedItem) return;
    await navigator.clipboard.writeText(selectedContent);
  }, [selectedContent, selectedItem]);

  const handleDownload = React.useCallback(() => {
    if (!selectedItem) return;
    const blob = new Blob([selectedContent], { type: format === 'toml' ? 'application/toml' : 'text/markdown' });
    downloadBlob(blob, getMarketplaceItemFileName(selectedItem));
  }, [format, selectedContent, selectedItem]);

  const handleCreate = React.useCallback((value: { path: string; content: string }) => {
    const id = marketplaceDefaultItemId();
    const nextItem: MarketplaceEditorResourceItem = {
      id,
      titleKey: 'marketplace.editor.documentViewer.create.defaultTitle',
      descriptionKey: 'marketplace.editor.documentViewer.create.defaultDescription',
      title: value.path,
      description: value.path,
      path: value.path,
      content: value.content,
      badge: format === 'toml' ? 'toml' : 'md',
    };
    const nextItems = [...localItems, nextItem];
    const nextDrafts = { ...drafts, [id]: value.content };
    setLocalItems(nextItems);
    setDrafts(nextDrafts);
    setSelectedId(id);
    setCreateDialogOpen(false);
    emitItemsChange(nextItems, nextDrafts);
    onDirty();
  }, [drafts, emitItemsChange, format, localItems, onDirty]);

  const handleRenameSubmit = React.useCallback((nextPath: string) => {
    if (!renameItem) return;
    const nextItems = localItems.map(item => (
      item.id === renameItem.id ? { ...item, path: nextPath } : item
    ));
    setLocalItems(nextItems);
    setRenameItem(null);
    emitItemsChange(nextItems, drafts);
    onDirty();
  }, [drafts, emitItemsChange, localItems, onDirty, renameItem]);

  const handleContentChange = React.useCallback((value: string) => {
    if (!selectedItem) return;
    const nextDrafts = { ...drafts, [selectedItem.id]: value };
    setDrafts(nextDrafts);
    emitItemsChange(localItems, nextDrafts);
    onDirty();
  }, [drafts, emitItemsChange, localItems, onDirty, selectedItem]);

  return {
    search,
    setSearch,
    renameItem,
    setRenameItem,
    createDialogOpen,
    setCreateDialogOpen,
    sidebarItems,
    dirtyItemIds,
    filteredItems,
    selectedItem,
    selectedContent,
    isSelectedDirty,
    canNavigatePrevious,
    canNavigateNext,
    handleSelectPrevious,
    handleSelectNext,
    handleSelectItem,
    handleCreate,
    handleRenameSubmit,
    handleContentChange,
    handleCopy,
    handleDownload,
  };
};
