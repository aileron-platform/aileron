import React from 'react';
import { Button } from '@/shared/components/ui/button';

interface PluginPaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  previousLabel: string;
  nextLabel: string;
  pageLabel: string;
  summaryLabel: string;
  onPageChange: (page: number) => void;
}

export const PluginPagination: React.FC<PluginPaginationProps> = ({
  page,
  totalPages,
  totalItems,
  pageSize,
  previousLabel,
  nextLabel,
  pageLabel,
  summaryLabel,
  onPageChange,
}) => {
  if (totalItems <= pageSize) {
    return null;
  }

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <span>{summaryLabel}</span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          {previousLabel}
        </Button>
        <span className="min-w-20 text-center">{pageLabel}</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          {nextLabel}
        </Button>
      </div>
    </div>
  );
};
