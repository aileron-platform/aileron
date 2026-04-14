import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';

interface SectionCardProps {
  title: React.ReactNode;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

const SectionCard: React.FC<SectionCardProps> = ({ title, description, action, children, className }) => {
  const isTabsHeader = typeof title !== 'string';

  return (
    <Card className={`border-border/80 shadow-sm p-0 m-0 ${className || ''}`}>
      <CardHeader className={`flex flex-row items-start justify-between gap-4 ${isTabsHeader ? 'border-b border-border p-0 overflow-hidden' : 'p-6 pb-4'}`}>
        <div className="min-w-0">
          {typeof title === 'string' ? (
            <CardTitle className="text-base font-semibold text-foreground">{title}</CardTitle>
          ) : (
            <div>{title}</div>
          )}
          {description ? (
            <CardDescription className="text-sm text-muted-foreground mt-1">{description}</CardDescription>
          ) : null}
        </div>
        {action ? <div>{action}</div> : null}
      </CardHeader>
      <CardContent className="!p-0 !m-0 flex-1">{children}</CardContent>
    </Card>
  );
};

export default SectionCard;

