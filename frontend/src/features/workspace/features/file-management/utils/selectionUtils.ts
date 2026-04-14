/**
 * 檔案選擇工具函數
 * 提供範圍選擇、可見節點取得等功能
 *
 * 使用泛型支援不同的節點型別，只要符合基本的節點介面即可
 */

/**
 * 基本節點介面，所有節點型別都必須符合此介面
 */
export interface BaseFileNode {
  path: string;
  type: 'file' | 'directory';
  children?: BaseFileNode[];
}

/**
 * 取得所有可見的檔案節點（扁平化）
 * 只包含當前展開狀態下可見的節點
 *
 * @param nodes 檔案樹節點
 * @param expandedNodes 展開的節點集合
 * @returns 扁平化的可見節點列表
 */
export function getVisibleFileNodes<T extends BaseFileNode>(
  nodes: T[],
  expandedNodes: Set<string>
): T[] {
  const result: T[] = [];

  function traverse(nodeList: T[]) {
    for (const node of nodeList) {
      result.push(node);

      // 如果是資料夾且已展開，遍歷子節點
      if (node.type === 'directory' &&
          node.children &&
          expandedNodes.has(node.path)) {
        traverse(node.children as T[]);
      }
    }
  }

  traverse(nodes);
  return result;
}

/**
 * 計算範圍選擇的檔案路徑
 * 從起始路徑到結束路徑之間的所有節點（包含資料夾和檔案）
 *
 * @param nodes 所有可見的檔案節點（扁平化）
 * @param fromPath 起始路徑
 * @param toPath 結束路徑
 * @returns 範圍內的所有節點路徑
 */
export function calculateRangeSelection<T extends BaseFileNode>(
  nodes: T[],
  fromPath: string,
  toPath: string
): string[] {
  // 選擇所有節點（包含資料夾和檔案）
  const fromIndex = nodes.findIndex(node => node.path === fromPath);
  const toIndex = nodes.findIndex(node => node.path === toPath);

  // 如果找不到起始或結束節點，返回空陣列
  if (fromIndex === -1 || toIndex === -1) {
    return [];
  }

  // 確保起始索引小於結束索引
  const startIndex = Math.min(fromIndex, toIndex);
  const endIndex = Math.max(fromIndex, toIndex);

  // 返回範圍內的所有節點路徑
  return nodes
    .slice(startIndex, endIndex + 1)
    .map(node => node.path);
}

/**
 * 取得所有節點（包含資料夾和檔案）
 * 遞迴遍歷整個檔案樹
 *
 * @param nodes 檔案樹節點
 * @returns 所有節點
 */
export function getAllFileNodes<T extends BaseFileNode>(nodes: T[]): T[] {
  const result: T[] = [];

  function traverse(nodeList: T[]) {
    for (const node of nodeList) {
      // 包含所有節點（資料夾和檔案）
      result.push(node);

      if (node.children) {
        traverse(node.children as T[]);
      }
    }
  }

  traverse(nodes);
  return result;
}

/**
 * 取得資料夾下的所有子節點路徑（遞迴）
 *
 * @param node 資料夾節點
 * @returns 所有子節點的路徑陣列（包含資料夾本身）
 */
export function getDescendantPaths<T extends BaseFileNode>(node: T): string[] {
  const paths: string[] = [node.path];

  if (node.type === 'directory' && node.children) {
    for (const child of node.children) {
      paths.push(...getDescendantPaths(child as T));
    }
  }

  return paths;
}

/**
 * 根據路徑找到節點
 *
 * @param nodes 檔案樹節點
 * @param path 要尋找的路徑
 * @returns 找到的節點或 null
 */
export function findNodeByPath<T extends BaseFileNode>(nodes: T[], path: string): T | null {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }

    if (node.children) {
      const found = findNodeByPath(node.children as T[], path);
      if (found) {
        return found;
      }
    }
  }

  return null;
}

/**
 * 檢測作業系統類型
 * @returns 是否為 Mac 系統
 */
export function isMacOS(): boolean {
  return /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
}

/**
 * 從事件中取得選擇修飾鍵類型
 * 
 * @param event 滑鼠事件
 * @returns 修飾鍵類型
 */
export function getSelectionModifierFromEvent(
  event: React.MouseEvent
): 'none' | 'ctrl' | 'shift' {
  const isMac = isMacOS();
  const isCtrlOrCmd = isMac ? event.metaKey : event.ctrlKey;
  const isShift = event.shiftKey;

  if (isCtrlOrCmd) {
    return 'ctrl';
  } else if (isShift) {
    return 'shift';
  }

  return 'none';
}
