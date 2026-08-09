import { GitBranch, Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  RepositorySetupCapability,
  RepositorySetupMutationKind,
  RepositorySetupOperationResult,
  RepositorySetupRemoteEffects,
  RepositorySetupTarget,
} from '@/shared/version-control';
import { useRepositorySetupWorkflow } from '@/shared/version-control/repositorySetupWorkflow';
import { VersionControlRepositorySetupDialog } from './VersionControlRepositorySetupDialog';

export interface VersionControlRepositorySetupProps {
  target: RepositorySetupTarget;
  capability: RepositorySetupCapability;
  remoteEffects: RepositorySetupRemoteEffects;
  onSetupComplete?: (kind: RepositorySetupMutationKind) => void | Promise<void>;
}

export const VersionControlRepositorySetup = ({
  target,
  capability,
  remoteEffects,
  onSetupComplete,
}: VersionControlRepositorySetupProps) => {
  const { t } = useI18n();
  const workflow = useRepositorySetupWorkflow({
    target,
    capability,
    remoteEffects,
  });
  const { state, events } = workflow;
  const isInitializing = state.phase === 'initializing';

  const completeSetup = async (result: RepositorySetupOperationResult) => {
    if (result.status === 'completed' && result.kind !== 'discovery') {
      await onSetupComplete?.(result.kind);
    }
  };

  const presentationWorkflow = {
    state,
    events: {
      ...events,
      initialize: async () => {
        const result = await events.initialize();
        await completeSetup(result);
        return result;
      },
      clone: async () => {
        const result = await events.clone();
        await completeSetup(result);
        return result;
      },
    },
  } satisfies typeof workflow;

  return (
    <>
      <EmptyState
        icon={GitBranch}
        title={t('shared.versionControl.repositorySetup.title')}
        description={t('shared.versionControl.repositorySetup.description')}
        action={state.canMutate ? (
          <div className="space-y-3">
            <div className="flex items-center justify-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                data-variant="outline"
                disabled={!state.canOpenInitialize}
                aria-busy={isInitializing}
                onClick={events.openInitialize}
              >
                {isInitializing && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {t(
                  isInitializing
                    ? 'shared.versionControl.repositorySetup.actions.initializing'
                    : 'shared.versionControl.repositorySetup.actions.init',
                )}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={!state.canOpenClone}
                onClick={events.openClone}
              >
                {t('shared.versionControl.repositorySetup.actions.clone')}
              </Button>
            </div>
          </div>
        ) : undefined}
      />
      <VersionControlRepositorySetupDialog workflow={presentationWorkflow} />
    </>
  );
};
