import React from 'react';
import { PackagePlus } from 'lucide-react';
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceCreateRequest, MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';

interface CreatePackageDialogProps {
  open: boolean;
  errorKey: string | null;
  isSubmitting: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (request: MarketplaceCreateRequest) => Promise<void>;
}

const PROVIDERS: MarketplaceProvider[] = ['claude-code', 'codex'];

const initialForm: MarketplaceCreateRequest = {
  provider: 'claude-code',
  packageId: '',
  displayName: '',
  description: '',
};

export const CreatePackageDialog: React.FC<CreatePackageDialogProps> = ({
  open,
  errorKey,
  isSubmitting,
  onOpenChange,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [form, setForm] = React.useState<MarketplaceCreateRequest>(initialForm);
  const providerLabelId = React.useId();

  React.useEffect(() => {
    if (!open) {
      setForm(initialForm);
    }
  }, [open]);

  const updateField = <Key extends keyof MarketplaceCreateRequest>(
    key: Key,
    value: MarketplaceCreateRequest[Key],
  ) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit({
      provider: form.provider,
      packageId: form.packageId.trim(),
      displayName: form.displayName.trim(),
      description: form.description?.trim() || undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogHeading icon={PackagePlus}>
            {t('marketplace.createPackage.title')}
          </DialogHeading>
          <DialogDescription>{t('marketplace.createPackage.description')}</DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label id={providerLabelId}>{t('marketplace.createPackage.fields.provider')}</Label>
            <Select
              value={form.provider}
              onValueChange={value => updateField('provider', value as MarketplaceProvider)}
              disabled={isSubmitting}
            >
              <SelectTrigger aria-labelledby={providerLabelId}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map(provider => (
                  <SelectItem key={provider} value={provider}>
                    {t(`marketplace.providers.${provider}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="marketplace-create-package-id">
              {t('marketplace.createPackage.fields.packageId')}
            </Label>
            <Input
              id="marketplace-create-package-id"
              value={form.packageId}
              placeholder={t('marketplace.createPackage.placeholders.packageId')}
              onChange={event => updateField('packageId', event.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="marketplace-create-display-name">
              {t('marketplace.createPackage.fields.displayName')}
            </Label>
            <Input
              id="marketplace-create-display-name"
              value={form.displayName}
              placeholder={t('marketplace.createPackage.placeholders.displayName')}
              onChange={event => updateField('displayName', event.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="marketplace-create-description">
              {t('marketplace.createPackage.fields.description')}
            </Label>
            <Textarea
              id="marketplace-create-description"
              value={form.description}
              placeholder={t('marketplace.createPackage.placeholders.description')}
              onChange={event => updateField('description', event.target.value)}
              disabled={isSubmitting}
              rows={4}
            />
          </div>

          {errorKey ? (
            <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {t(errorKey)}
            </div>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              {t('marketplace.createPackage.actions.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? t('marketplace.createPackage.actions.creating')
                : t('marketplace.createPackage.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
