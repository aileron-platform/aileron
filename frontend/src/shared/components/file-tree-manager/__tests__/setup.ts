/**
 * 測試設置文件
 * 
 * 提供測試所需的工具函數和模擬數據
 */

import { FileTreeNode, FileTreeApiConfig } from '../types';

/**
 * 創建模擬的檔案樹節點
 */
export function createMockNode(overrides: Partial<FileTreeNode> = {}): FileTreeNode {
  return {
    id: 'test-id',
    name: 'test.txt',
    path: '/test.txt',
    type: 'file',
    size: 1024,
    extension: 'txt',
    modifiedAt: '2024-01-01T00:00:00Z',
    createdAt: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * 創建模擬的檔案樹
 */
export function createMockTree(): FileTreeNode[] {
  return [
    {
      id: 'root',
      name: 'root',
      path: '/',
      type: 'directory',
      children: [
        {
          id: 'src',
          name: 'src',
          path: '/src',
          type: 'directory',
          children: [
            {
              id: 'index.ts',
              name: 'index.ts',
              path: '/src/index.ts',
              type: 'file',
              size: 2048,
              extension: 'ts',
            },
            {
              id: 'utils.ts',
              name: 'utils.ts',
              path: '/src/utils.ts',
              type: 'file',
              size: 1024,
              extension: 'ts',
            },
          ],
        },
        {
          id: 'README.md',
          name: 'README.md',
          path: '/README.md',
          type: 'file',
          size: 512,
          extension: 'md',
        },
      ],
    },
  ];
}

/**
 * 創建模擬的 API 配置
 */
export function createMockApiConfig(overrides: Partial<FileTreeApiConfig> = {}): FileTreeApiConfig {
  return {
    type: 'workspace',
    workspaceId: 'test-workspace-id',
    ...overrides,
  };
}

/**
 * 模擬 fetch API
 */
export function mockFetch(response: any, options: { ok?: boolean; status?: number } = {}) {
  const { ok = true, status = 200 } = options;
  
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(response),
      text: () => Promise.resolve(typeof response === 'string' ? response : JSON.stringify(response)),
    } as Response)
  );
}

/**
 * 清除所有模擬
 */
export function clearAllMocks() {
  vi.clearAllMocks();
}

/**
 * 等待異步操作完成
 */
export function waitFor(ms: number = 0): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 模擬檔案內容
 */
export const MOCK_FILE_CONTENT = `// Test file content
export function hello() {
  console.log('Hello, World!');
}
`;

/**
 * 模擬錯誤訊息
 */
export const MOCK_ERROR_MESSAGE = 'Test error message';

