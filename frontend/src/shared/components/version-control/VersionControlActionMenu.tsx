import React from 'react';
import { ArrowDown, ArrowUp, MoreHorizontal, RefreshCw, Settings, SlidersHorizontal } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

type VersionControlActionId = 'refresh' | 'fetch' | 'pull' | 'push' | 'remoteSettings' | 'lfs';

export interface VersionControlActionMenuItem {
  id: VersionControlActionId;
  onClick: () => void;
  disabled?: boolean;
  disabledReasonKey?: string;
  labelKey?: string;
}

export interface VersionControlActionMenuExtensionItem {
  key: string;
  labelKey: string;
  onClick: () => void;
  disabled?: boolean;
  icon?: React.ReactNode;
}

interface VersionControlActionMenuProps {
  actions: VersionControlActionMenuItem[];
  extensionActions?: VersionControlActionMenuExtensionItem[];
  disabled?: boolean;
  className?: string;
}

const actionIcons: Record<VersionControlActionId, React.ReactNode> = {
  refresh: <RefreshCw className="h-3 w-3" />,
  fetch: <RefreshCw className="h-3 w-3" />,
  pull: <ArrowDown className="h-3 w-3" />,
  push: <ArrowUp className="h-3 w-3" />,
  remoteSettings: <Settings className="h-3 w-3" />,
  lfs: <SlidersHorizontal className="h-3 w-3" />,
};

const actionGroups: readonly (readonly VersionControlActionId[])[] = [
  ['refresh', 'fetch', 'pull', 'push'],
  ['remoteSettings', 'lfs'],
];

export const VersionControlActionMenu: React.FC<VersionControlActionMenuProps> = ({
  actions,
  extensionActions = [],
  disabled = false,
  className,
}) => {
  const { t } = useI18n();
  const byId = new Map(actions.map(action => [action.id, action]));
  const visibleGroups = actionGroups
    .map(group => group.map(id => byId.get(id)).filter(Boolean) as VersionControlActionMenuItem[])
    .filter(group => group.length > 0);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'rounded p-1 transition-colors hover:bg-muted/30 disabled:opacity-50',
            className,
          )}
          aria-label={t('shared.versionControl.actions.menu.label')}
          title={t('shared.versionControl.actions.menu.label')}
          disabled={disabled}
        >
          <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" collisionPadding={8} className="w-52">
        {visibleGroups.map((group, groupIndex) => (
          <React.Fragment key={group.map(action => action.id).join(':')}>
            {groupIndex > 0 && <DropdownMenuSeparator />}
            {group.map((action) => (
              <DropdownMenuItem
                key={action.id}
                disabled={action.disabled}
                title={action.disabledReasonKey ? t(action.disabledReasonKey) : undefined}
                onSelect={action.onClick}
              >
                {actionIcons[action.id]}
                {t(action.labelKey ?? `shared.versionControl.actions.${action.id}.label`)}
              </DropdownMenuItem>
            ))}
          </React.Fragment>
        ))}
        {extensionActions.length > 0 && <DropdownMenuSeparator />}
        {extensionActions.map(action => (
          <DropdownMenuItem
            key={action.key}
            disabled={action.disabled}
            onSelect={action.onClick}
          >
            {action.icon}
            {t(action.labelKey)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
