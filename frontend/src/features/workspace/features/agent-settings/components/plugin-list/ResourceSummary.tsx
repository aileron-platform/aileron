import React from 'react';
import { ExternalLink } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';

interface ResourceSummaryProps {
  label: string;
  count: number;
  href?: string;
  linkLabel?: string;
}

export const ResourceSummary: React.FC<ResourceSummaryProps> = ({
  label,
  count,
  href,
  linkLabel,
}) => {
  const content = (
    <>
      <span className="flex min-w-0 items-center gap-1 text-muted-foreground">
        <span className="truncate">{label}</span>
        {href ? <ExternalLink className="h-3 w-3 shrink-0" /> : null}
      </span>
      <Badge variant="secondary">{count}</Badge>
    </>
  );

  return href ? (
    <a
      href={href}
      aria-label={linkLabel}
      className="flex items-center justify-between rounded border border-border p-3 text-sm transition-colors hover:bg-muted/50"
    >
      {content}
    </a>
  ) : (
    <div className="flex items-center justify-between rounded border border-border p-3 text-sm">
      {content}
    </div>
  );
};
