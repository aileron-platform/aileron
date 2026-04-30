import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useApp } from '@/app/providers/AppProvider';
import { apiClient } from '@/shared/api/apiClient';
import { useWorkspaceWizard } from './hooks/useWorkspaceWizard';
import { BasicInfoStep, RuntimeConfigStep, WorkspaceCreationStep, SettingsSyncStep } from './components';
import type { BasicInfoForm, RuntimeConfigForm } from './types';

const WorkspaceWizardPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useI18n();
  const { toast } = useToast();
  const { state: appState } = useApp();
  const user = appState.user;
  const hasLoadedEnvVarsRef = useRef(false);

  const {
    state,
    setBasicInfo,
    setRuntimeConfig,
    kubernetesNamespaceOptions,
    submitBasicInfo,
    submitRuntimeConfig,
    runtimeHelpers,
    goToStep,
    reset,
    completeWizard,
  } = useWorkspaceWizard({
    onCompleted: (workspaceId) => {
      toast({
        title: t('workspace.wizard.notifications.completedTitle'),
        description: t('workspace.wizard.notifications.completedDescription'),
      });
      navigate('/workspaces');
    },
  });

  useEffect(() => () => reset(), [reset]);

  // 載入系統設定中的 Claude Code 環境變數，預填到 Runtime 設定
  useEffect(() => {
    if (!user?.id || hasLoadedEnvVarsRef.current) return;
    hasLoadedEnvVarsRef.current = true;

    const loadClaudeEnvVars = async () => {
      try {
        const response = await apiClient.get<{ data: { claudeCode?: { environmentVariables?: Array<{ key: string; value: string }> } } }>(`/users/${user.id}/settings`);
        const envVars = response.data?.claudeCode?.environmentVariables;
        if (envVars && envVars.length > 0) {
          setRuntimeConfig(prev => ({
            ...prev,
            envVars: [
              ...prev.envVars,
              ...envVars.map(ev => ({ id: crypto.randomUUID(), key: ev.key, value: ev.value })),
            ],
          }));
        }
      } catch {
        // 靜默忽略，不影響 wizard 流程
      }
    };

    void loadClaudeEnvVars();
  }, [user?.id, setRuntimeConfig]);

  useEffect(() => {
    if (!state.error || state.error.startsWith('validation')) {
      return;
    }
    toast({
      title: t('workspace.wizard.notifications.errorTitle'),
      description: t(`workspace.wizard.${state.error}`),
      variant: 'destructive',
    });
  }, [state.error, t, toast]);

  const handleCancel = () => {
    reset();
    navigate('/workspaces');
  };

  const handleBasicInfoChange = (next: BasicInfoForm) => setBasicInfo(next);
  const handleRuntimeConfigChange = (next: RuntimeConfigForm) => setRuntimeConfig(next);

  const renderStep = () => {
    switch (state.step) {
      case 'basicInfo':
        return (
          <BasicInfoStep
            data={state.basicInfo}
            onChange={handleBasicInfoChange}
            onCancel={handleCancel}
            onSubmit={submitBasicInfo}
            isSubmitting={state.isSubmitting}
            t={t}
          />
        );
      case 'runtimeConfig':
        return (
          <RuntimeConfigStep
            data={state.runtimeConfig}
            onChange={handleRuntimeConfigChange}
            kubernetesNamespaceOptions={kubernetesNamespaceOptions}
            helpers={runtimeHelpers}
            onPrevious={() => goToStep('basicInfo')}
            onSubmit={submitRuntimeConfig}
            isSubmitting={state.isSubmitting}
            t={t}
          />
        );
      case 'workspaceCreation':
        return (
          <WorkspaceCreationStep
            workspaceId={state.createdWorkspaceId}
            isPolling={state.isPolling}
            errorKey={state.error}
            onPrevious={() => goToStep('runtimeConfig')}
            onRetry={submitRuntimeConfig}
            onContinue={() => goToStep('settingsSync')}
            t={t}
          />
        );
      case 'settingsSync':
        return state.createdWorkspaceId ? (
          <SettingsSyncStep
            workspaceId={state.createdWorkspaceId}
            onPrevious={() => goToStep('workspaceCreation')}
            onComplete={() => {
              completeWizard();
            }}
            isSubmitting={state.isSubmitting}
            t={t}
          />
        ) : null;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen w-full flex-col bg-background">
      <GlobalNavigation />
<main className="flex-1 overflow-auto px-10 sm:px-24 lg:px-40 xl:px-56 2xl:px-72 py-10">
  <div className="w-full space-y-8">
    {renderStep()}
  </div>
</main>
    </div>
  );
};

export default WorkspaceWizardPage;
