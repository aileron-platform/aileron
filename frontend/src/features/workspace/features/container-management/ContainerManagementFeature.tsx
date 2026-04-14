/**
 * ContainerManagementFeature - 容器管理功能
 *
 * 提供容器管理的主內容區域組件
 */

import React from 'react';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { RuntimeSettingsView } from './components/RuntimeSettingsView';
import { FirewallSettingsView } from './components/FirewallSettingsView';
import { TerminalView } from './components/TerminalView';

// 容器管理主內容組件（第三欄）
export const ContainerManagementMainContent: React.FC = () => {
  const { workspace } = useWorkspace();

  switch (workspace.containerManagement.subView) {
    case 'runtime':
      return <RuntimeSettingsView />;
    case 'firewall':
      return <FirewallSettingsView />;
    case 'terminal':
      return <TerminalView />;
    default:
      return <RuntimeSettingsView />;
  }
};

// 導出功能組件
export const ContainerManagementFeature = {
  MainContent: ContainerManagementMainContent,
};

// 默認導出一個 React 組件，供 lazy loading 使用
const ContainerManagementFeatureDefault: React.FC = () => {
  return <ContainerManagementMainContent />;
};

export default ContainerManagementFeatureDefault;
