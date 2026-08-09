import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { apiClient } from '@/shared/api/apiClient';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';
import { useWorkspaceWizard } from './hooks/useWorkspaceWizard';
import BasicInfoStep from './components/steps/BasicInfoStep';
import RuntimeConfigStep from './components/steps/RuntimeConfigStep';
import WorkspaceCreationStep from './components/steps/WorkspaceCreationStep';
import type { BasicInfoForm, RuntimeConfigForm } from './model/workspaceWizardTypes';

const logger = createLogger('WorkspaceWizardPage');

interface WorkspaceWizardPageProps {
  navigationSlot: React.ReactNode;
  userId?: string;
}

const WorkspaceWizardPage: React.FC<WorkspaceWizardPageProps> = ({
  navigationSlot,
  userId,
}) => {
  const navigate = useNavigate();
  const { t } = useI18n();
  const { toast } = useToast();
  const hasLoadedEnvVarsRef = useRef(false);

  const {
    state,
    setBasicInfo,
    setRuntimeConfig,
    submitBasicInfo,
    submitRuntimeConfig,
    retryWorkspaceCreation,
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
      navigate(ROUTES.workspace.home(workspaceId));
    },
  });

  useEffect(() => () => reset(), [reset]);

  useEffect(() => {
    if (!userId || hasLoadedEnvVarsRef.current) return;
    hasLoadedEnvVarsRef.current = true;

    const loadClaudeEnvVars = async () => {
      try {
        const response = await apiClient.get<{ data: { claudeCode?: { environmentVariables?: Array<{ key: string; value: string }> } } }>(`/users/${userId}/settings`);
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
      } catch (error) {
        logger.debug('Claude environment variables preload failed', {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    };

    void loadClaudeEnvVars();
  }, [userId, setRuntimeConfig]);

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
    navigate(ROUTES.workspace.root);
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
            onRetry={retryWorkspaceCreation}
            onComplete={completeWizard}
            t={t}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen w-full flex-col bg-background">
      {navigationSlot}
<main className="flex-1 overflow-auto px-10 sm:px-24 lg:px-40 xl:px-56 2xl:px-72 py-10">
  <div className="w-full space-y-8">
    {renderStep()}
  </div>
</main>
    </div>
  );
};

export default WorkspaceWizardPage;
