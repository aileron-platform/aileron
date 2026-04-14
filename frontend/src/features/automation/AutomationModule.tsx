/**
 * AutomationModule - Scheduler center root module
 */

import React from 'react';
import { AutomationProvider } from './providers/AutomationProvider';
import { AutomationShell } from './components/AutomationShell';
import { AutomationSidebar } from './components/AutomationSidebar';
import { AutomationDashboard } from './views/AutomationDashboard';
import { JobCreateDialog } from './components/JobCreateDialog';
import { JobEditDialog } from './components/JobEditDialog';

export const AutomationModule: React.FC = () => {
  return (
    <AutomationProvider>
      <AutomationShell>
        <div className="flex h-full">
          <AutomationSidebar />
          <div className="flex-1 overflow-hidden">
            <AutomationDashboard />
          </div>
        </div>
        <JobCreateDialog />
        <JobEditDialog />
      </AutomationShell>
    </AutomationProvider>
  );
};

export default AutomationModule;
