import React, { useState } from 'react';
import { GitCommit } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { useI18n } from '@/shared/hooks/useI18n';
import type { GitBranch } from '@/shared/services/templateGitApi';

interface CommitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  branches: GitBranch[];
  currentBranch: string;
  onCommit: (message: string, branch?: string, push?: boolean) => Promise<void>;
  isCommitting: boolean;
}

export const CommitDialog: React.FC<CommitDialogProps> = ({
  open,
  onOpenChange,
  branches,
  currentBranch,
  onCommit,
  isCommitting,
}) => {
  const { t } = useI18n();
  const [message, setMessage] = useState('');
  const [selectedBranch, setSelectedBranch] = useState<string>(currentBranch);
  const [autoPush, setAutoPush] = useState(true);

  const handleConfirm = async () => {
    if (!message.trim()) {
      return;
    }

    try {
      // 如果選擇的是當前分支，傳 undefined；否則傳選擇的分支名稱
      const targetBranch = selectedBranch === currentBranch ? undefined : selectedBranch;
      await onCommit(message, targetBranch, autoPush);
      // 成功後重置表單
      setMessage('');
      setSelectedBranch(currentBranch);
      setAutoPush(true);
      onOpenChange(false);
    } catch (error) {
      // 錯誤處理由父組件負責
    }
  };

  const handleCancel = () => {
    setMessage('');
    setSelectedBranch(currentBranch);
    setAutoPush(true);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitCommit className="h-5 w-5" />
            {t('template.center.settingsDialog.git.commitDialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t('template.center.settingsDialog.git.commitDialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Commit Message */}
          <div className="space-y-2">
            <Label htmlFor="commit-message" className="text-sm font-medium">
              {t('template.center.settingsDialog.git.commitDialog.messageLabel')}
              <span className="text-destructive ml-1">*</span>
            </Label>
            <Textarea
              id="commit-message"
              placeholder={t('template.center.settingsDialog.git.commitDialog.messagePlaceholder')}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className="resize-none"
              disabled={isCommitting}
            />
          </div>

          {/* Branch Selection */}
          <div className="space-y-2">
            <Label htmlFor="branch-select" className="text-sm font-medium">
              {t('template.center.settingsDialog.git.commitDialog.branchLabel')}
            </Label>
            <Select
              value={selectedBranch}
              onValueChange={setSelectedBranch}
              disabled={isCommitting}
            >
              <SelectTrigger id="branch-select">
                <SelectValue
                  placeholder={t('template.center.settingsDialog.git.commitDialog.branchPlaceholder')}
                />
              </SelectTrigger>
              <SelectContent>
                {/* 當前分支 */}
                <SelectItem value={currentBranch}>
                  {currentBranch} ({t('template.center.settingsDialog.git.status.currentBranchSuffix')})
                </SelectItem>
                {/* 其他分支 */}
                {branches
                  .filter((b) => !b.is_remote && b.name !== currentBranch)
                  .map((branch) => (
                    <SelectItem key={branch.name} value={branch.name}>
                      {branch.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Auto Push Checkbox */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto-push"
              checked={autoPush}
              onCheckedChange={(checked) => setAutoPush(checked as boolean)}
              disabled={isCommitting}
            />
            <Label
              htmlFor="auto-push"
              className="text-sm font-normal cursor-pointer"
            >
              {t('template.center.settingsDialog.git.commitDialog.pushLabel')}
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isCommitting}
          >
            {t('template.center.settingsDialog.git.commitDialog.actions.cancel')}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!message.trim() || isCommitting}
          >
            {isCommitting
              ? t('template.center.settingsDialog.git.commitDialog.actions.confirming')
              : t('template.center.settingsDialog.git.commitDialog.actions.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
