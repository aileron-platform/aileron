/**
 * AppShell - 應用程式外殼
 *
 * 負責整個應用程式的基礎佈局和全域元件管理
 * 包含導航、對話框系統、狀態列等全域元件
 */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { AppProvider } from './providers/AppProvider';
import { AuthProvider } from '../features/auth/contexts/AuthContext';
import { DialogProvider } from './providers/DialogProvider';
import { NavigationProvider } from './providers/NavigationProvider';
import { I18nProvider } from './providers/I18nProvider';
import { AppRouter } from './AppRouter';
import { GlobalDialogSystem } from '../shared/components/dialogs/GlobalDialogSystem';
import { Toaster } from '../shared/components/ui/toaster';
import { MonacoInitializer } from '../shared/components/monaco/MonacoInitializer';

// 創建 QueryClient 實例
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 分鐘
    },
  },
});

/**
 * AppShell 組件
 *
 * 應用程式的最外層容器，負責：
 * 1. 提供全域狀態管理 (Provider 層級)
 * 2. 渲染全域 UI 元件 (導航、對話框、狀態列)
 * 3. 管理應用程式路由
 */
export const AppShell: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
      >
        <I18nProvider>
          <MonacoInitializer />
          <AuthProvider>
            <AppProvider>
              <NavigationProvider>
                <DialogProvider>
                  <div className="h-screen flex flex-col bg-background">
                    {/* 主要內容區域 */}
                    <div className="flex-1 overflow-hidden">
                      <AppRouter />
                    </div>

                    {/* 全域對話框系統 */}
                    <GlobalDialogSystem />

                    {/* Toast 通知系統 */}
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
