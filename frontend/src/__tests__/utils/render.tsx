/**
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
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
  });

/**
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
 */
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
  initialRoute?: string;
}

/**
 */
export const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => {
  const { queryClient, initialRoute = '/', ...renderOptions } = options || {};

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

export * from '@testing-library/react';
export { customRender as render };
