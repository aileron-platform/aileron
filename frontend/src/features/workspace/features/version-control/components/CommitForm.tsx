/**
 * CommitForm - 提交表單組件
 * 
 * 處理 Git 提交操作，包含提交訊息輸入和提交按鈕
 */

import React, { useState } from 'react';
import { useI18n } from '@/shared/hooks/useI18n';

interface CommitFormProps {
  onCommit?: (data: { message: string }) => void;
  isLoading?: boolean;
  stagedCount?: number;
  currentBranch?: string;
}

export const CommitForm: React.FC<CommitFormProps> = ({
  onCommit,
  isLoading = false,
  stagedCount = 0,
  currentBranch = 'main'
}) => {
  const [commitMessage, setCommitMessage] = useState('');
  const { t } = useI18n();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (commitMessage.trim() && stagedCount > 0) {
      onCommit?.({
        message: commitMessage.trim()
      });
      setCommitMessage('');
    }
  };

  return (
    <div className="px-3 py-2 border-b border-border bg-card/50 flex-shrink-0">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          placeholder={t('workspace.versionControl.commitForm.placeholder')}
          value={commitMessage}
          onChange={(e) => setCommitMessage(e.target.value)}
          className="min-w-0 flex-1 h-8 px-2.5 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={!commitMessage.trim() || stagedCount === 0 || isLoading}
          className="shrink-0 h-8 px-3 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading
            ? t('workspace.versionControl.commitForm.submitting')
            : t('workspace.versionControl.commitForm.submit')}
        </button>
      </form>
    </div>
  );
};
