/**
 * AutomationModule - Automation center root module
 */

import React from 'react';
import { AutomationProvider } from './providers/AutomationProvider';
import { AutomationShell } from './components/AutomationShell';
import { AutomationSidebar } from './components/AutomationSidebar';
import { AutomationDashboardPage } from './pages/AutomationDashboardPage';
import { AutomationJobCreateDialog } from './components/job-form/AutomationJobCreateDialog';
import { AutomationDashboardJobEditDialog } from './components/job-form/AutomationDashboardJobEditDialog';

interface AutomationModuleProps {
  navigationSlot: React.ReactNode;
}

export const AutomationModule: React.FC<AutomationModuleProps> = ({
  navigationSlot,
}) => {
  return (
    <AutomationProvider>
      <AutomationShell navigationSlot={navigationSlot}>
        <div className="flex h-full">
          <AutomationSidebar />
          <div className="flex-1 overflow-hidden">
            <AutomationDashboardPage />
          </div>
        </div>
        <AutomationJobCreateDialog />
        <AutomationDashboardJobEditDialog />
      </AutomationShell>
    </AutomationProvider>
  );
};
