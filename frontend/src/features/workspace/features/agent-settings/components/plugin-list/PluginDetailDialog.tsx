import React from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';

interface PluginDetailDialogProps {
  open: boolean;
  title: string;
  description?: string;
  icon: LucideIcon;
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
        <div className="min-w-0 space-y-1">
          <DialogHeading icon={icon} className="truncate">
            {title}
          </DialogHeading>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </div>
      </DialogHeader>
      {children}
    </DialogContent>
  </Dialog>
);
