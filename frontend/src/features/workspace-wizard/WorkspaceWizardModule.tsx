import React, { useEffect } from 'react';
import { Dialog, DialogContent } from '@/shared/components/ui/dialog';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspaceWizard } from './hooks/useWorkspaceWizard';
import { BasicInfoStep } from './components';
import { RuntimeConfigStep } from './components';
import { WorkspaceCreationStep } from './components';
import { SettingsSyncStep } from './components';
import { BasicInfoForm, RuntimeConfigForm } from './types';

interface WorkspaceWizardModuleProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  onCompleted?: (workspaceId: string) => void;
}

export const WorkspaceWizardModule: React.FC<WorkspaceWizardModuleProps> = ({
  open,
  onOpenChange,
  t,
  onCompleted,
}) => {
  const { toast } = useToast();
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
      onCompleted?.(workspaceId);
      toast({
        title: t('workspace.wizard.notifications.completedTitle'),
        description: t('workspace.wizard.notifications.completedDescription'),
      });
      onOpenChange(false);
    },
  });

  useEffect(() => {
    if (!open) {
      reset();
    }
  }, [open, reset]);

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

  const handleDialogChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      reset();
    }
    onOpenChange(nextOpen);
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
            onCancel={() => handleDialogChange(false)}
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
            onComplete={completeWizard}
            isSubmitting={state.isSubmitting}
            t={t}
          />
        ) : null;
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogChange}>
      <DialogContent className="max-h-[90vh] w-full max-w-5xl overflow-y-auto border-none p-6 sm:p-8">
        {renderStep()}
      </DialogContent>
    </Dialog>
  );
};

export default WorkspaceWizardModule;
