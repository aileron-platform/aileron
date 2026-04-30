/**
 * 
 */

import { FileTreeNode, FileTreeApiConfig } from '../types';

/**
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
 */
export function createMockApiConfig(overrides: Partial<FileTreeApiConfig> = {}): FileTreeApiConfig {
  return {
    type: 'workspace',
    workspaceId: 'test-workspace-id',
    ...overrides,
  };
}

/**
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
 */
export function clearAllMocks() {
  vi.clearAllMocks();
}

/**
 */
export function waitFor(ms: number = 0): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 */
export const MOCK_FILE_CONTENT = `// Test file content
export function hello() {
  console.log('Hello, World!');
}
`;

/**
 */
export const MOCK_ERROR_MESSAGE = 'Test error message';

