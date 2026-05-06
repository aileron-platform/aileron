import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

interface PluginStatusPillProps {
  enabled: boolean;
  enabledLabel: string;
  disabledLabel: string;
}

export const PluginStatusPill: React.FC<PluginStatusPillProps> = ({
  enabled,
  enabledLabel,
  disabledLabel,
}) => (
  <span
    className={cn(
      'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium',
      enabled
        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
        : 'border-border bg-muted text-muted-foreground',
    )}
  >
    {enabled ? <CheckCircle2 className="h-3.5 w-3.5" /> : <span className="h-2 w-2 rounded-full bg-muted-foreground/60" />}
    {enabled ? enabledLabel : disabledLabel}
  </span>
);
