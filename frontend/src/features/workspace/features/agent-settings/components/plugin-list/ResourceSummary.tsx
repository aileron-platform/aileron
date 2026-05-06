import React from 'react';
import { Badge } from '@/shared/components/ui/badge';

export const ResourceSummary: React.FC<{ label: string; count: number }> = ({
  label,
  count,
}) => (
  <div className="flex items-center justify-between rounded border border-border p-3 text-sm">
    <span className="text-muted-foreground">{label}</span>
    <Badge variant="secondary">{count}</Badge>
  </div>
);
