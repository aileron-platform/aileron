import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';

export const ResourceBadge: React.FC<{ label: string; icon: LucideIcon }> = ({
  label,
  icon: Icon,
}) => (
  <Badge variant="outline" className="gap-1.5 text-xs">
    <Icon className="h-3.5 w-3.5" />
    {label}
  </Badge>
);
