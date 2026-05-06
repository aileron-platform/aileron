import React from 'react';
import { Button } from '@/shared/components/ui/button';

export type PluginDisplayMode = 'enabled' | 'all';

interface PluginDisplayModeToggleProps {
  value: PluginDisplayMode;
  labels: Record<PluginDisplayMode, string>;
  onChange: (value: PluginDisplayMode) => void;
}

export const PluginDisplayModeToggle: React.FC<PluginDisplayModeToggleProps> = ({
  value,
  labels,
  onChange,
}) => (
  <div className="flex flex-wrap items-center gap-2">
    {(['enabled', 'all'] as const).map((mode) => (
      <Button
        key={mode}
        type="button"
        variant={value === mode ? 'default' : 'outline'}
        size="sm"
        className="h-8 px-3 text-xs"
        onClick={() => onChange(mode)}
      >
        {labels[mode]}
      </Button>
    ))}
  </div>
);
