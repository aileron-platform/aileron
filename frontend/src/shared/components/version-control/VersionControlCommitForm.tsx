import React, { useState } from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

interface VersionControlCommitFormProps {
  onCommit?: (data: { message: string }) => void;
  isLoading?: boolean;
  disabled?: boolean;
  stagedCount?: number;
  placeholderKey?: string;
  submitKey?: string;
  submittingKey?: string;
  className?: string;
  inputClassName?: string;
  buttonClassName?: string;
}

export const VersionControlCommitForm: React.FC<VersionControlCommitFormProps> = ({
  onCommit,
  isLoading = false,
  disabled = false,
  stagedCount = 0,
  placeholderKey = 'shared.versionControl.commitForm.placeholder',
  submitKey = 'shared.versionControl.commitForm.submit',
  submittingKey = 'shared.versionControl.commitForm.submitting',
  className,
  inputClassName,
  buttonClassName,
}) => {
  const [commitMessage, setCommitMessage] = useState('');
  const { t } = useI18n();
  const formDisabled = disabled || isLoading;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const message = commitMessage.trim();
    if (!message || stagedCount === 0 || formDisabled) {
      return;
    }
    onCommit?.({ message });
    setCommitMessage('');
  };

  return (
    <div className={cn('px-3 py-2 border-b border-border bg-card/50 flex-shrink-0', className)}>
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          placeholder={t(placeholderKey)}
          value={commitMessage}
          onChange={(event) => setCommitMessage(event.target.value)}
          className={cn(
            'min-w-0 flex-1 h-8 px-2.5 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background',
            inputClassName,
          )}
          disabled={formDisabled}
        />
        <button
          type="submit"
          disabled={!commitMessage.trim() || stagedCount === 0 || formDisabled}
          className={cn(
            'shrink-0 h-8 px-3 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
            buttonClassName,
          )}
        >
          {isLoading ? t(submittingKey) : t(submitKey)}
        </button>
      </form>
    </div>
  );
};
