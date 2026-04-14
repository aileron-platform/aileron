/**
 * WorkspaceAutomationFeature - 工作區自動化功能
 *
 * 提供工作區自動化任務的主內容區域組件
 */

import React from 'react';
import { WorkspaceAutomationView } from './components/WorkspaceAutomationView';

// 透過預設導出供懶載入使用
const WorkspaceAutomationMainContent: React.FC = () => {
  return <WorkspaceAutomationView />;
};

export default WorkspaceAutomationMainContent;
