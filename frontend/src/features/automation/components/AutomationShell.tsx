/**
 * AutomationShell - Scheduler center shell
 */

import React from 'react';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';

interface AutomationShellProps {
  children: React.ReactNode;
}

export const AutomationShell: React.FC<AutomationShellProps> = ({ children }) => {
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

export default AutomationShell;
