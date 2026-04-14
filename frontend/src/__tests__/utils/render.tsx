/**
 * 自定義 Render 函數
 * 提供包含所有必要 Providers 的測試環境
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * 創建測試用 QueryClient
 */
export const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
    logger: {
      log: console.log,
      warn: console.warn,
      error: () => {}, // 禁用錯誤日誌
    },
  });

/**
 * 所有 Providers 的包裝器
 */
interface AllProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
}

export const AllProviders = ({ children, queryClient }: AllProvidersProps) => {
  const client = queryClient || createTestQueryClient();

  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

/**
 * 自定義 render 選項
 */
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
  initialRoute?: string;
}

/**
 * 自定義 render 函數
 */
export const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => {
  const { queryClient, initialRoute = '/', ...renderOptions } = options || {};

  // 設置初始路由
  if (initialRoute !== '/') {
    window.history.pushState({}, 'Test page', initialRoute);
  }

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AllProviders queryClient={queryClient}>{children}</AllProviders>
  );

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient: queryClient || createTestQueryClient(),
  };
};

/**
 * 不帶 Router 的 render (用於不需要路由的組件)
 */
export const renderWithoutRouter = (
  ui: ReactElement,
  options?: Omit<CustomRenderOptions, 'initialRoute'>
) => {
  const { queryClient, ...renderOptions } = options || {};
  const client = queryClient || createTestQueryClient();

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient: client,
  };
};

/**
 * 只有 QueryClient 的簡單 render (最小化 setup)
 */
export const renderWithQuery = (
  ui: ReactElement,
  queryClient?: QueryClient
) => {
  const client = queryClient || createTestQueryClient();

  return {
    ...render(ui, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    }),
    queryClient: client,
  };
};

// 重新導出所有 testing-library 的工具
export * from '@testing-library/react';
export { customRender as render };
