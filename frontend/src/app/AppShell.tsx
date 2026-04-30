import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { AppProvider } from './providers/AppProvider';
import { AuthProvider } from '../features/auth/contexts/AuthContext';
import { DialogProvider } from './providers/DialogProvider';
import { NavigationProvider } from './providers/NavigationProvider';
import { I18nProvider } from './providers/I18nProvider';
import { AppRouter } from './AppRouter';
import { GlobalDialogSystem } from '@/app/components/dialogs/GlobalDialogSystem';
import { Toaster } from '../shared/components/ui/toaster';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
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
              <NavigationProvider>
                <DialogProvider>
                  <div className="h-screen flex flex-col bg-background">
                    <div className="flex-1 overflow-hidden">
                      <AppRouter />
                    </div>

                    <GlobalDialogSystem />

                    <Toaster />
                  </div>
                </DialogProvider>
              </NavigationProvider>
            </AppProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default AppShell;
