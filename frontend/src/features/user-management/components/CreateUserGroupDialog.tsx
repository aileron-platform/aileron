import React from 'react';
import { UsersRound } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';

export interface CreateUserGroupRequest {
  name: string;
  description: string;
}

interface CreateUserGroupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (request: CreateUserGroupRequest) => Promise<void>;
}

const initialForm: CreateUserGroupRequest = {
  name: '',
  description: '',
};

export const CreateUserGroupDialog: React.FC<CreateUserGroupDialogProps> = ({
  open,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [form, setForm] = React.useState<CreateUserGroupRequest>(initialForm);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setForm(initialForm);
    }
  }, [open]);

  const updateField = <Key extends keyof CreateUserGroupRequest>(
    key: Key,
    value: CreateUserGroupRequest[Key],
  ) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmit({
        name: form.name.trim(),
        description: form.description.trim(),
      });
      onOpenChange(false);
    } catch {
      // The page reports the localized API error.
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogHeading icon={UsersRound}>
            {t('userManagement.groups.createDialog.title')}
          </DialogHeading>
          <DialogDescription>{t('userManagement.groups.createDialog.description')}</DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="user-management-create-group-name">
              {t('userManagement.groups.createDialog.fields.name')}
            </Label>
            <Input
              id="user-management-create-group-name"
              value={form.name}
              placeholder={t('userManagement.groups.createDialog.placeholders.name')}
              onChange={event => updateField('name', event.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="user-management-create-group-description">
              {t('userManagement.groups.createDialog.fields.description')}
            </Label>
            <Textarea
              id="user-management-create-group-description"
              value={form.description}
              placeholder={t('userManagement.groups.createDialog.placeholders.description')}
              onChange={event => updateField('description', event.target.value)}
              rows={4}
            />
          </div>

          <div className="rounded-md border bg-muted/30 px-3 py-2">
            <div className="text-xs font-medium text-foreground">
              {t('userManagement.groups.createDialog.previewTitle')}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t('userManagement.groups.createDialog.previewDescription')}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('userManagement.groups.createDialog.actions.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {t('userManagement.groups.createDialog.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
