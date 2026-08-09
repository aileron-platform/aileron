import React, { useMemo, useState } from 'react';
import {
  Layers,
  RefreshCw,
  Search,
  type LucideIcon,
} from 'lucide-react';
import { DocumentList } from '@/shared/components/document-workflow';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { SidebarCollapseToggle } from '@/shared/components/layout/CollapsedSidebarControls';
import { ResourceSidebarShell } from '@/shared/components/resource-workflow';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  DocumentSourceBadge,
  getDocumentSourceIcon,
  type DocumentSourceType,
} from '@/shared/components/document-resource';
import {
  AgentSettingsSourceFilter,
  type AgentSettingsSourceOption,
} from '../AgentSettingsSourceControls';

export interface AgentSettingsDocumentSidebarItem {
  id: string;
  label: string;
  description?: string;
  source: DocumentSourceType;
  sourceLabel: string;
  sizeLabel?: string;
  readOnly?: boolean;
  badges?: Array<{ key: string; label: string; tone?: 'default' | 'muted' }>;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentSettingsDocumentSidebarLabels {
  searchPlaceholder: string;
  loading: string;
  empty: string;
  refresh: string;
  toggleCollapse: string;
  toggleExpand: string;
  readOnly?: string;
}

export interface AgentSettingsDocumentSidebarProps<TFilterValue extends string = string> {
  title: string;
  icon: LucideIcon;
  items: AgentSettingsDocumentSidebarItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  isLoading?: boolean;
  isRefreshing?: boolean;
  onRefresh?: () => void | Promise<void>;
  filterValue: TFilterValue;
  onFilterChange: (value: TFilterValue) => void;
  filterOptions: AgentSettingsSourceOption<TFilterValue>[];
  filterLabel: string;
  labels: AgentSettingsDocumentSidebarLabels;
  collapsed?: boolean;
  showHeader?: boolean;
}

const badgeToneClassName: Record<NonNullable<AgentSettingsDocumentSidebarItem['badges']>[number]['tone'], string> = {
  default: 'text-[10px]',
  muted: 'border-border/70 bg-muted/50 text-[10px] text-muted-foreground',
};

export const AgentSettingsDocumentSidebar = <TFilterValue extends string = string>({
  title,
  icon: Icon,
  items,
  selectedId,
  onSelect,
  isLoading = false,
  isRefreshing = false,
  onRefresh,
  filterValue,
  onFilterChange,
  filterOptions,
  filterLabel,
  labels,
  collapsed = false,
  showHeader = true,
}: AgentSettingsDocumentSidebarProps<TFilterValue>) => {
  const [query, setQuery] = useState('');
  const isCollapsed = collapsed;

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesFilter = filterOptions.some((option) => option.value === filterValue)
        ? filterValue === filterOptions[0]?.value || item.source === filterValue
        : true;
      if (!matchesFilter) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      return item.label.toLowerCase().includes(normalizedQuery)
        || item.description?.toLowerCase().includes(normalizedQuery)
        || item.badges?.some((badge) => badge.label.toLowerCase().includes(normalizedQuery))
        || false;
    });
  }, [filterOptions, filterValue, items, query]);

  const header = showHeader ? (
      <div className={`flex h-10 items-center border-b border-border bg-card px-3 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
        {!isCollapsed ? (
          <div className="flex min-w-0 items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
            <span className="truncate text-sm font-medium">{title}</span>
          </div>
        ) : null}
        <div className="flex flex-shrink-0 items-center gap-1">
          {!isCollapsed ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => void onRefresh?.()}
              disabled={isRefreshing || !onRefresh}
              aria-label={labels.refresh}
              title={labels.refresh}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          ) : null}
          <SidebarCollapseToggle
            collapsed={isCollapsed}
            label={isCollapsed ? labels.toggleExpand : labels.toggleCollapse}
            onClick={() => undefined}
          />
        </div>
      </div>
  ) : undefined;

  const filterControls = !isCollapsed ? (
    <div className="border-b border-border bg-muted/30">
            <div className="p-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={labels.searchPlaceholder}
                  className="h-7 pl-8 text-xs"
                />
              </div>
            </div>
            <AgentSettingsSourceFilter
              value={filterValue}
              onChange={onFilterChange}
              options={filterOptions}
              label={filterLabel}
              className="border-t border-border/70 px-2 pb-2 pt-2"
            />
    </div>
  ) : undefined;

  const body = isCollapsed ? (
    <CollapsedSidebarPlaceholder icon={Icon} />
  ) : (
    <DocumentList
      items={filteredItems}
      selectedId={selectedId}
      onSelect={onSelect}
      labels={{
        loading: labels.loading,
        empty: labels.empty,
        dirty: '',
      }}
      isLoading={isLoading && items.length === 0}
      emptySelectionBehavior="preserveOnEmpty"
      renderItemMeta={(item) => (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <DocumentSourceBadge
              source={{
                type: item.source,
                label: item.sourceLabel,
                pluginName: item.pluginName,
                marketplaceName: item.marketplaceName,
              }}
              className="flex-shrink-0 whitespace-nowrap px-1 py-0 text-[10px]"
            />
            {item.readOnly && labels.readOnly ? (
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {labels.readOnly}
              </Badge>
            ) : null}
            {item.sizeLabel ? (
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {item.sizeLabel}
              </Badge>
            ) : null}
            {item.badges?.map((badge) => (
              <Badge
                key={badge.key}
                variant="outline"
                className={badgeToneClassName[badge.tone ?? 'default']}
              >
                {badge.label}
              </Badge>
            ))}
          </div>
        </>
      )}
    />
  );

  return (
    <ResourceSidebarShell
      className="bg-background text-foreground"
      header={header}
      scopeFilter={filterControls}
      body={body}
      bodyClassName={isCollapsed ? 'flex-1' : 'flex-1 space-y-1.5 overflow-y-auto p-2'}
    />
  );
};

AgentSettingsDocumentSidebar.displayName = 'AgentSettingsDocumentSidebar';

export const buildSidebarSourceOption = <TValue extends string = string>(
  value: TValue,
  label: string,
): AgentSettingsSourceOption<TValue> => {
  const Icon = value === 'all' ? Layers : getDocumentSourceIcon(value);
  return {
    value,
    label,
    icon: <Icon className="h-3 w-3" />,
  };
};

export default AgentSettingsDocumentSidebar;
