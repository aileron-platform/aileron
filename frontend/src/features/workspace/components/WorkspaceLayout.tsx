/**
 * WorkspaceLayout - 工作區佈局組件
 * 
 * 提供工作區的基礎佈局結構，支援：
 * - 三欄模式
 * - 四欄模式
 * - 側邊欄管理
 */

import React, { ReactNode } from 'react';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { WorkspaceSidebar } from './WorkspaceSidebar';

interface WorkspaceLayoutProps {
  children: ReactNode;
}

export const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({ children }) => {
  const { state } = useWorkspace();

  return (
    <div className="flex h-full">
      {/* 主側邊欄 */}
      <WorkspaceSidebar />
      
      {/* 主內容區域 */}
      <div className="flex-1 flex overflow-hidden">
        {children}
      </div>
    </div>
  );
};

export default WorkspaceLayout;
