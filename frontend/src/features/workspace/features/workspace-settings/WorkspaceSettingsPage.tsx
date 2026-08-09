/**
 *
 */

import React from 'react';
import { Settings } from 'lucide-react';
import { AuthorizationDeniedState } from '@/features/auth/public';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { WorkspaceAccessSettings } from './components/WorkspaceAccessSettings';
import { WorkspaceBasicSettings } from './components/WorkspaceBasicSettings';
import { WorkspaceKnowledgeBasesSettings } from './components/WorkspaceKnowledgeBasesSettings';
import { WorkspaceResetSettings } from './components/WorkspaceResetSettings';

export const WorkspaceSettingsPage: React.FC = () => {
  const { workspace, permissions } = useWorkspace();
  const { t } = useI18n();

  switch (workspace.workspaceSettings.subView) {
    case 'basic':
      if (!permissions.canRead) {
        return <AuthorizationDeniedState />;
      }
      return <WorkspaceBasicSettings />;
    case 'access':
      if (!permissions.canRead) {
        return <AuthorizationDeniedState />;
      }
      return <WorkspaceAccessSettings />;
    case 'knowledge-bases':
      if (!permissions.canRead) {
        return <AuthorizationDeniedState />;
      }
      return <WorkspaceKnowledgeBasesSettings />;
    case 'reset':
      if (!permissions.canRunLifecycle) {
        return <AuthorizationDeniedState />;
      }
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

export default WorkspaceSettingsPage;
