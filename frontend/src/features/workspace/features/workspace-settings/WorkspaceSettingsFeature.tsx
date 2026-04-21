/**
 * WorkspaceSettingsFeature - 工作區設定功能
 *
 * 提供工作區設定的主內容區域組件
 */

import React from 'react';
import { Settings } from 'lucide-react';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { WorkspaceAccessSettings } from './components/WorkspaceAccessSettings';
import { WorkspaceBasicSettings } from './components/WorkspaceBasicSettings';
import { WorkspaceKnowledgeBasesSettings } from './components/WorkspaceKnowledgeBasesSettings';
import { WorkspaceResetSettings } from './components/WorkspaceResetSettings';

// 工作區設定主內容組件（第三欄）
export const WorkspaceSettingsMainContent: React.FC = () => {
  const { workspace } = useWorkspace();
  const { t } = useI18n();

  switch (workspace.workspaceSettings.subView) {
    case 'basic':
      return <WorkspaceBasicSettings />;
    case 'access':
      return <WorkspaceAccessSettings />;
    case 'knowledge-bases':
      return <WorkspaceKnowledgeBasesSettings />;
    case 'reset':
      return <WorkspaceResetSettings />;
    default:
      return (
        <div className="h-full flex flex-col">
          <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {t('workspace.workspaceSettings.header.title')}
              </h2>
            </div>
          </div>
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <Settings className="h-16 w-16 mx-auto mb-4 opacity-20" />
              <p className="text-lg text-foreground">
                {t('workspace.workspaceSettings.empty.title')}
              </p>
              <p className="text-sm mt-2">
                {t('workspace.workspaceSettings.empty.description')}
              </p>
            </div>
          </div>
        </div>
      );
  }
};

// 導出功能組件
export const WorkspaceSettingsFeature = {
  MainContent: WorkspaceSettingsMainContent,
};

// 默認導出一個 React 組件，供 lazy loading 使用
const WorkspaceSettingsFeatureDefault: React.FC = () => {
  return <WorkspaceSettingsMainContent />;
};

export default WorkspaceSettingsFeatureDefault;
