import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';

interface ListPaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

const PAGE_SIZE_OPTIONS = [25, 50, 100];

export const ListPagination: React.FC<ListPaginationProps> = ({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}) => {
  const { t } = useI18n();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : ((page - 1) * pageSize) + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex h-11 shrink-0 items-center justify-between gap-3 border-t bg-background px-3">
      <div className="min-w-0 truncate text-xs text-muted-foreground">
        {t('userManagement.pagination.range', { start, end, total })}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Select
          value={String(pageSize)}
          onValueChange={value => onPageSizeChange(Number(value))}
        >
          <SelectTrigger
            className="h-8 w-[92px] text-xs"
            aria-label={t('userManagement.pagination.pageSize')}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PAGE_SIZE_OPTIONS.map(option => (
              <SelectItem key={option} value={String(option)}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            disabled={page <= 1}
            aria-label={t('userManagement.pagination.previous')}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            disabled={page >= totalPages}
            aria-label={t('userManagement.pagination.next')}
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
};
