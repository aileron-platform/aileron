import React from 'react';

interface PluginEmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  actions?: React.ReactNode;
}

export const PluginEmptyState: React.FC<PluginEmptyStateProps> = ({
  icon,
  title,
  description,
  actions,
}) => (
  <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-6 text-center">
    <div className="text-muted-foreground">{icon}</div>
    <div className="space-y-1">
      <p className="text-base font-medium">{title}</p>
      <p className="max-w-md text-sm text-muted-foreground">{description}</p>
    </div>
    {actions}
  </div>
);
