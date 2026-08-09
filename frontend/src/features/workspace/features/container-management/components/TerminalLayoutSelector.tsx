import React, { useMemo } from 'react';
import {
  Square,
  Columns,
  Rows,
  LayoutGrid,
  PanelLeft,
  PanelRight,
  PanelTop,
  PanelBottom,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import type { TerminalLayoutType } from '../model/terminalLayoutModel';

interface TerminalLayoutSelectorProps {
  currentLayout: TerminalLayoutType;
  onLayoutChange: (layout: TerminalLayoutType) => void;
}

const LAYOUT_CONFIG: Record<
  TerminalLayoutType,
  {
    icon: React.ElementType;
    labelKey: string;
    descriptionKey: string;
  }
> = {
  single: {
    icon: Square,
    labelKey: 'workspace.containerManagement.terminal.layout.options.single.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.single.description',
  },
  'split-horizontal': {
    icon: Columns,
    labelKey: 'workspace.containerManagement.terminal.layout.options.splitHorizontal.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.splitHorizontal.description',
  },
  'split-vertical': {
    icon: Rows,
    labelKey: 'workspace.containerManagement.terminal.layout.options.splitVertical.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.splitVertical.description',
  },
  quad: {
    icon: LayoutGrid,
    labelKey: 'workspace.containerManagement.terminal.layout.options.quad.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.quad.description',
  },
  'left-1-right-2': {
    icon: PanelLeft,
    labelKey: 'workspace.containerManagement.terminal.layout.options.leftOneRightTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.leftOneRightTwo.description',
  },
  'right-1-left-2': {
    icon: PanelRight,
    labelKey: 'workspace.containerManagement.terminal.layout.options.rightOneLeftTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.rightOneLeftTwo.description',
  },
  'top-1-bottom-2': {
    icon: PanelTop,
    labelKey: 'workspace.containerManagement.terminal.layout.options.topOneBottomTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.topOneBottomTwo.description',
  },
  'bottom-1-top-2': {
    icon: PanelBottom,
    labelKey: 'workspace.containerManagement.terminal.layout.options.bottomOneTopTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.bottomOneTopTwo.description',
  },
};

export const TerminalLayoutSelector: React.FC<TerminalLayoutSelectorProps> = ({
  currentLayout,
  onLayoutChange,
}) => {
  const { t } = useI18n();

  const layoutOptions = useMemo(
    () =>
      (Object.keys(LAYOUT_CONFIG) as TerminalLayoutType[]).map((id) => {
        const config = LAYOUT_CONFIG[id];
        return {
          id,
          icon: config.icon,
          label: t(config.labelKey),
          description: t(config.descriptionKey),
        };
      }),
    [t],
  );

  const currentOption =
    layoutOptions.find((opt) => opt.id === currentLayout) || layoutOptions[0];
  const Icon = currentOption.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          data-testid="terminal-layout-selector"
          title={t('workspace.containerManagement.terminal.layout.changeTooltip')}
        >
          <Icon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {layoutOptions.map((option) => (
          <DropdownMenuItem
            key={option.id}
            onClick={() => onLayoutChange(option.id)}
            className={cn(
              'flex cursor-pointer items-start gap-3 p-3',
              currentLayout === option.id && 'bg-accent',
            )}
          >
            <div className="mt-0.5 rounded border p-1">
              <option.icon className="h-4 w-4" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium">{option.label}</span>
              <span className="text-xs text-muted-foreground">
                {option.description}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
