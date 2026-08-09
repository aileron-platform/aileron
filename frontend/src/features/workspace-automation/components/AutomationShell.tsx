/**
 * AutomationShell - Automation center shell
 */

import React from 'react';

interface AutomationShellProps {
  children: React.ReactNode;
  navigationSlot: React.ReactNode;
}

export const AutomationShell: React.FC<AutomationShellProps> = ({
  children,
  navigationSlot,
}) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      {navigationSlot}
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-hidden bg-muted/20">
          {children}
        </div>
      </div>
    </div>
  );
};
