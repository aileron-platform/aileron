/**
 *
 */

import React from 'react';
import { AuthorizationDeniedState } from '@/features/auth/public';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { RuntimeSettingsPage } from './components/RuntimeSettingsPage';
import { FirewallSettingsPage } from './components/FirewallSettingsPage';
import { TerminalPage } from './components/TerminalPage';

export const ContainerManagementPage: React.FC = () => {
  const { workspace, permissions } = useWorkspace();

  switch (workspace.containerManagement.subView) {
    case 'runtime':
      if (!permissions.canUseSensitiveSettings) {
        return <AuthorizationDeniedState />;
      }
      return <RuntimeSettingsPage />;
    case 'firewall':
      if (!permissions.canReadFirewall) {
        return <AuthorizationDeniedState />;
      }
      return <FirewallSettingsPage />;
    case 'terminal':
      if (!permissions.canUseTerminal) {
        return <AuthorizationDeniedState />;
      }
      return <TerminalPage />;
    default:
      return <AuthorizationDeniedState />;
  }
};

export default ContainerManagementPage;
