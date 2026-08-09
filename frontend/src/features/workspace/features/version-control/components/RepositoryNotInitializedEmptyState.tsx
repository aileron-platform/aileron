import { VersionControlRepositorySetup } from '@/shared/components/version-control';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type { RepositorySetupMutationKind } from '@/shared/version-control';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import { useWorkspace } from '../../../providers/WorkspaceProvider';

export const RepositoryNotInitializedEmptyState = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, permissions } = useWorkspace();
  const versionControl = useWorkspaceVersionControlSession({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
  });
  const initializeRepositoryMutation =
    versionControl.remote.useInitializeRepositoryMutation();
  const cloneRepositoryMutation =
    versionControl.remote.useCloneRepositoryMutation();
  const remoteBranchesMutation =
    versionControl.remote.useRemoteBranchesMutation();
  const repositoryQuery =
    versionControl.remote.useRepositoryQuery(permissions.canWrite);

  const handleSetupComplete = (kind: RepositorySetupMutationKind) => {
    toast({
      title: t(kind === 'initialize'
        ? 'workspace.versionControl.toasts.initializeSuccess.title'
        : 'workspace.versionControl.toasts.cloneSuccess.title'),
      variant: 'success',
    });
  };

  return (
    <VersionControlRepositorySetup
      target={{
        scopeKey: workspaceRuntime.workspaceId
          ? `workspace:${workspaceRuntime.workspaceId}`
          : '',
        repository: repositoryQuery.data ?? null,
      }}
      capability={{ canMutate: permissions.canWrite }}
      remoteEffects={{
        initialize: defaultBranch => initializeRepositoryMutation.mutateAsync({ defaultBranch }),
        clone: (remoteUrl, branch) => cloneRepositoryMutation.mutateAsync({
          remoteUrl,
          ...(branch ? { branch } : {}),
        }),
        discoverBranches: remoteBranchesMutation.mutateAsync,
      }}
      onSetupComplete={handleSetupComplete}
    />
  );
};
