import React, { useEffect, useMemo, useState } from 'react';
import { GitBranch, GitPullRequest, CheckCircle2, Loader2, Lock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTaskProgress } from '@/shared/hooks/useTaskProgress';
import { TaskProgressCard } from '@/shared/components/task-progress/TaskProgressCard';
import type { GitUserConfigRequest, CloneStatus } from '@/shared/services/templateGitApi';
import { getCloneProgress, checkCloneStatus } from '@/shared/services/templateGitApi';

interface GitUserConfigTabProps {
  value: GitUserConfigRequest | null;
  remoteUrl: string;
  onSave: (value: GitUserConfigRequest) => Promise<void> | void;
  onCloneRepository: (url: string, branch?: string) => Promise<void> | void;
  isSaving?: boolean;
  isCloningRepository?: boolean;
}

const emptyConfig: GitUserConfigRequest = {
  userName: '',
  userEmail: '',
};

export const GitUserConfigTab: React.FC<GitUserConfigTabProps> = ({
  value,
  remoteUrl,
  onSave,
  onCloneRepository,
  isSaving,
  isCloningRepository
}) => {
  const { t } = useI18n();
  const [formValue, setFormValue] = useState<GitUserConfigRequest>(emptyConfig);
  const [repoUrlValue, setRepoUrlValue] = useState<string>('');
  const [branchValue, setBranchValue] = useState<string>('');
  const [cloneStatus, setCloneStatus] = useState<CloneStatus | null>(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);

  // 使用 useTaskProgress Hook 管理 clone 進度
  const {
    progress: taskProgress,
    isPolling,
    resetProgress: resetCloneProgress,
  } = useTaskProgress(
    null,
    getCloneProgress
  );

  // 檢查倉庫狀態
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await checkCloneStatus();
        if (response.success && response.data) {
          setCloneStatus(response.data);
        }
      } catch (error) {
        // 靜默失敗，不顯示日誌
      } finally {
        setIsCheckingStatus(false);
      }
    };

    void checkStatus();
  }, []);

  useEffect(() => {
    if (value) {
      setFormValue({ ...value });
    } else {
      setFormValue(emptyConfig);
    }
  }, [value]);

  useEffect(() => {
    setRepoUrlValue(remoteUrl);
  }, [remoteUrl]);

  const initialUserName = value?.userName ?? '';
  const initialUserEmail = value?.userEmail ?? '';

  const isUserConfigDirty = useMemo(() => {
    return (
      formValue.userName !== initialUserName ||
      formValue.userEmail !== initialUserEmail
    );
  }, [formValue.userEmail, formValue.userName, initialUserEmail, initialUserName]);

  const isUserConfigValid = useMemo(() => {
    return Boolean(formValue.userName.trim()) && Boolean(formValue.userEmail.trim());
  }, [formValue.userEmail, formValue.userName]);

  const isRepoUrlValid = useMemo(() => {
    return Boolean(repoUrlValue.trim());
  }, [repoUrlValue]);

  const handleChange = (key: keyof GitUserConfigRequest, nextValue: string) => {
    setFormValue((prev) => ({
      ...prev,
      [key]: nextValue,
    }));
  };

  const handleSubmitUserConfig = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isUserConfigValid) {
      return;
    }
    void onSave({
      userName: formValue.userName.trim(),
      userEmail: formValue.userEmail.trim(),
    });
  };

  const handleCloneRepository = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRepoUrlValid) {
      return;
    }

    try {
      await onCloneRepository(repoUrlValue.trim(), branchValue.trim() || undefined);
      // onCloneRepository 會在父組件中處理任務 ID 的設置
      // 這裡只需要調用即可
    } catch (error) {
      // 錯誤由父組件的 toast 處理
    }
  };

  return (
    <div className="space-y-4">
      {/* Clone Git 倉庫 */}
      <form onSubmit={handleCloneRepository}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitPullRequest className="h-5 w-5" />
              {t('template.center.settingsDialog.git.cloneRepo.title')}
            </CardTitle>
            <CardDescription>
              {t('template.center.settingsDialog.git.cloneRepo.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 已 Clone 提示 */}
            {cloneStatus?.is_cloned && (
              <Alert className="border-green-200 bg-green-50">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800">
                  <div className="font-medium">
                    {t('template.center.settingsDialog.git.cloneRepo.successAlertTitle')}
                  </div>
                  <div className="text-sm mt-1">
                    {t('template.center.settingsDialog.git.cloneRepo.remoteLabel')}: {cloneStatus.remote_url}
                  </div>
                  <div className="text-sm">
                    {t('template.center.settingsDialog.git.cloneRepo.branchStatusLabel')}: {cloneStatus.current_branch}
                  </div>
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="gitRepoUrl">
                {t('template.center.settingsDialog.git.cloneRepo.urlLabel')}
              </Label>
              <div className="relative">
                <Input
                  id="gitRepoUrl"
                  value={repoUrlValue}
                  placeholder={t('template.center.settingsDialog.git.cloneRepo.urlPlaceholder')}
                  onChange={(event) => setRepoUrlValue(event.target.value)}
                  disabled={cloneStatus?.is_cloned || isCheckingStatus}
                />
                {cloneStatus?.is_cloned && (
                  <Lock className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="gitBranch">
                {t('template.center.settingsDialog.git.cloneRepo.branchLabel')}
              </Label>
              <Input
                id="gitBranch"
                value={branchValue}
                placeholder={t('template.center.settingsDialog.git.cloneRepo.branchPlaceholder')}
                onChange={(event) => setBranchValue(event.target.value)}
                disabled={cloneStatus?.is_cloned || isCheckingStatus}
              />
              <p className="text-xs text-muted-foreground">
                {t('template.center.settingsDialog.git.cloneRepo.branchHelper')}
              </p>
            </div>

            <p className="text-xs text-muted-foreground">
              {t('template.center.settingsDialog.git.cloneRepo.helper')}
            </p>

            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={!isRepoUrlValid || isCloningRepository || isPolling || cloneStatus?.is_cloned || isCheckingStatus}
              >
                {isPolling ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('template.center.settingsDialog.git.cloneRepo.actions.cloning')}
                  </>
                ) : isCloningRepository ? (
                  t('template.center.settingsDialog.git.cloneRepo.actions.cloning')
                ) : (
                  t('template.center.settingsDialog.git.cloneRepo.actions.clone')
                )}
              </Button>
            </div>

            {/* 進度顯示 */}
            {taskProgress && (
              <div className="border-t pt-4">
                <TaskProgressCard
                  progress={taskProgress}
                  title={t('template.center.settingsDialog.git.cloneRepo.cloneProgressTitle')}
                  onDismiss={resetCloneProgress}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </form>

      {/* Git 使用者設定 */}
      <form onSubmit={handleSubmitUserConfig}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              {t('template.center.settingsDialog.git.userConfig.title')}
            </CardTitle>
            <CardDescription>
              {t('template.center.settingsDialog.git.userConfig.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="gitUserName">
                {t('template.center.settingsDialog.git.userConfig.userNameLabel')}
              </Label>
              <Input
                id="gitUserName"
                value={formValue.userName}
                placeholder={t('template.center.settingsDialog.git.userConfig.userNamePlaceholder')}
                onChange={(event) => handleChange('userName', event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="gitUserEmail">
                {t('template.center.settingsDialog.git.userConfig.userEmailLabel')}
              </Label>
              <Input
                id="gitUserEmail"
                type="email"
                value={formValue.userEmail}
                placeholder={t('template.center.settingsDialog.git.userConfig.userEmailPlaceholder')}
                onChange={(event) => handleChange('userEmail', event.target.value)}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              {t('template.center.settingsDialog.git.userConfig.helper')}
            </p>

            <div className="flex justify-end">
              <Button type="submit" disabled={!isUserConfigDirty || !isUserConfigValid || isSaving}>
                {isSaving
                  ? t('template.center.settingsDialog.git.userConfig.actions.saving')
                  : t('template.center.settingsDialog.git.userConfig.actions.save')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
};

export default GitUserConfigTab;
