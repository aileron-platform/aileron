import { useId } from 'react';
import { GitBranch } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

export function AutomationWorktreeSetting() {
  const { t } = useI18n();
  const summaryId = useId();
  const fieldLabelId = `${summaryId}-field-label`;
  const dedicatedLabelId = `${summaryId}-dedicated-label`;
  const dedicatedDescriptionId = `${summaryId}-dedicated-description`;

  return (
    <div className="space-y-2">
      <p id={fieldLabelId} className="text-sm font-medium leading-none">
        {t('automation.form.fields.worktree.label')}
      </p>
      <div
        role="group"
        aria-labelledby={`${fieldLabelId} ${dedicatedLabelId}`}
        aria-describedby={dedicatedDescriptionId}
        className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-4"
      >
        <span
          aria-hidden="true"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
        >
          <GitBranch className="h-4 w-4" />
        </span>
        <div className="min-w-0 space-y-1">
          <p id={dedicatedLabelId} className="text-sm font-medium text-foreground">
            {t('automation.form.fields.worktree.dedicated.label')}
          </p>
          <p
            id={dedicatedDescriptionId}
            className="text-xs font-normal leading-5 text-muted-foreground"
          >
            {t('automation.form.fields.worktree.dedicated.description')}
          </p>
        </div>
      </div>
    </div>
  );
}
