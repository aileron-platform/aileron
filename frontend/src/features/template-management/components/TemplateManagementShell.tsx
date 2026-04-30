/**
 * TemplateManagementShell - 範本管理模組外殼
 *
 * 統一提供模組外層佈局與全域導覽列
 */

import React from 'react';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';

export interface TemplateManagementShellProps {
  children: React.ReactNode;
}

export const TemplateManagementShell: React.FC<TemplateManagementShellProps> = ({ children }) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      <GlobalNavigation />
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-hidden bg-muted/20">
          {children}
        </div>
      </div>
    </div>
  );
};

export default TemplateManagementShell;
