/**
 * GlobalStatusBar - 全域狀態列
 * 
 * 應用程式底部的狀態列
 */

import React from 'react';
import { useApp } from '../../../app/providers/AppProvider';

export const GlobalStatusBar: React.FC = () => {
  const { state } = useApp();

  return (
    <footer className="h-6 bg-muted border-t border-border flex items-center justify-between px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>Aileron v1.0</span>
        {state.system.isLoading && (
          <span>載入中...</span>
        )}
      </div>
      
      <div className="flex items-center gap-4">
        <span>錯誤: {state.system.errors.length}</span>
        <span>通知: {state.system.notifications.length}</span>
      </div>
    </footer>
  );
};

export default GlobalStatusBar;
