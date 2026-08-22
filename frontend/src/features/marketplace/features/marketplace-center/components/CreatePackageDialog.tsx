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
import { listPackageFormatOptions } from '@/features/marketplace/api/marketplaceApi';
import type {
  MarketplaceCreateRequest,
  MarketplacePackageFormat,
  MarketplacePackageFormatOption,
  MarketplaceTargetClient,
} from '@/features/marketplace/model/marketplaceTypes';

interface CreatePackageDialogProps {
  open: boolean;
  errorKey: string | null;
  isSubmitting: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (request: MarketplaceCreateRequest) => Promise<void>;
}

const initialForm: MarketplaceCreateRequest = {
  packageFormat: 'agent-plugin/1.0.0',
  targetClients: [],
  packageId: '',
  displayName: '',
  version: '1.0.0',
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
  const [formatOptions, setFormatOptions] = React.useState<MarketplacePackageFormatOption[]>([]);
  const packageFormatLabelId = React.useId();
  const targetClientLabelId = React.useId();

  React.useEffect(() => {
    if (!open) {
      setForm(initialForm);
      setFormatOptions([]);
      return;
    }
    let active = true;
    void listPackageFormatOptions().then(options => {
      if (!active) return;
      setFormatOptions(options);
      const first = options[0];
      if (first) {
        setForm(current => ({
          ...current,
          packageFormat: first.packageFormat,
          targetClients: first.targetClients.slice(0, 1),
          version: first.defaultVersion,
        }));
      }
    });
    return () => { active = false; };
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
      packageFormat: form.packageFormat,
      targetClients: form.targetClients,
      packageId: form.packageId.trim(),
      displayName: form.displayName.trim(),
      version: form.version.trim(),
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
            <Label id={packageFormatLabelId}>{t('marketplace.createPackage.fields.packageFormat')}</Label>
            <Select
              value={form.packageFormat}
              onValueChange={value => {
                const option = formatOptions.find(item => item.packageFormat === value);
                if (!option) return;
                setForm(current => ({
                  ...current,
                  packageFormat: value as MarketplacePackageFormat,
                  targetClients: option.targetClients.slice(0, 1),
                  version: option.defaultVersion,
                }));
              }}
              disabled={isSubmitting || formatOptions.length === 0}
            >
              <SelectTrigger aria-labelledby={packageFormatLabelId}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {formatOptions.map(option => (
                  <SelectItem key={option.packageFormat} value={option.packageFormat}>
                    {option.packageFormat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label id={targetClientLabelId}>{t('marketplace.createPackage.fields.targetClient')}</Label>
            <Select
              value={form.targetClients[0] ?? ''}
              onValueChange={value => updateField('targetClients', [value as MarketplaceTargetClient])}
              disabled={isSubmitting}
            >
              <SelectTrigger aria-labelledby={targetClientLabelId}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(formatOptions.find(option => option.packageFormat === form.packageFormat)?.targetClients ?? []).map(targetClient => (
                  <SelectItem key={targetClient} value={targetClient}>
                    {t(`marketplace.targetClients.${targetClient}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="marketplace-create-version">
              {t('marketplace.createPackage.fields.version')}
            </Label>
            <Input
              id="marketplace-create-version"
              value={form.version}
              onChange={event => updateField('version', event.target.value)}
              disabled={isSubmitting}
              required
            />
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
