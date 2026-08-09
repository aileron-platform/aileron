import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { AppProvider } from './providers/AppProvider';
import { AuthProvider } from '@/features/auth/public';
import { DialogProvider } from './providers/DialogProvider';
import { WorkspaceSelectionProvider } from '@/features/workspace/public';
import { I18nProvider } from '@/shared/contexts/I18nContext';
import { AppRouter } from './AppRouter';
import { GlobalDialogSystem } from '@/app/components/dialogs/GlobalDialogSystem';
import { Toaster } from '../shared/components/ui/toaster';
import { ApiError } from '@/shared/api/apiClient';

export const shouldRetryQuery = (failureCount: number, error: Error): boolean => {
  if (error instanceof ApiError) {
    const isStableClientError =
      error.status >= 400
      && error.status < 500
      && error.status !== 408
      && error.status !== 429;
    if (isStableClientError) {
      return false;
    }
  }
  return failureCount < 1;
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetryQuery,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

export const AppShell: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
      >
        <I18nProvider>
          <AuthProvider>
            <AppProvider>
              <WorkspaceSelectionProvider>
                <DialogProvider>
                  <div className="h-screen flex flex-col bg-background">
                    <div className="flex-1 overflow-hidden">
                      <AppRouter />
                    </div>

                    <GlobalDialogSystem />

                    <Toaster />
                  </div>
                </DialogProvider>
              </WorkspaceSelectionProvider>
            </AppProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default AppShell;
