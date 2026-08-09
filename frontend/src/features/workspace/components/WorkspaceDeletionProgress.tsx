import React from 'react';
import { CheckCircle2, Circle, LoaderCircle, XCircle } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  WORKSPACE_DELETION_PHASES,
  type WorkspaceDeletionProgressSnapshot,
} from '../api/workspaceLifecycleApi';
import type { WorkspaceDeletionController } from '../hooks/useWorkspaceDeletion';
import { WorkspaceDeletionDialog } from './WorkspaceDeletionDialog';

interface WorkspaceDeletionActionProps extends WorkspaceDeletionController {
  workspaceName: string | null;
  canDelete: boolean;
  className?: string;
}

const phaseLabelKey = (phase: string) => {
  const normalized = phase.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
  const aliases: Record<string, string> = {
    queued: 'queued',
    cancelling_automations: 'cancellingAutomations',
    stopping_runtime: 'stoppingRuntime',
    deleting_resources: 'deletingResources',
    finalizing: 'finalizing',
  };
  return `workspace.workspaceSettings.reset.delete.progress.phases.${aliases[normalized] ?? normalized}`;
};

const phaseIndex = (phase: string | null): number => {
  if (!phase) {
    return -1;
  }
  const normalized = phase.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
  return WORKSPACE_DELETION_PHASES.indexOf(
    normalized as typeof WORKSPACE_DELETION_PHASES[number],
  );
};

type DisplayPhaseStatus = 'pending' | 'active' | 'completed' | 'failed';

const displayPhaseStatus = (
  progress: WorkspaceDeletionProgressSnapshot,
  index: number,
): DisplayPhaseStatus => {
  const currentIndex = phaseIndex(progress.phase);
  if (progress.status === 'failed' && index === currentIndex) {
    return 'failed';
  }
  if (currentIndex >= 0 && index < currentIndex) {
    return 'completed';
  }
  if (currentIndex === index && progress.status !== 'failed') {
    return 'active';
  }
  return 'pending';
};

const PHASE_ICONS = {
  pending: Circle,
  active: LoaderCircle,
  completed: CheckCircle2,
  failed: XCircle,
} as const;

export const WorkspaceDeletionProgress: React.FC<{
  progress: WorkspaceDeletionProgressSnapshot;
}> = ({ progress }) => {
  const { t } = useI18n();
  const isFailed = progress.status === 'failed';

  return (
    <section
      className="w-full space-y-3 rounded-md border border-border/60 bg-background/70 p-4"
      data-testid="workspace-deletion-progress"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-1">
          <h5 className="text-sm font-medium text-foreground">
            {t('workspace.workspaceSettings.reset.delete.progress.title')}
          </h5>
          <p className="text-xs text-muted-foreground">
            {t(isFailed
              ? 'workspace.workspaceSettings.reset.delete.progress.failedDescription'
              : 'workspace.workspaceSettings.reset.delete.progress.description')}
          </p>
        </div>
        <Badge
          variant="outline"
          className={isFailed
            ? 'border-destructive/20 bg-destructive/10 text-destructive'
            : 'border-amber-500/20 bg-amber-500/10 text-amber-700'}
        >
          {t(isFailed
            ? 'workspace.workspaceSettings.reset.delete.progress.status.failed'
            : progress.status === 'queued'
              ? 'workspace.workspaceSettings.reset.delete.progress.status.pending'
              : 'workspace.workspaceSettings.reset.delete.progress.status.active')}
        </Badge>
      </div>

      <ol className="grid gap-2 sm:grid-cols-2" aria-label={t(
        'workspace.workspaceSettings.reset.delete.progress.phasesLabel',
      )}>
        {WORKSPACE_DELETION_PHASES.map((phase, index) => {
          const status = displayPhaseStatus(progress, index);
          const Icon = PHASE_ICONS[status];
          return (
            <li
              key={phase}
              data-phase={phase}
              data-status={status}
              className="flex items-center gap-2 rounded border border-border/60 bg-card px-3 py-2 text-xs"
            >
              <Icon
                aria-hidden="true"
                className={`h-3.5 w-3.5 shrink-0 ${status === 'active' ? 'animate-spin' : ''}`}
              />
              <span>{t(phaseLabelKey(phase))}</span>
              <span className="sr-only">
                {t(`workspace.workspaceSettings.reset.delete.progress.status.${status}`)}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
};

export const WorkspaceDeletionAction: React.FC<WorkspaceDeletionActionProps> = ({
  workspaceName,
  canDelete,
  isDeleting,
  progress,
  requestDelete,
  className,
}) => {
  if (!canDelete && !isDeleting && !progress) {
    return null;
  }

  const effectiveProgress = progress ?? (isDeleting ? {
    jobId: 'pending',
    status: 'queued' as const,
    phase: null,
    errorCode: null,
  } : null);
  const isRetry = progress?.status === 'failed';

  return (
    <div className={`w-full space-y-3 ${className ?? ''}`} data-testid="workspace-deletion-action">
      {effectiveProgress ? <WorkspaceDeletionProgress progress={effectiveProgress} /> : null}
      <WorkspaceDeletionDialog
        workspaceName={workspaceName}
        canDelete={canDelete}
        isDeleting={isDeleting}
        isRetry={isRetry}
        onConfirm={requestDelete}
      />
    </div>
  );
};
