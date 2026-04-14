/**
 * 虛擬滾動 Hook
 * 
 * 基於 @tanstack/react-virtual 的封裝，提供更簡單的 API
 */

import { useVirtualizer, VirtualizerOptions } from '@tanstack/react-virtual';
import { useRef, useEffect, MutableRefObject } from 'react';

interface UseVirtualListOptions<T> {
  items: T[];
  estimateSize?: number;
  overscan?: number;
  onLoadMore?: () => void;
  hasMore?: boolean;
  isLoading?: boolean;
  threshold?: number; // 距離底部多少像素時觸發載入更多
}

interface UseVirtualListReturn<T> {
  parentRef: MutableRefObject<HTMLDivElement | null>;
  virtualizer: ReturnType<typeof useVirtualizer>;
  items: T[];
  totalSize: number;
  virtualItems: ReturnType<typeof useVirtualizer>['getVirtualItems'];
}

/**
 * 虛擬列表 Hook
 * 
 * @example
 * ```tsx
 * const { parentRef, virtualizer, virtualItems } = useVirtualList({
 *   items: files,
 *   estimateSize: 40,
 *   overscan: 5,
 *   onLoadMore: loadMore,
 *   hasMore: true,
 * });
 * 
 * return (
 *   <div ref={parentRef} style={{ height: '400px', overflow: 'auto' }}>
 *     <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
 *       {virtualItems().map(virtualRow => (
 *         <div
 *           key={virtualRow.key}
 *           style={{
 *             position: 'absolute',
 *             top: 0,
 *             left: 0,
 *             width: '100%',
 *             height: `${virtualRow.size}px`,
 *             transform: `translateY(${virtualRow.start}px)`,
 *           }}
 *         >
 *           {items[virtualRow.index]}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * );
 * ```
 */
export function useVirtualList<T>({
  items,
  estimateSize = 40,
  overscan = 5,
  onLoadMore,
  hasMore = false,
  isLoading = false,
  threshold = 200,
}: UseVirtualListOptions<T>): UseVirtualListReturn<T> {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
  });

  // 無限滾動：當接近底部時載入更多
  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoading) return;

    const virtualItems = virtualizer.getVirtualItems();

    // 邊界檢查：確保有虛擬項目
    if (virtualItems.length === 0) return;

    const [lastItem] = [...virtualItems].reverse();
    if (!lastItem) return;

    // 檢查是否接近底部
    const scrollElement = parentRef.current;
    if (!scrollElement) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollElement;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    if (distanceFromBottom < threshold && lastItem.index >= items.length - 1 - overscan) {
      onLoadMore();
    }
  }, [
    virtualizer.getVirtualItems(),
    items.length,
    onLoadMore,
    hasMore,
    isLoading,
    threshold,
    overscan,
  ]);

  return {
    parentRef,
    virtualizer,
    items,
    totalSize: virtualizer.getTotalSize(),
    virtualItems: virtualizer.getVirtualItems,
  };
}

/**
 * 固定大小虛擬列表 Hook（效能更好）
 */
export function useFixedVirtualList<T>({
  items,
  itemHeight,
  overscan = 5,
  onLoadMore,
  hasMore = false,
  isLoading = false,
  threshold = 200,
}: Omit<UseVirtualListOptions<T>, 'estimateSize'> & { itemHeight: number }): UseVirtualListReturn<T> {
  return useVirtualList({
    items,
    estimateSize: itemHeight,
    overscan,
    onLoadMore,
    hasMore,
    isLoading,
    threshold,
  });
}

/**
 * 動態大小虛擬列表 Hook
 * 
 * 適用於項目高度不固定的情況
 */
export function useDynamicVirtualList<T>({
  items,
  measureElement,
  overscan = 5,
  onLoadMore,
  hasMore = false,
  isLoading = false,
  threshold = 200,
}: Omit<UseVirtualListOptions<T>, 'estimateSize'> & {
  measureElement?: (element: Element) => void;
}): UseVirtualListReturn<T> {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50, // 預估高度
    overscan,
    measureElement,
  });

  // 無限滾動邏輯
  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoading) return;

    const [lastItem] = [...virtualizer.getVirtualItems()].reverse();
    if (!lastItem) return;

    const scrollElement = parentRef.current;
    if (!scrollElement) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollElement;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    if (distanceFromBottom < threshold && lastItem.index >= items.length - 1 - overscan) {
      onLoadMore();
    }
  }, [
    virtualizer.getVirtualItems(),
    items.length,
    onLoadMore,
    hasMore,
    isLoading,
    threshold,
    overscan,
  ]);

  return {
    parentRef,
    virtualizer,
    items,
    totalSize: virtualizer.getTotalSize(),
    virtualItems: virtualizer.getVirtualItems,
  };
}

/**
 * 水平虛擬列表 Hook
 */
export function useHorizontalVirtualList<T>({
  items,
  estimateSize = 100,
  overscan = 5,
}: Pick<UseVirtualListOptions<T>, 'items' | 'estimateSize' | 'overscan'>): UseVirtualListReturn<T> {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    horizontal: true,
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
  });

  return {
    parentRef,
    virtualizer,
    items,
    totalSize: virtualizer.getTotalSize(),
    virtualItems: virtualizer.getVirtualItems,
  };
}

