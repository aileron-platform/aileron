import React from 'react';
import { Save, Settings } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceRegistryRootMetadataSavePayload } from '@/features/marketplace/model/marketplaceTypes';

export interface MarketplaceRootMetadata {
  name: string;
  maintainerName: string;
  maintainerEmail: string;
  description: string;
}

interface MarketplaceGeneralTabProps {
  metadata: MarketplaceRootMetadata;
  rootPath: string;
  isSaving: boolean;
  onMetadataChange: (metadata: MarketplaceRootMetadata) => void;
  onSave: () => void;
}

export const MarketplaceGeneralTab: React.FC<MarketplaceGeneralTabProps> = ({
  metadata,
  rootPath,
  isSaving,
  onMetadataChange,
  onSave,
}) => {
  const { t } = useI18n();
  const updateMetadata = (updates: Partial<MarketplaceRootMetadata>) => {
    onMetadataChange({ ...metadata, ...updates });
  };
  const savePayload: MarketplaceRegistryRootMetadataSavePayload = {
    name: metadata.name,
    owner: {
      name: metadata.maintainerName,
      email: metadata.maintainerEmail,
    },
    description: metadata.description,
  };
  const claudePreview = JSON.stringify({
    ...savePayload,
    plugins: [],
  }, null, 2);
  const codexPreview = JSON.stringify({
    name: savePayload.name,
    description: savePayload.description,
    plugins: [],
  }, null, 2);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          {t('marketplace.settings.general.title')}
        </CardTitle>
        <CardDescription>{t('marketplace.settings.general.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <section className="space-y-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{t('marketplace.settings.general.rootMetadataTitle')}</h3>
            <p className="text-xs text-muted-foreground">{t('marketplace.settings.general.rootMetadataDescription')}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <SettingsEditableField
              label={t('marketplace.settings.general.displayName')}
              value={metadata.name}
              onChange={value => updateMetadata({ name: value })}
            />
            <SettingsEditableField
              label={t('marketplace.settings.general.maintainerName')}
              value={metadata.maintainerName}
              onChange={value => updateMetadata({ maintainerName: value })}
            />
            <SettingsEditableField
              label={t('marketplace.settings.general.maintainerEmail')}
              value={metadata.maintainerEmail}
              onChange={value => updateMetadata({ maintainerEmail: value })}
            />
            <div className="md:col-span-2">
              <SettingsTextAreaField
                label={t('marketplace.settings.general.descriptionField')}
                value={metadata.description}
                onChange={value => updateMetadata({ description: value })}
              />
            </div>
            <div className="md:col-span-2">
              <SettingsReadOnlyField label={t('marketplace.settings.general.rootPath')} value={rootPath} monospace />
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={onSave} disabled={isSaving}>
              <Save className="mr-2 h-4 w-4" />
              {t('marketplace.common.actions.save')}
            </Button>
          </div>
        </section>

        <section className="space-y-4 border-t border-border pt-6">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{t('marketplace.settings.general.generatedPreviewTitle')}</h3>
            <p className="text-xs text-muted-foreground">{t('marketplace.settings.general.generatedPreviewDescription')}</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <SettingsJsonPreview
              title={t('marketplace.settings.general.previews.claude.title')}
              filePath="claude-code/.claude-plugin/marketplace.json"
              value={claudePreview}
            />
            <SettingsJsonPreview
              title={t('marketplace.settings.general.previews.codex.title')}
              filePath="codex/.agents/plugins/marketplace.json"
              value={codexPreview}
            />
          </div>
        </section>
      </CardContent>
    </Card>
  );
};

interface SettingsEditableFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const SettingsEditableField: React.FC<SettingsEditableFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input value={value} onChange={event => onChange(event.target.value)} />
  </div>
);

interface SettingsTextAreaFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const SettingsTextAreaField: React.FC<SettingsTextAreaFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Textarea value={value} rows={3} onChange={event => onChange(event.target.value)} />
  </div>
);

interface SettingsReadOnlyFieldProps {
  label: string;
  value: string;
  monospace?: boolean;
}

const SettingsReadOnlyField: React.FC<SettingsReadOnlyFieldProps> = ({ label, value, monospace = false }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input value={value} readOnly className={monospace ? 'bg-muted font-mono text-sm' : 'bg-muted'} />
  </div>
);

interface SettingsJsonPreviewProps {
  title: string;
  filePath: string;
  value: string;
}

const SettingsJsonPreview: React.FC<SettingsJsonPreviewProps> = ({ title, filePath, value }) => (
  <div className="space-y-3 rounded-md border border-border bg-muted/20 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">{filePath}</span>
    </div>
    <Textarea
      aria-label={filePath}
      value={value}
      readOnly
      className="min-h-[14rem] resize-none bg-background font-mono text-xs"
    />
  </div>
);
