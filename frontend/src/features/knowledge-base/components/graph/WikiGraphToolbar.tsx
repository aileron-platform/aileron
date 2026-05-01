import React from 'react';
import {
  Focus,
  RefreshCw,
  RotateCcw,
  Search,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

interface WikiGraphToolbarProps {
  searchTerm: string;
  isLoading: boolean;
  onSearchTermChange: (value: string) => void;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetLayout: () => void;
  onRefresh: () => void;
}

export const WikiGraphToolbar: React.FC<WikiGraphToolbarProps> = ({
  searchTerm,
  isLoading,
  onSearchTermChange,
  onFit,
  onZoomIn,
  onZoomOut,
  onResetLayout,
  onRefresh,
}) => {
  const { t } = useI18n();

  const iconButton = (
    label: string,
    icon: React.ReactNode,
    onClick: () => void,
    disabled = false,
  ) => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label={label}
          title={label}
          disabled={disabled}
          onClick={onClick}
        >
          {icon}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );

  const actionGroup = (children: React.ReactNode, className?: string) => (
    <div className={cn('flex items-center gap-1', className)}>
      {children}
    </div>
  );

  const separator = <div className="mx-1 h-6 w-px bg-border" />;

  return (
    <TooltipProvider>
      <div className="flex h-10 flex-wrap items-center gap-3 border-b bg-card px-3">
        <div className="relative min-w-56 flex-1 sm:max-w-80">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchTerm}
            className="h-8 pl-8"
            placeholder={t('knowledgeBase.graph.search.placeholder')}
            aria-label={t('knowledgeBase.graph.search.label')}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1">
          {actionGroup(
            <>
              {iconButton(t('knowledgeBase.graph.actions.fit'), <Focus className="h-4 w-4" />, onFit)}
              {iconButton(t('knowledgeBase.graph.actions.zoomIn'), <ZoomIn className="h-4 w-4" />, onZoomIn)}
              {iconButton(t('knowledgeBase.graph.actions.zoomOut'), <ZoomOut className="h-4 w-4" />, onZoomOut)}
            </>,
          )}
          {separator}
          {actionGroup(
            <>
              {iconButton(t('knowledgeBase.graph.actions.resetLayout'), <RotateCcw className="h-4 w-4" />, onResetLayout)}
            </>,
          )}
          {separator}
          {actionGroup(
            <>
              {iconButton(t('knowledgeBase.common.actions.refresh'), <RefreshCw className={isLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />, onRefresh, isLoading)}
            </>,
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};
