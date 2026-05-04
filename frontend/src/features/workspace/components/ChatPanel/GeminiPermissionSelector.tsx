import React from 'react';
import {
  Check,
  ClipboardList,
  Lock,
  LockOpen,
  Pencil,
  Sparkles,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';
import {
  GEMINI_SESSION_PERMISSION_MODES,
  type GeminiSessionPermissionMode,
} from './agentSessionTypes';

interface GeminiPermissionSelectorProps {
  value: GeminiSessionPermissionMode;
  onChange: (mode: GeminiSessionPermissionMode) => void;
  t: (key: string) => string;
  appliesOnNextHint?: boolean;
}

const modeIcons: Record<GeminiSessionPermissionMode, React.ReactNode> = {
  default: <Lock className="h-4 w-4" />,
  autoEdit: <Pencil className="h-4 w-4" />,
  yolo: <LockOpen className="h-4 w-4" />,
  plan: <ClipboardList className="h-4 w-4" />,
};

export const DEFAULT_GEMINI_SESSION_PERMISSION_CONFIG: GeminiSessionPermissionMode = 'yolo';

export const GeminiPermissionSelector: React.FC<GeminiPermissionSelectorProps> = ({
  value,
  onChange,
  t,
  appliesOnNextHint = false,
}) => {
  const isYolo = value === 'yolo';

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 shadow-sm transition-all',
              isYolo
                ? 'border border-amber-500/60 bg-amber-100 text-amber-950 hover:border-amber-500 hover:bg-amber-200/80'
                : 'border border-border bg-secondary/50 hover:border-primary/30 hover:bg-secondary',
            )}
            title={t('workspace.chat.input.geminiPermission.label')}
          >
            <Sparkles className={cn('h-3 w-3 flex-shrink-0', isYolo ? 'text-amber-700' : 'text-primary')} />
            <span className="whitespace-nowrap text-xs font-medium">
              {t(`workspace.chat.input.geminiPermission.${value}.label`)}
            </span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-96">
          <div className="px-3 py-2">
            <div className="text-sm font-medium">{t('workspace.chat.input.geminiPermission.label')}</div>
            <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {t('workspace.chat.input.geminiPermission.description')}
            </div>
          </div>
          {GEMINI_SESSION_PERMISSION_MODES.map((mode) => (
            <DropdownMenuItem
              key={mode}
              onClick={() => onChange(mode)}
              className="flex cursor-pointer items-start gap-2 py-2.5"
            >
              <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
                {value === mode ? <Check className="h-4 w-4 text-primary" /> : modeIcons[mode]}
              </div>
              <div className="flex flex-1 flex-col gap-0.5">
                <div className="text-sm font-medium">
                  {t(`workspace.chat.input.geminiPermission.${mode}.label`)}
                </div>
                <div className="text-xs leading-relaxed text-muted-foreground">
                  {t(`workspace.chat.input.geminiPermission.${mode}.description`)}
                </div>
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      {appliesOnNextHint && (
        <span className="text-xs text-muted-foreground">
          {t('workspace.chat.input.geminiPermission.applyOnNextHint')}
        </span>
      )}
    </div>
  );
};

export default GeminiPermissionSelector;
