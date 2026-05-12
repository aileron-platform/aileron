import React, { useState } from 'react';
import { Check, ChevronRight, Folder, GitBranch, Info, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';
import { apiClient } from '@/shared/api/apiClient';
import { BasicInfoForm, CliType } from '../../types';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('BasicInfoStep');

interface BasicInfoStepProps {
  data: BasicInfoForm;
  onChange: (next: BasicInfoForm) => void;
  onCancel: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const cliTypeOptions: Array<{
  value: CliType;
  labelKey: string;
  descriptionKey: string;
  iconSrc: string;
}> = [
  {
    value: 'claude-code',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.cliType.options.claudeCode',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.claudeCode',
    iconSrc: '/marketplace/providers/claude-code.png',
  },
  {
    value: 'codex',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.cliType.options.codex',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.codex',
    iconSrc: '/marketplace/providers/codex.png',
  },
  {
    value: 'gemini',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.cliType.options.gemini',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.gemini',
    iconSrc: '/marketplace/providers/gemini.svg',
  },
];

export const BasicInfoStep: React.FC<BasicInfoStepProps> = ({
  data,
  onChange,
  onCancel,
  onSubmit,
  isSubmitting,
  t,
}) => {
  const [branches, setBranches] = useState<string[]>([]);
  const [isLoadingBranches, setIsLoadingBranches] = useState(false);
  const [branchError, setBranchError] = useState<string | null>(null);
  const [hasFetchedBranches, setHasFetchedBranches] = useState(false);

  const updateField = (field: keyof BasicInfoForm, value: string) => {
    // Reset branch state when the Git URL changes.
    if (field === 'gitUrl') {
      setBranches([]);
      setHasFetchedBranches(false);
      setBranchError(null);
      onChange({ ...data, [field]: value, branch: '' });
    } else {
      onChange({ ...data, [field]: value });
    }
  };

  // Require core fields, and require a fetched branch when a Git URL is provided.
  const hasGitUrl = data.gitUrl.trim().length > 0;
  const isValid =
    data.name.trim().length > 0 &&
    data.description.trim().length > 0 &&
    !!data.cliType &&
    (!hasGitUrl || (hasFetchedBranches && branches.length > 0 && data.branch.trim().length > 0));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSubmitting && isValid) {
      onSubmit();
    }
  };

  const fetchBranches = async () => {
    if (!data.gitUrl.trim()) {
      setBranchError(t('workspace.wizard.steps.basicInfo.fields.gitUrl.errors.empty'));
      return;
    }

    setIsLoadingBranches(true);
    setBranchError(null);
    setBranches([]);
    setHasFetchedBranches(false);

    try {
      const result = await apiClient.get<{ branches: string[]; total: number }>(
        `/workspaces/temp/setup/git-branches?git_url=${encodeURIComponent(data.gitUrl)}`
      );

      const fetchedBranches = result.branches || [];
      setBranches(fetchedBranches);
      setHasFetchedBranches(true);

      // Select the first fetched branch when no branch has been selected yet.
      if (!data.branch && fetchedBranches.length > 0) {
        updateField('branch', fetchedBranches[0]);
      }
    } catch (error) {
      logger.error('Failed to fetch branches', { error });
      const errorMessage = error instanceof Error
        ? error.message
        : t('workspace.wizard.steps.basicInfo.fields.gitUrl.errors.fetchFailed');
      setBranchError(errorMessage);
      setHasFetchedBranches(false);
    } finally {
      setIsLoadingBranches(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <div className="flex items-center justify-center gap-2 text-primary">
          <Folder className="h-8 w-8" />
          <h1 className="text-2xl font-semibold text-foreground">
            {t('workspace.wizard.steps.basicInfo.title')}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('workspace.wizard.steps.basicInfo.subtitle', { current: 1, total: 4 })}
        </p>
      </div>

      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: '25%' }} />
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <GitBranch className="h-5 w-5" />
            {t('workspace.wizard.steps.basicInfo.cardTitle')}
          </CardTitle>
          <CardDescription>{t('workspace.wizard.steps.basicInfo.cardDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="wizard-basic-name" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.name.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <Input
                id="wizard-basic-name"
                value={data.name}
                onChange={(event) => updateField('name', event.target.value)}
                placeholder={t('workspace.wizard.steps.basicInfo.fields.name.placeholder')}
                disabled={isSubmitting}
                required
              />
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.name.helper')}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="wizard-basic-description" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.description.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <Textarea
                id="wizard-basic-description"
                value={data.description}
                onChange={(event) => updateField('description', event.target.value)}
                placeholder={t('workspace.wizard.steps.basicInfo.fields.description.placeholder')}
                disabled={isSubmitting}
                rows={4}
                required
                className="resize-none"
              />
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.description.helper')}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="wizard-basic-git" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.gitUrl.label')}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="wizard-basic-git"
                  value={data.gitUrl}
                  onChange={(event) => updateField('gitUrl', event.target.value)}
                  placeholder={t('workspace.wizard.steps.basicInfo.fields.gitUrl.placeholder')}
                  disabled={isSubmitting}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={fetchBranches}
                  disabled={isSubmitting || isLoadingBranches || !data.gitUrl.trim()}
                  title={t('workspace.wizard.steps.basicInfo.fields.gitUrl.fetchBranches')}
                >
                  <RefreshCw className={cn('h-4 w-4', isLoadingBranches && 'animate-spin')} />
                </Button>
              </div>
              {branchError && (
                <p className="text-xs text-destructive">{branchError}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.gitUrl.helper')}
              </p>
            </div>

            {/* Show branch choices only after branches are fetched. */}
            {branches.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="wizard-basic-branch" className="text-sm font-medium">
                  {t('workspace.wizard.steps.basicInfo.fields.branch.label')}
                </Label>
                <Select
                  value={data.branch}
                  onValueChange={(value) => updateField('branch', value)}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="wizard-basic-branch">
                    <SelectValue placeholder={t('workspace.wizard.steps.basicInfo.fields.branch.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {branches.map((branch) => (
                      <SelectItem key={branch} value={branch}>
                        {branch}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {t('workspace.wizard.steps.basicInfo.fields.branch.helper')}
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.cliType.label')}
              </Label>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {cliTypeOptions.map((option) => {
                  const isSelected = data.cliType === option.value;

                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => updateField('cliType', option.value)}
                      disabled={isSubmitting}
                      className={cn(
                        'group flex min-h-[132px] flex-col rounded-lg border bg-card p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
                        isSelected
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-border hover:border-primary/60 hover:bg-accent/40'
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-md border border-border bg-background">
                            <img src={option.iconSrc} alt="" className="h-7 w-7 object-contain" />
                          </span>
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-foreground">
                              {t(option.labelKey)}
                            </div>
                            {isSelected && (
                              <div className="mt-1 inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                                <Check className="h-3 w-3" />
                                {t('workspace.wizard.steps.basicInfo.fields.cliType.selected')}
                              </div>
                            )}
                          </div>
                        </div>
                        <ChevronRight
                          className={cn(
                            'mt-1 h-4 w-4 text-muted-foreground transition-colors',
                            isSelected ? 'text-primary' : 'group-hover:text-primary'
                          )}
                        />
                      </div>
                      <p className="mt-3 text-xs leading-5 text-muted-foreground">
                        {t(option.descriptionKey)}
                      </p>
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.cliType.helper')}
              </p>
            </div>

            {!isValid && (
              <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                <Info className="mt-0.5 h-4 w-4" />
                <div className="flex flex-col gap-1">
                  <span>{t('workspace.wizard.validation.basicInfo')}</span>
                  {hasGitUrl && !hasFetchedBranches && (
                    <span className="text-xs">{t('workspace.wizard.validation.gitFetchRequired')}</span>
                  )}
                  {hasGitUrl && hasFetchedBranches && branches.length === 0 && (
                    <span className="text-xs">{t('workspace.wizard.validation.gitFetchFailed')}</span>
                  )}
                  {hasGitUrl && hasFetchedBranches && branches.length > 0 && !data.branch && (
                    <span className="text-xs">{t('workspace.wizard.validation.branchRequired')}</span>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-4">
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                {t('workspace.wizard.buttons.cancel')}
              </Button>
              <Button type="submit" disabled={!isValid || isSubmitting} className={cn('bg-primary text-primary-foreground')}>
                {isSubmitting ? t('workspace.wizard.buttons.processing') : t('workspace.wizard.buttons.next')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default BasicInfoStep;
