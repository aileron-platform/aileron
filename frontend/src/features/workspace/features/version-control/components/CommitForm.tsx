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
    <div className="p-4 border-b border-border bg-card/50 flex-shrink-0">
      {/* 提交表單 */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          placeholder={t('workspace.versionControl.commitForm.placeholder')}
          value={commitMessage}
          onChange={(e) => setCommitMessage(e.target.value)}
          className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={!commitMessage.trim() || stagedCount === 0 || isLoading}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading
            ? t('workspace.versionControl.commitForm.submitting')
            : t('workspace.versionControl.commitForm.submit')}
        </button>
      </form>
    </div>
  );
};
