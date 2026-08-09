import React from 'react';
import { WorkspaceAutomationPage } from '@/features/workspace-automation/public';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../providers/WorkspaceProvider';

const WorkspaceAutomationRoute: React.FC = () => {
  const { permissions, workspaceRuntime } = useWorkspace();
  const { state } = useI18n();
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';

  return (
    <WorkspaceAutomationPage
      workspaceId={workspaceRuntime.workspaceId}
      runtimeBaseUrl={workspaceRuntime.runtimeBaseUrl}
      isRuntimeLoading={workspaceRuntime.isLoading}
      locale={locale}
      canUseAgentChat={permissions?.canUseChat ?? false}
    />
  );
};

export default WorkspaceAutomationRoute;
