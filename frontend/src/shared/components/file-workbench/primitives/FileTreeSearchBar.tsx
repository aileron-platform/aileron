import React from 'react';
import { Search, X } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface FileTreeSearchBarProps {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  onClear?: () => void;
  disabled?: boolean;
  showSearchButton?: boolean;
  searchButtonLabel?: string;
  searchButtonContent?: React.ReactNode;
  searchButtonDisabled?: boolean;
  isLoading?: boolean;
  showClearButton?: boolean;
  summary?: React.ReactNode;
  className?: string;
  containerClassName?: string;
  inputClassName?: string;
  searchButtonClassName?: string;
  clearButtonClassName?: string;
  iconClassName?: string;
  summaryClassName?: string;
}

export const FileTreeSearchBar: React.FC<FileTreeSearchBarProps> = ({
  value,
  placeholder,
  onChange,
  onSubmit,
  onClear,
  disabled = false,
  showSearchButton = false,
  searchButtonLabel,
  searchButtonContent,
  searchButtonDisabled,
  isLoading = false,
  showClearButton,
  summary,
  className,
  containerClassName,
  inputClassName,
  searchButtonClassName,
  clearButtonClassName,
  iconClassName,
  summaryClassName,
}) => {
  const { t } = useI18n();

  const resolvedSearchButtonDisabled =
    typeof searchButtonDisabled === 'boolean'
      ? searchButtonDisabled
      : disabled || !value.trim() || isLoading;

  const handleSubmit = React.useCallback(() => {
    if (disabled || resolvedSearchButtonDisabled) {
      return;
    }
    onSubmit?.();
  }, [disabled, resolvedSearchButtonDisabled, onSubmit]);

  return (
    <div className={cn('flex items-center h-10 px-3 border-b border-border flex-shrink-0 gap-2', containerClassName, className)}>
      <div className="relative flex-1">
        <Search className={cn('absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground', iconClassName)} />
        <Input
          value={value}
          placeholder={placeholder}
          onChange={event => onChange(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter') {
              event.preventDefault();
              handleSubmit();
            }
          }}
          disabled={disabled}
          className={cn('pl-8 h-7 text-xs', inputClassName)}
        />
        {showClearButton && onClear ? (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => onClear?.()}
            className={cn(
              'absolute right-1.5 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground hover:bg-muted/60',
              clearButtonClassName,
            )}
          >
            <X className="h-3 w-3" />
          </Button>
        ) : null}
      </div>
      {showSearchButton ? (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={disabled || resolvedSearchButtonDisabled}
          onClick={handleSubmit}
          className={cn('h-7 px-2 text-xs', searchButtonClassName)}
        >
          {searchButtonContent ?? searchButtonLabel ?? t('common.fileTree.search.button')}
        </Button>
      ) : null}
      {summary ? <div className={cn('text-xs text-muted-foreground', summaryClassName)}>{summary}</div> : null}
    </div>
  );
};
