import type { LucideIcon } from 'lucide-react';

interface AutomationFormSectionHeadingProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function AutomationFormSectionHeading({
  icon: Icon,
  title,
  description,
}: AutomationFormSectionHeadingProps) {
  return (
    <div className="flex items-start gap-3 border-b border-border/50 pb-4">
      <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 space-y-0.5">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export const automationFormSectionClassName =
  'space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-sm';
