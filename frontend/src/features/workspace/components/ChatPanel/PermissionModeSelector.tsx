import React from 'react';
import { FastForward, Check } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

export type PermissionMode = 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions' | 'dontAsk' | 'auto';

interface PermissionModeSelectorProps {
  value: PermissionMode;
  onChange: (mode: PermissionMode) => void;
  t: (key: string) => string;
}

const PERMISSION_MODES: PermissionMode[] = ['default', 'acceptEdits', 'plan', 'bypassPermissions', 'dontAsk', 'auto'];

export const PermissionModeSelector: React.FC<PermissionModeSelectorProps> = ({
  value,
  onChange,
  t,
}) => {
  const getModeLabel = (mode: PermissionMode): string => {
    switch (mode) {
      case 'default':
        return 'Default';
      case 'acceptEdits':
        return 'Accept Edits';
      case 'plan':
        return 'Plan';
      case 'bypassPermissions':
        return 'Bypass Permissions';
      case 'dontAsk':
        return "Don't Ask";
      case 'auto':
        return 'Auto';
    }
  };

  const getModeDescription = (mode: PermissionMode): string => {
    return t(`workspace.chat.input.permissionMode.${mode}`);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-secondary/50 px-2.5 hover:bg-secondary hover:border-primary/30 transition-all shadow-sm"
          title={t('workspace.chat.input.permissionMode.label')}
        >
          <FastForward className="h-3 w-3 flex-shrink-0 text-primary" />
          <span className="text-xs font-medium whitespace-nowrap">
            {getModeLabel(value)}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        {PERMISSION_MODES.map((mode) => (
          <DropdownMenuItem
            key={mode}
            onClick={() => onChange(mode)}
            className="flex items-start gap-2 py-2.5 cursor-pointer"
          >
            <div className="flex h-5 w-5 items-center justify-center flex-shrink-0">
              {value === mode && <Check className="h-4 w-4 text-primary" />}
            </div>
            <div className="flex flex-col gap-0.5 flex-1">
              <div className="text-sm font-medium">{getModeLabel(mode)}</div>
              <div className="text-xs text-muted-foreground leading-relaxed">
                {getModeDescription(mode)}
              </div>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default PermissionModeSelector;

