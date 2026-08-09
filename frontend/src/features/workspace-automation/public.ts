export { WorkspaceAutomationPage } from './pages/WorkspaceAutomationPage';

export const loadAutomationModule = () =>
  import('./AutomationModule').then(({ AutomationModule }) => ({
    default: AutomationModule,
  }));
