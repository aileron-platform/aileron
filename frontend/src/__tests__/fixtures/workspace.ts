/**
 * 工作區測試資料 Fixtures
 */

export interface MockWorkspace {
  id: string;
  name: string;
  description: string;
  status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error';
  userId: string;
  containerImage: string;
  createdAt: string;
  updatedAt: string;
  containerPort?: number;
  hostPort?: number;
  environmentVariables?: Record<string, string>;
}

/**
 * 創建 Mock 工作區
 */
export const createMockWorkspace = (
  overrides: Partial<MockWorkspace> = {}
): MockWorkspace => ({
  id: 'ws-1',
  name: 'Test Workspace',
  description: 'Test workspace description',
  status: 'running',
  userId: 'user-1',
  containerImage: 'node:latest',
  createdAt: '2024-01-01T00:00:00.000Z',
  updatedAt: '2024-01-01T00:00:00.000Z',
  containerPort: 3000,
  hostPort: 8080,
  ...overrides,
});

/**
 * 創建多個 Mock 工作區
 */
export const createMockWorkspaces = (count: number = 5): MockWorkspace[] =>
  Array.from({ length: count }, (_, i) =>
    createMockWorkspace({
      id: `ws-${i + 1}`,
      name: `Workspace ${i + 1}`,
      description: `Description for workspace ${i + 1}`,
    })
  );

/**
 * 創建停止狀態的工作區
 */
export const createStoppedWorkspace = (
  overrides: Partial<MockWorkspace> = {}
): MockWorkspace =>
  createMockWorkspace({
    status: 'stopped',
    ...overrides,
  });

/**
 * 創建錯誤狀態的工作區
 */
export const createErrorWorkspace = (
  overrides: Partial<MockWorkspace> = {}
): MockWorkspace =>
  createMockWorkspace({
    status: 'error',
    ...overrides,
  });
