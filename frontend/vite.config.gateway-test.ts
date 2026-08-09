import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['config/workspaceGateway.vite.test.ts'],
    testTimeout: 10_000,
  },
});
