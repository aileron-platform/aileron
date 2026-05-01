import React from 'react';
import {
  BookOpen,
  Maximize,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
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

interface WikiGraphToolbarProps {
  searchTerm: string;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  isLoading: boolean;
  hasSelection: boolean;
  onSearchTermChange: (value: string) => void;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onRefresh: () => void;
  onOpenInWiki: () => void;
  onToggleLeft: () => void;
  onToggleRight: () => void;
}

export const WikiGraphToolbar: React.FC<WikiGraphToolbarProps> = ({
  searchTerm,
  leftCollapsed,
  rightCollapsed,
  isLoading,
  hasSelection,
  onSearchTermChange,
  onFit,
  onZoomIn,
  onZoomOut,
  onReset,
  onRefresh,
  onOpenInWiki,
  onToggleLeft,
  onToggleRight,
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

  return (
    <TooltipProvider>
      <div className="flex min-h-12 flex-wrap items-center gap-2 border-b bg-background px-3 py-2">
        <div className="relative min-w-56 flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchTerm}
            className="h-8 pl-8"
            placeholder={t('knowledgeBase.graph.search.placeholder')}
            aria-label={t('knowledgeBase.graph.search.label')}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
        </div>
        <div className="flex items-center gap-1">
          {iconButton(
            leftCollapsed ? t('knowledgeBase.graph.actions.showNodes') : t('knowledgeBase.graph.actions.hideNodes'),
            leftCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />,
            onToggleLeft,
          )}
          {iconButton(t('knowledgeBase.graph.actions.fit'), <Maximize className="h-4 w-4" />, onFit)}
          {iconButton(t('knowledgeBase.graph.actions.zoomIn'), <ZoomIn className="h-4 w-4" />, onZoomIn)}
          {iconButton(t('knowledgeBase.graph.actions.zoomOut'), <ZoomOut className="h-4 w-4" />, onZoomOut)}
          {iconButton(t('knowledgeBase.graph.actions.reset'), <RotateCcw className="h-4 w-4" />, onReset)}
          {iconButton(t('knowledgeBase.common.actions.refresh'), <RefreshCw className={isLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />, onRefresh, isLoading)}
          {iconButton(t('knowledgeBase.graph.actions.openInWiki'), <BookOpen className="h-4 w-4" />, onOpenInWiki, !hasSelection)}
          {iconButton(
            rightCollapsed ? t('knowledgeBase.graph.actions.showPreview') : t('knowledgeBase.graph.actions.hidePreview'),
            rightCollapsed ? <PanelRightOpen className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />,
            onToggleRight,
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};
