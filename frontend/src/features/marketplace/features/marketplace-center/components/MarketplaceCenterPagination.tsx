import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { PAGE_SIZE_OPTIONS } from '../marketplaceCenterModel';

interface MarketplaceCenterPaginationProps {
  page: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export const MarketplaceCenterPagination: React.FC<MarketplaceCenterPaginationProps> = ({
  page,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4 text-sm">
      <div className="flex items-center gap-3">
        <span>
          {t('marketplace.center.pagination.pageCount', {
            current: page,
            total: totalPages,
          })}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t('marketplace.center.pagination.previous')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={page >= totalPages}
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          >
            {t('marketplace.center.pagination.next')}
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span>{t('marketplace.center.pagination.perPage')}</span>
        <div className="flex items-center gap-2">
          {PAGE_SIZE_OPTIONS.map(size => (
            <Button
              key={size}
              variant={pageSize === size ? 'default' : 'outline'}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => onPageSizeChange(size)}
            >
              {t('marketplace.center.pagination.perPageOption', { count: size })}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};
