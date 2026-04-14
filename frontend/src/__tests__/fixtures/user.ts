/**
 * 使用者測試資料 Fixtures
 */

export interface MockUser {
  id: string;
  email: string;
  username: string;
  createdAt: string;
  updatedAt: string;
  avatar?: string;
}

/**
 * 創建 Mock 使用者
 */
export const createMockUser = (overrides: Partial<MockUser> = {}): MockUser => ({
  id: 'user-1',
  email: 'test@example.com',
  username: 'testuser',
  createdAt: '2024-01-01T00:00:00.000Z',
  updatedAt: '2024-01-01T00:00:00.000Z',
  ...overrides,
});

/**
 * 創建 Admin 使用者
 */
export const createMockAdmin = (overrides: Partial<MockUser> = {}): MockUser =>
  createMockUser({
    id: 'admin-1',
    email: 'admin@example.com',
    username: 'admin',
    ...overrides,
  });

/**
 * 創建多個 Mock 使用者
 */
export const createMockUsers = (count: number = 5): MockUser[] =>
  Array.from({ length: count }, (_, i) =>
    createMockUser({
      id: `user-${i + 1}`,
      email: `user${i + 1}@example.com`,
      username: `user${i + 1}`,
    })
  );
