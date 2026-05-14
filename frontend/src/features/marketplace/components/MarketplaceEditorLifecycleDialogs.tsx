import React from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
} from '@/shared/components/ui/alert-dialog';
import { AlertDialogHeading } from '@/shared/components/ui/dialog-heading';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceEditorLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
  onDiscard: () => void;
}

export const MarketplaceEditorLeaveDialog: React.FC<MarketplaceEditorLeaveDialogProps> = ({
  open,
  onOpenChange,
  onSave,
  onDiscard,
}) => {
  const { t } = useI18n();

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogHeading icon={AlertTriangle}>
            {t('marketplace.editor.unsaved.title')}
          </AlertDialogHeading>
          <AlertDialogDescription>{t('marketplace.editor.unsaved.description')}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </AlertDialogCancel>
          <AlertDialogAction className="border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground" onClick={onDiscard}>
            {t('marketplace.editor.actions.discard')}
          </AlertDialogAction>
          <AlertDialogAction onClick={onSave}>
            {t('marketplace.editor.actions.save')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
