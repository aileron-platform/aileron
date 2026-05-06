import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';

interface PluginDetailDialogProps {
  open: boolean;
  title: string;
  description?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  onOpenChange: (open: boolean) => void;
}

export const PluginDetailDialog: React.FC<PluginDetailDialogProps> = ({
  open,
  title,
  description,
  icon,
  children,
  onOpenChange,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col overflow-hidden p-0">
      <DialogHeader className="px-6 pt-6">
        <div className="flex min-w-0 items-start gap-3">
          {icon ? (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground">
              {icon}
            </div>
          ) : null}
          <div className="min-w-0 space-y-1">
            <DialogTitle className="truncate">{title}</DialogTitle>
            {description ? <DialogDescription>{description}</DialogDescription> : null}
          </div>
        </div>
      </DialogHeader>
      {children}
    </DialogContent>
  </Dialog>
);
