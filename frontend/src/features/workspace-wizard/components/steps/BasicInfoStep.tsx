import React, { useState } from 'react';
import { Folder, GitBranch, Info, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';
import { apiClient } from '@/shared/api/apiClient';
import { BasicInfoForm } from '../../types';
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
    // 如果修改了 gitUrl，重置分支相關狀態
    if (field === 'gitUrl') {
      setBranches([]);
      setHasFetchedBranches(false);
      setBranchError(null);
      onChange({ ...data, [field]: value, branch: '' });
    } else {
      onChange({ ...data, [field]: value });
    }
  };

  // 驗證邏輯：
  // 1. 基本欄位必填
  // 2. 如果填寫了 gitUrl，則必須點擊整理按鈕並成功獲取分支
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

  // 從 Git URL 獲取分支列表
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
      // 使用 apiClient 調用後端 API 獲取分支列表（會自動加上 Authorization header）
      const result = await apiClient.get<{ branches: string[]; total: number }>(
        `/workspaces/temp/setup/git-branches?git_url=${encodeURIComponent(data.gitUrl)}`
      );

      const fetchedBranches = result.branches || [];
      setBranches(fetchedBranches);
      setHasFetchedBranches(true);

      // 如果當前沒有選擇分支，自動選擇第一個
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

            {/* 分支選擇 - 只在成功獲取分支後顯示 */}
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
              <Label htmlFor="wizard-basic-cli" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.cliType.label')}
              </Label>
              <Select value={data.cliType} onValueChange={(v) => updateField('cliType', v)}>
                <SelectTrigger id="wizard-basic-cli">
                  <SelectValue placeholder={t('workspace.wizard.steps.basicInfo.fields.cliType.placeholder')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="claude-code">{t('workspace.wizard.steps.basicInfo.fields.cliType.options.claudeCode')}</SelectItem>
                  <SelectItem value="codex">{t('workspace.wizard.steps.basicInfo.fields.cliType.options.codex')}</SelectItem>
                  <SelectItem value="gemini">{t('workspace.wizard.steps.basicInfo.fields.cliType.options.gemini')}</SelectItem>
                </SelectContent>
              </Select>
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
