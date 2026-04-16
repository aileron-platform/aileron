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

export type TerminalLayoutType =
  | 'single'
  | 'split-horizontal'
  | 'split-vertical'
  | 'quad'
  | 'left-1-right-2'
  | 'right-1-left-2'
  | 'top-1-bottom-2'
  | 'bottom-1-top-2';

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
    defaultLabel: string;
    defaultDescription: string;
  }
> = {
  single: {
    icon: Square,
    labelKey: 'workspace.containerManagement.terminal.layout.options.single.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.single.description',
    defaultLabel: '單一窗格',
    defaultDescription: '1 個窗格',
  },
  'split-horizontal': {
    icon: Columns,
    labelKey: 'workspace.containerManagement.terminal.layout.options.splitHorizontal.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.splitHorizontal.description',
    defaultLabel: '左右分割',
    defaultDescription: '左右 2 個窗格',
  },
  'split-vertical': {
    icon: Rows,
    labelKey: 'workspace.containerManagement.terminal.layout.options.splitVertical.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.splitVertical.description',
    defaultLabel: '上下分割',
    defaultDescription: '上下 2 個窗格',
  },
  quad: {
    icon: LayoutGrid,
    labelKey: 'workspace.containerManagement.terminal.layout.options.quad.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.quad.description',
    defaultLabel: '四分割',
    defaultDescription: '4 個等分窗格',
  },
  'left-1-right-2': {
    icon: PanelLeft,
    labelKey: 'workspace.containerManagement.terminal.layout.options.leftOneRightTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.leftOneRightTwo.description',
    defaultLabel: '左 1 右 2',
    defaultDescription: '左側 1 個，右側上下 2 個',
  },
  'right-1-left-2': {
    icon: PanelRight,
    labelKey: 'workspace.containerManagement.terminal.layout.options.rightOneLeftTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.rightOneLeftTwo.description',
    defaultLabel: '右 1 左 2',
    defaultDescription: '左側上下 2 個，右側 1 個',
  },
  'top-1-bottom-2': {
    icon: PanelTop,
    labelKey: 'workspace.containerManagement.terminal.layout.options.topOneBottomTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.topOneBottomTwo.description',
    defaultLabel: '上 1 下 2',
    defaultDescription: '上方 1 個，下方左右 2 個',
  },
  'bottom-1-top-2': {
    icon: PanelBottom,
    labelKey: 'workspace.containerManagement.terminal.layout.options.bottomOneTopTwo.label',
    descriptionKey: 'workspace.containerManagement.terminal.layout.options.bottomOneTopTwo.description',
    defaultLabel: '下 1 上 2',
    defaultDescription: '上方左右 2 個，下方 1 個',
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
          label: t(config.labelKey, { defaultValue: config.defaultLabel }),
          description: t(config.descriptionKey, {
            defaultValue: config.defaultDescription,
          }),
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
          title={t('workspace.containerManagement.terminal.layout.changeTooltip', {
            defaultValue: '切換佈局',
          })}
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
