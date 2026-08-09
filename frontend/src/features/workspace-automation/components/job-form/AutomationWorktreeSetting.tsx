import { GitBranch } from 'lucide-react';
import { Label } from '@/shared/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import { useI18n } from '@/shared/hooks/useI18n';

export function AutomationWorktreeSetting() {
  const { t } = useI18n();

  return (
    <div className="space-y-2">
      <Label>{t('automation.form.fields.worktree.label')}</Label>
      <RadioGroup value="dedicated" aria-label={t('automation.form.fields.worktree.label')}>
        <Label
          htmlFor="automation-worktree-dedicated"
          className="flex cursor-default items-start gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4"
        >
          <RadioGroupItem id="automation-worktree-dedicated" value="dedicated" className="mt-0.5" />
          <GitBranch className="mt-0.5 h-4 w-4 flex-none text-primary" />
          <span className="space-y-1">
            <span className="block text-sm font-medium text-foreground">
              {t('automation.form.fields.worktree.dedicated.label')}
            </span>
            <span className="block text-xs font-normal leading-5 text-muted-foreground">
              {t('automation.form.fields.worktree.dedicated.description')}
            </span>
          </span>
        </Label>
      </RadioGroup>
    </div>
  );
}
