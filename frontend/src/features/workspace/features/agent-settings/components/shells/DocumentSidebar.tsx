import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, FileText, Layers, RefreshCw, Search } from 'lucide-react';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  AgentSettingsSourceBadge,
  AgentSettingsSourceFilter,
  getAgentSettingsSourceIcon,
  type AgentSettingsSourceOption,
  type AgentSettingsSourceType,
} from '../SettingsSourcePrimitives';

export interface SidebarItem {
  id: string;
  label: string;
  description?: string;
  source: AgentSettingsSourceType;
  sourceLabel: string;
  sizeLabel?: string;
  readOnly?: boolean;
  badges?: Array<{ key: string; label: string; tone?: 'default' | 'muted' }>;
  pluginName?: string;
  marketplaceName?: string;
  extensionName?: string;
  extensionVersion?: string;
}

interface DocumentSidebarLabels {
  searchPlaceholder: string;
  loading: string;
  empty: string;
  refresh: string;
  toggleCollapse: string;
  toggleExpand: string;
  readOnly?: string;
}

export interface DocumentSidebarProps<TFilterValue extends string = string> {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: SidebarItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  isLoading?: boolean;
  isRefreshing?: boolean;
  onRefresh?: () => void | Promise<void>;
  filterValue: TFilterValue;
  onFilterChange: (value: TFilterValue) => void;
  filterOptions: AgentSettingsSourceOption<TFilterValue>[];
  filterLabel: string;
  labels: DocumentSidebarLabels;
}

const badgeToneClassName: Record<NonNullable<SidebarItem['badges']>[number]['tone'], string> = {
  default: 'text-[10px]',
  muted: 'border-border/70 bg-muted/50 text-[10px] text-muted-foreground',
};

export const DocumentSidebar = <TFilterValue extends string = string>({
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
}: DocumentSidebarProps<TFilterValue>) => {
  const { layout, toggleSecondColumn } = useWorkspace();
  const [search, setSearch] = useState('');
  const isCollapsed = layout.secondColumnCollapsed;

  const filteredItems = useMemo(() => {
    const normalizedQuery = search.trim().toLowerCase();
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
  }, [filterOptions, filterValue, items, search]);

  useEffect(() => {
    const selectedExists = selectedId
      ? filteredItems.some((item) => item.id === selectedId)
      : false;
    if (filteredItems.length > 0 && (!selectedId || !selectedExists)) {
      onSelect(filteredItems[0].id);
    }
  }, [filteredItems, onSelect, selectedId]);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
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
          <button
            type="button"
            onClick={toggleSecondColumn}
            className="rounded p-0.5 text-sidebar-foreground hover:bg-sidebar-accent"
            aria-label={isCollapsed ? labels.toggleExpand : labels.toggleCollapse}
            title={isCollapsed ? labels.toggleExpand : labels.toggleCollapse}
          >
            <ChevronLeft className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {isCollapsed ? (
        <CollapsedSidebarPlaceholder icon={Icon} className="text-primary" iconClassName="text-primary" />
      ) : (
        <>
          <div className="space-y-2 border-b border-border bg-muted/30 p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={labels.searchPlaceholder}
                className="h-7 pl-8 text-xs"
              />
            </div>
            <AgentSettingsSourceFilter
              value={filterValue}
              onChange={onFilterChange}
              options={filterOptions}
              label={filterLabel}
            />
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto p-2">
            {isLoading && items.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {labels.loading}
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
                {labels.empty}
              </div>
            ) : (
              filteredItems.map((item) => {
                const isActive = item.id === selectedId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelect(item.id)}
                    className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                      isActive
                        ? 'border-primary/60 bg-primary/10 shadow-sm'
                        : 'border-transparent bg-muted/20 hover:border-primary/20 hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                          <div className="truncate text-sm font-medium">{item.label}</div>
                        </div>
                        {item.description ? (
                          <div className="truncate text-xs text-muted-foreground">{item.description}</div>
                        ) : null}
                      </div>
                      <AgentSettingsSourceBadge
                        source={{
                          type: item.source,
                          label: item.sourceLabel,
                          pluginName: item.pluginName,
                          marketplaceName: item.marketplaceName,
                          extensionName: item.extensionName,
                          extensionVersion: item.extensionVersion,
                        }}
                        className="flex-shrink-0 whitespace-nowrap px-1 py-0 text-[10px]"
                      />
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
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
                  </button>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
};

DocumentSidebar.displayName = 'DocumentSidebar';

export const buildSidebarSourceOption = <TValue extends string = string>(
  value: TValue,
  label: string,
): AgentSettingsSourceOption<TValue> => {
  const Icon = value === 'all' ? Layers : getAgentSettingsSourceIcon(value);
  return {
    value,
    label,
    icon: <Icon className="h-3 w-3" />,
  };
};

export default DocumentSidebar;
