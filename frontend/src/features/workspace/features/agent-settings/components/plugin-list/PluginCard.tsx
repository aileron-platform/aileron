import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

interface PluginCardProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  description?: React.ReactNode;
  statusBadge?: React.ReactNode;
  warningBadge?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  onTitleClick?: () => void;
}

export const PluginCard: React.FC<PluginCardProps> = ({
  title,
  subtitle,
  description,
  statusBadge,
  warningBadge,
  actions,
  children,
  onTitleClick,
}) => (
  <Card className="flex h-full flex-col">
    <CardHeader className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <CardTitle className="truncate text-base">
            {onTitleClick ? (
              <button
                type="button"
                className="max-w-full truncate text-left hover:text-primary hover:underline"
                onClick={onTitleClick}
              >
                {title}
              </button>
            ) : title}
          </CardTitle>
          {subtitle ? <p className="text-xs text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {warningBadge}
          {statusBadge}
          {actions}
        </div>
      </div>
      {description ? <p className="line-clamp-3 text-sm text-muted-foreground">{description}</p> : null}
    </CardHeader>
    {children ? <CardContent className="mt-auto space-y-3 text-sm">{children}</CardContent> : null}
  </Card>
);
