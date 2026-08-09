import React from 'react';
import { ArrowUpDown, Search, SlidersHorizontal, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { useI18n } from '@/shared/hooks/useI18n';

interface ListFilterButton {
  id: string;
  labelKey: string;
}

interface SelectFilterOption {
  value: string;
  labelKey: string;
}

interface SelectFilter {
  id: string;
  labelKey: string;
  value: string;
  options: SelectFilterOption[];
  onChange: (value: string) => void;
}

interface SortOption {
  value: string;
  labelKey: string;
}

interface ListFilterBarProps {
  searchLabel: string;
  searchPlaceholder: string;
  query: string;
  onQueryChange: (query: string) => void;
  filters?: ListFilterButton[];
  selectFilters?: SelectFilter[];
  sortOptions?: SortOption[];
  sortValue?: string;
  onSortChange?: (value: string) => void;
  hasAppliedFilters?: boolean;
  resultLabelKey?: string;
  resultCount?: number;
  totalCount?: number;
  onClearAll?: () => void;
}

export const ListFilterBar: React.FC<ListFilterBarProps> = ({
  searchLabel,
  searchPlaceholder,
  query,
  onQueryChange,
  filters = [],
  selectFilters = [],
  sortOptions = [],
  sortValue,
  onSortChange,
  hasAppliedFilters = false,
  resultLabelKey,
  resultCount,
  totalCount,
  onClearAll,
}) => {
  const { t } = useI18n();
  const hasActiveFilters = hasAppliedFilters || query.trim().length > 0;
  const activeAdvancedCount = selectFilters.filter(filter => filter.value !== 'all').length;

  return (
    <div className="flex min-h-11 min-w-0 items-center gap-2 border-b bg-background/95 px-3 py-1.5">
      <div className="relative min-w-[220px] flex-1">
        <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={query}
          onChange={event => onQueryChange(event.target.value)}
          className="h-8 pl-8 text-xs"
          placeholder={t(searchPlaceholder)}
          aria-label={t(searchLabel)}
        />
      </div>

      {selectFilters.length > 0 || filters.length > 0 ? (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 shrink-0 gap-1.5 px-2 text-xs"
              aria-label={t('userManagement.filters.advanced')}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {t('userManagement.filters.advanced')}
              {activeAdvancedCount > 0 ? (
                <span className="ml-0.5 rounded bg-primary px-1.5 py-0.5 text-[10px] leading-none text-primary-foreground">
                  {activeAdvancedCount}
                </span>
              ) : null}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-3">
            <div className="space-y-3">
              <div>
                <div className="text-xs font-medium text-foreground">{t('userManagement.filters.advanced')}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {t('userManagement.filters.advancedDescription')}
                </div>
              </div>

              <div className="space-y-2">
                {selectFilters.map(filter => (
                  <label key={filter.id} className="grid grid-cols-[96px_minmax(0,1fr)] items-center gap-2">
                    <span className="truncate text-xs text-muted-foreground">{t(filter.labelKey)}</span>
                    <select
                      value={filter.value}
                      onChange={event => filter.onChange(event.target.value)}
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus:ring-2 focus:ring-ring"
                      aria-label={t(filter.labelKey)}
                    >
                      {filter.options.map(option => (
                        <option key={option.value} value={option.value}>
                          {t(option.labelKey)}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>

              {filters.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 border-t pt-2">
                  {filters.map(filter => (
                    <span key={filter.id} className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                      {t(filter.labelKey)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </PopoverContent>
        </Popover>
      ) : null}

      {sortOptions.length > 0 && sortValue && onSortChange ? (
        <label className="flex shrink-0 items-center gap-1.5 rounded-md border bg-background px-2">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="sr-only">{t('userManagement.sort.label')}</span>
          <select
            value={sortValue}
            onChange={event => onSortChange(event.target.value)}
            className="h-8 bg-transparent text-xs text-foreground outline-none"
            aria-label={t('userManagement.sort.label')}
          >
            {sortOptions.map(option => (
              <option key={option.value} value={option.value}>
                {t(option.labelKey)}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {resultLabelKey && resultCount !== undefined && totalCount !== undefined ? (
          <span className="text-xs text-muted-foreground">
            {t(resultLabelKey, { count: resultCount, total: totalCount })}
          </span>
        ) : null}

        {onClearAll && hasActiveFilters ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            aria-label={t('userManagement.filters.clearAll')}
            onClick={onClearAll}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        ) : null}
      </div>
    </div>
  );
};
