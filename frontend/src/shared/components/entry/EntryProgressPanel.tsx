import React from 'react';
import {
  AlertCircle,
  Check,
  Circle,
  Clipboard,
  HelpCircle,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  UserRound,
  Wrench,
  X,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  WorkspaceEntryActionId,
  WorkspaceEntryProjection,
  PlatformIdentityEntryProjection,
  WorkspaceEntryStageStatus,
} from './workspaceEntryTypes';

type EntryProjection = WorkspaceEntryProjection | PlatformIdentityEntryProjection;

interface EntryProgressPanelProps {
  projection: EntryProjection;
  onAction: (action: WorkspaceEntryActionId) => void;
  disableMutationActions?: boolean;
  auxiliaryActions?: React.ReactNode;
}

interface StagePresentation {
  Icon: typeof Circle;
  iconClassName: string;
  nodeClassName: string;
  labelClassName: string;
  statusClassName: string;
}

const STAGE_PRESENTATION: Record<WorkspaceEntryStageStatus, StagePresentation> = {
  pending: {
    Icon: Circle,
    iconClassName: 'h-2 w-2 fill-current',
    nodeClassName: 'border-dashed border-border bg-background text-muted-foreground/60',
    labelClassName: 'text-muted-foreground',
    statusClassName: 'text-muted-foreground/80',
  },
  active: {
    Icon: LoaderCircle,
    iconClassName: 'h-4 w-4 animate-spin',
    nodeClassName: 'border-primary bg-primary/10 text-primary ring-4 ring-primary/15',
    labelClassName: 'text-foreground',
    statusClassName: 'text-primary',
  },
  complete: {
    Icon: Check,
    iconClassName: 'h-4 w-4',
    nodeClassName: 'border-primary bg-primary text-primary-foreground',
    labelClassName: 'text-foreground',
    statusClassName: 'text-muted-foreground',
  },
  action_required: {
    Icon: AlertCircle,
    iconClassName: 'h-4 w-4',
    nodeClassName: 'border-warning bg-warning/10 text-warning ring-4 ring-warning/15',
    labelClassName: 'text-foreground',
    statusClassName: 'text-warning',
  },
  uncertain: {
    Icon: HelpCircle,
    iconClassName: 'h-4 w-4',
    nodeClassName: 'border-warning bg-warning/10 text-warning ring-4 ring-warning/15',
    labelClassName: 'text-foreground',
    statusClassName: 'text-warning',
  },
  failed: {
    Icon: X,
    iconClassName: 'h-4 w-4',
    nodeClassName: 'border-destructive bg-destructive/10 text-destructive ring-4 ring-destructive/15',
    labelClassName: 'text-foreground',
    statusClassName: 'text-destructive',
  },
};

// The rail is solid up to the frontier the entry sequence reached, dashed beyond it.
const railClassName = (isTraversed: boolean) => (
  isTraversed ? 'w-px bg-primary' : 'w-0 border-l border-dashed border-border'
);

const ACTION_ICONS: Record<WorkspaceEntryActionId, typeof RefreshCw> = {
  login: UserRound,
  create: UserRound,
  refresh: RefreshCw,
  start: RefreshCw,
  retry: RotateCcw,
  rebuild: Wrench,
  return: ShieldAlert,
};

export const EntryProgressPanel: React.FC<EntryProgressPanelProps> = ({
  projection,
  onAction,
  disableMutationActions = false,
  auxiliaryActions,
}) => {
  const { t } = useI18n();
  const [isReasonCodeCopied, setIsReasonCodeCopied] = React.useState(false);

  const copyReasonCode = async () => {
    if (!projection.reasonCode || !navigator.clipboard?.writeText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(projection.reasonCode);
      setIsReasonCodeCopied(true);
    } catch {
      setIsReasonCodeCopied(false);
    }
  };

  return (
    <section
      className="w-full max-w-md rounded-2xl border border-border bg-card p-7 text-card-foreground shadow-xl shadow-foreground/[0.06] duration-500 animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none"
      data-testid="entry-progress-panel"
      aria-live="polite"
    >
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {t(projection.titleKey)}
        </h1>
        <p className="min-h-6 text-sm leading-6 text-muted-foreground">
          {t(projection.descriptionKey)}
        </p>
      </header>

      <ol aria-label={t('common.entry.stages.label')} className="mt-7">
        {projection.stages.map((entryStage, stageIndex) => {
          const presentation = STAGE_PRESENTATION[entryStage.status];
          const { Icon: StatusIcon } = presentation;
          const isActive = entryStage.id === projection.activeStage;
          const isLastStage = stageIndex === projection.stages.length - 1;
          return (
            <li
              key={entryStage.id}
              aria-current={isActive ? 'step' : undefined}
              aria-label={t(`common.entry.stages.${entryStage.id}`)}
              aria-describedby={`entry-stage-status-${entryStage.id}`}
              data-status={entryStage.status}
              className="relative flex gap-3.5 pb-6 last:pb-0"
            >
              {!isLastStage ? (
                <span
                  aria-hidden="true"
                  className={`absolute bottom-0 left-4 top-[2.375rem] -translate-x-1/2 ${railClassName(entryStage.status === 'complete')}`}
                />
              ) : null}
              <span
                aria-hidden="true"
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border transition-colors ${presentation.nodeClassName}`}
              >
                <StatusIcon
                  className={`shrink-0 motion-reduce:animate-none ${presentation.iconClassName}`}
                />
              </span>
              <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 pt-1.5">
                <span className={`min-w-0 text-sm font-medium ${presentation.labelClassName}`}>
                  {t(`common.entry.stages.${entryStage.id}`)}
                </span>
                <span
                  id={`entry-stage-status-${entryStage.id}`}
                  className={`shrink-0 text-xs ${presentation.statusClassName}`}
                >
                  {t(`common.entry.status.${entryStage.status}`)}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      {projection.reasonCode ? (
        <div className="mt-6 flex items-center gap-3 rounded-xl border border-dashed border-border bg-muted/40 px-3.5 py-2.5">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {t('common.entry.reasonCode')}
            </p>
            <code className="mt-0.5 block truncate font-mono text-xs text-foreground">
              {projection.reasonCode}
            </code>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
            aria-label={t(
              isReasonCodeCopied
                ? 'common.entry.reasonCodeCopied'
                : 'common.entry.copyReasonCode',
            )}
            onClick={() => void copyReasonCode()}
          >
            {isReasonCodeCopied ? (
              <Check className="h-4 w-4 text-primary" aria-hidden="true" />
            ) : (
              <Clipboard className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        </div>
      ) : null}

      {projection.actions.length > 0 || auxiliaryActions ? (
        <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-border pt-6">
          {projection.actions.map((entryAction) => {
            const ActionIcon = ACTION_ICONS[entryAction.id];
            const variant = entryAction.emphasis === 'danger-secondary'
              ? 'destructive'
              : entryAction.emphasis === 'secondary'
                ? 'outline'
                : 'default';
            return (
              <Button
                key={entryAction.id}
                type="button"
                variant={variant}
                disabled={disableMutationActions && entryAction.id !== 'return'}
                onClick={() => onAction(entryAction.id)}
              >
                <ActionIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                {t(`common.entry.actions.${entryAction.id}`)}
              </Button>
            );
          })}
          {auxiliaryActions}
        </div>
      ) : null}
    </section>
  );
};
