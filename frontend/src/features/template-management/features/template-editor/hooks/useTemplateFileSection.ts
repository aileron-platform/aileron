import { useCallback, useEffect, useState } from 'react';

interface UseTemplateFileSectionOptions<T> {
  templateId?: string;
  initialItems: T[];
  onItemsChange: (items: T[]) => void;
  loadItems?: () => Promise<T[]>;
  getIdentifier: (item: T) => string;
}

interface UseTemplateFileSectionResult<T> {
  items: T[];
  addItem: (item: T) => void;
  updateItem: (item: T) => void;
  removeItem: (item: T) => void;
}

function isSameItem<T>(itemA: T, itemB: T, getIdentifier: (item: T) => string) {
  return getIdentifier(itemA) === getIdentifier(itemB);
}

/**
 * 模板檔案區段管理 Hook
 * 提供基本的狀態管理功能，不包含自動儲存機制
 * 儲存操作由父組件明確調用 API 進行
 */
export function useTemplateFileSection<T>({
  templateId,
  initialItems,
  onItemsChange,
  loadItems,
  getIdentifier,
}: UseTemplateFileSectionOptions<T>): UseTemplateFileSectionResult<T> {
  const [items, setItems] = useState<T[]>(initialItems);

  // 同步初始值（建立階段由父層控制）
  useEffect(() => {
    if (templateId) {
      return;
    }
    setItems(initialItems);
  }, [initialItems, templateId]);

  // 載入已存在的配置
  useEffect(() => {
    if (!templateId || !loadItems) {
      return;
    }

    let isMounted = true;

    (async () => {
      const loadedItems = await loadItems();
      if (!isMounted) {
        return;
      }
      setItems(loadedItems);
    })();

    return () => {
      isMounted = false;
    };
  }, [templateId, loadItems]);

  const commit = useCallback(
    (nextItems: T[]) => {
      setItems(nextItems);
      // 通知父組件狀態變更
      onItemsChange(nextItems);
    },
    [onItemsChange],
  );

  const addItem = useCallback(
    (item: T) => {
      const nextItems = [...items, item];
      commit(nextItems);
    },
    [commit, items],
  );

  const updateItem = useCallback(
    (item: T) => {
      commit(items.map(existing => (isSameItem(existing, item, getIdentifier) ? item : existing)));
    },
    [commit, items, getIdentifier],
  );

  const removeItem = useCallback(
    (item: T) => {
      commit(items.filter(existing => !isSameItem(existing, item, getIdentifier)));
    },
    [commit, items, getIdentifier],
  );

  return {
    items,
    addItem,
    updateItem,
    removeItem,
  };
}

export default useTemplateFileSection;
