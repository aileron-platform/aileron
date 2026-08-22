import React from 'react';
import { Info } from 'lucide-react';

import { CodeTextEditor } from '@/shared/components/file-workbench/viewer-entry';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { Input } from '@/shared/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail, MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';
import {
  createMarketplaceRequiredDraftFromDetail,
  getStringField,
  isJsonObject,
  mergeMarketplaceListingJson,
  mergeMarketplaceManifestJson,
  parseMarketplaceJsonObject,
  stringifyMarketplaceJson,
  type MarketplaceRequiredDraft,
  type MarketplaceRequiredDraftFallbacks,
} from './marketplaceEditorRequiredDraft';

type MarketplaceJsonDocument = 'listing' | 'manifest';

type MarketplaceRequiredEditorTab = 'form' | 'json';

export interface MarketplaceEditorBasicSectionProps {
  mode: 'create' | 'edit';
  targetClient: MarketplaceTargetClient;
  packageId: string;
  displayName: string;
  description: string;
  detail: MarketplacePackageDetail | null;
  onPackageIdChange: (value: string) => void;
  onDisplayNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onRequiredDraftChange: (draft: MarketplaceRequiredDraft) => void;
  onReadmeChange: (content: string) => void;
  onDirty: () => void;
  showReadmeSection?: boolean;
}

export const MarketplaceEditorBasicSection: React.FC<MarketplaceEditorBasicSectionProps> = ({
  mode,
  targetClient,
  packageId,
  displayName,
  description,
  detail,
  onPackageIdChange,
  onDisplayNameChange,
  onDescriptionChange,
  onRequiredDraftChange,
  onReadmeChange,
  onDirty,
  showReadmeSection = true,
}) => {
  const { t } = useI18n();
  const requiredDraftFallbacks = React.useMemo<MarketplaceRequiredDraftFallbacks>(() => ({
    packageName: t('marketplace.editor.defaults.packageName'),
    codexMarketplaceName: t('marketplace.editor.defaults.codexMarketplaceName'),
    claudeMarketplaceName: t('marketplace.editor.defaults.claudeMarketplaceName'),
    ownerName: t('marketplace.editor.defaults.ownerName'),
    description: t('marketplace.editor.defaults.description'),
  }), [t]);
  const [draft, setDraft] = React.useState<MarketplaceRequiredDraft>(() => (
    createMarketplaceRequiredDraftFromDetail(targetClient, detail, packageId, displayName, description, requiredDraftFallbacks)
  ));
  const [readmeDraft, setReadmeDraft] = React.useState('');
  const detailDraftIdentity = detail ? `${targetClient}:${detail.revision ?? ''}` : null;
  const initializedDetailDraftIdentityRef = React.useRef(detailDraftIdentity);

  React.useEffect(() => {
    if (!detail) return;
    if (initializedDetailDraftIdentityRef.current === detailDraftIdentity) return;

    initializedDetailDraftIdentityRef.current = detailDraftIdentity;
    setDraft(createMarketplaceRequiredDraftFromDetail(targetClient, detail, packageId, displayName, description, requiredDraftFallbacks));
  }, [description, detail, detailDraftIdentity, displayName, packageId, targetClient, requiredDraftFallbacks]);

  React.useEffect(() => {
    onRequiredDraftChange(draft);
  }, [draft, onRequiredDraftChange]);

  const resolvedPackageId = draft.packageName || packageId || t('marketplace.editor.fields.packageIdPreviewFallback');
  const manifestFile = {
    'claude-code': '.claude-plugin/plugin.json',
    codex: '.codex-plugin/plugin.json',
  }[targetClient];
  const registryPath = `${targetClient}/plugins/${resolvedPackageId}`;

  const updateRequiredDraft = (updates: Partial<MarketplaceRequiredDraft>) => {
    setDraft(prev => {
      const next = { ...prev, ...updates };
      return {
        ...next,
        listingJson: mergeMarketplaceListingJson(targetClient, prev.listingJson, next),
        manifestJson: mergeMarketplaceManifestJson(targetClient, prev.manifestJson, next),
        listingJsonError: null,
        manifestJsonError: null,
      };
    });
    onDirty();
  };

  const updatePackageName = (value: string) => {
    onPackageIdChange(value);
    onDisplayNameChange(value);
    updateRequiredDraft({
      packageName: value,
      manifestName: value,
      sourcePath: `./plugins/${value || requiredDraftFallbacks.packageName}`,
    });
  };

  const updateManifestDescription = (value: string) => {
    onDescriptionChange(value);
    updateRequiredDraft({ manifestDescription: value });
  };

  const updateJsonDraft = (document: MarketplaceJsonDocument, value: string) => {
    const parsed = parseMarketplaceJsonObject(value);
    const errorKey = parsed ? null : t('marketplace.editor.required.json.parseError');

    if (!parsed) {
      setDraft(prev => ({
        ...prev,
        [document === 'listing' ? 'listingJson' : 'manifestJson']: value,
        [document === 'listing' ? 'listingJsonError' : 'manifestJsonError']: errorKey,
      }));
      onDirty();
      return;
    }

    setDraft(prev => {
      if (document === 'listing') {
        const source = parsed.source;
        const sourcePath = typeof source === 'string'
          ? source
          : isJsonObject(source)
            ? getStringField(source.path, prev.sourcePath)
            : prev.sourcePath;
        const policy = isJsonObject(parsed.policy) ? parsed.policy : {};
        const packageName = getStringField(parsed.name, prev.packageName);
        const next = {
          ...prev,
          packageName,
          manifestName: packageName,
          sourcePath,
          codexInstallationPolicy: getStringField(policy.installation, prev.codexInstallationPolicy),
          codexAuthenticationPolicy: getStringField(policy.authentication, prev.codexAuthenticationPolicy),
          category: getStringField(parsed.category, prev.category),
          listingJson: '',
          listingJsonError: null,
        };

        if (packageName !== prev.packageName) {
          onPackageIdChange(packageName);
          onDisplayNameChange(packageName);
        }

        return {
          ...next,
          listingJson: mergeMarketplaceListingJson(targetClient, stringifyMarketplaceJson(parsed), next),
        };
      }

      const manifestName = getStringField(parsed.name, prev.manifestName);
      const manifestDescription = getStringField(parsed.description, prev.manifestDescription);
      if (manifestName !== prev.manifestName) {
        onPackageIdChange(manifestName);
        onDisplayNameChange(manifestName);
      }
      if (targetClient === 'codex' && manifestDescription !== prev.manifestDescription) {
        onDescriptionChange(manifestDescription);
      }

      return {
        ...prev,
        packageName: manifestName,
        manifestName,
        manifestVersion: getStringField(parsed.version, prev.manifestVersion),
        manifestDescription,
        manifestJson: stringifyMarketplaceJson(parsed),
        manifestJsonError: null,
      };
    });
    onDirty();
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.targetClient')}
            </label>
            <Select value={targetClient} disabled>
              <SelectTrigger className="cursor-not-allowed bg-muted">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="claude-code">{t('marketplace.targetClients.claude-code')}</SelectItem>
                <SelectItem value="codex">{t('marketplace.targetClients.codex')}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t('marketplace.editor.fields.targetClientHint')}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.packageId')}
            </label>
            <Input
              value={draft.packageName}
              placeholder={t('marketplace.editor.fields.packageIdPlaceholder')}
              readOnly={mode === 'edit'}
              disabled={mode === 'edit'}
              className={mode === 'edit' ? 'cursor-not-allowed bg-muted' : ''}
              onChange={event => updatePackageName(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t('marketplace.editor.fields.packageIdHint')}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.displayName')}
            </label>
            <Input
              value={displayName}
              placeholder={t('marketplace.editor.fields.displayNamePlaceholder')}
              onChange={event => onDisplayNameChange(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">
              {t('marketplace.editor.fields.registryPath')}
            </label>
            <Input
              value={registryPath}
              readOnly
              className="cursor-not-allowed bg-muted font-mono text-sm"
            />
          </div>
        </div>

        <MarketplaceEditorFormSection
          title={t('marketplace.editor.requiredFields.title')}
          description={t('marketplace.editor.requiredFields.description')}
        >
          <MarketplaceFormJsonTabs
            formLabel={t('marketplace.editor.requiredTabs.form')}
            jsonLabel={t('marketplace.editor.requiredTabs.json')}
            form={(
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <MarketplaceEditorReadonlyField
                  label={t('marketplace.editor.packageSections.fields.marketplaceName')}
                  value={draft.marketplaceName}
                  hint={t('marketplace.editor.packageSections.fields.rootMetadataHint')}
                />
                {targetClient === 'claude-code' ? (
                  <MarketplaceEditorReadonlyField
                    label={t('marketplace.editor.packageSections.fields.ownerName')}
                    value={draft.ownerName}
                    hint={t('marketplace.editor.packageSections.fields.rootMetadataHint')}
                  />
                ) : null}
                <MarketplaceEditorEditableField
                  label={t('marketplace.editor.packageSections.fields.packageName')}
                  value={draft.packageName}
                  onChange={updatePackageName}
                />
                <MarketplaceEditorEditableField
                  label={t('marketplace.editor.packageSections.fields.source')}
                  value={draft.sourcePath}
                  onChange={value => updateRequiredDraft({ sourcePath: value })}
                />
                {targetClient === 'codex' ? (
                  <>
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.policyInstallation')}
                      value={draft.codexInstallationPolicy}
                      onChange={value => updateRequiredDraft({ codexInstallationPolicy: value })}
                    />
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.policyAuthentication')}
                      value={draft.codexAuthenticationPolicy}
                      onChange={value => updateRequiredDraft({ codexAuthenticationPolicy: value })}
                    />
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.category')}
                      value={draft.category}
                      onChange={value => updateRequiredDraft({ category: value })}
                    />
                  </>
                ) : null}
                {targetClient !== 'claude-code' ? (
                  <>
                    <MarketplaceEditorEditableField
                      label={t('marketplace.editor.packageSections.fields.version')}
                      value={draft.manifestVersion}
                      onChange={value => updateRequiredDraft({ manifestVersion: value })}
                    />
                    {targetClient === 'codex' ? (
                      <div className="md:col-span-2">
                        <MarketplaceEditorTextAreaField
                          label={t('marketplace.editor.packageSections.fields.description')}
                          value={draft.manifestDescription}
                          rows={3}
                          onChange={updateManifestDescription}
                        />
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            )}
            json={(
              <MarketplaceRequiredJsonDocuments
                marketplaceFilePath={targetClient === 'codex' ? 'codex/.agents/plugins/marketplace.json' : 'claude-code/.claude-plugin/marketplace.json'}
                manifestFilePath={`${registryPath}/${manifestFile}`}
                listingJson={draft.listingJson}
                listingJsonError={draft.listingJsonError}
                manifestJson={draft.manifestJson}
                manifestJsonError={draft.manifestJsonError}
                onListingJsonChange={value => updateJsonDraft('listing', value)}
                onManifestJsonChange={value => updateJsonDraft('manifest', value)}
              />
            )}
          />
        </MarketplaceEditorFormSection>

        {showReadmeSection ? (
          <MarketplaceEditorFormSection
            title={t('marketplace.editor.tabs.readme')}
            description={t('marketplace.editor.packageSections.readme.description')}
            fileName="README.md"
          >
            <MarkdownEditor
              value={readmeDraft}
              onChange={(value) => {
                setReadmeDraft(value);
                onReadmeChange(value);
                onDirty();
              }}
              placeholder={t('marketplace.editor.packageSections.readme.placeholder')}
              className="min-h-[22rem]"
              textareaClassName="min-h-[16rem]"
            />
          </MarketplaceEditorFormSection>
        ) : null}
      </div>
    </div>
  );
};

interface MarketplaceEditorFormSectionProps {
  title: string;
  description: string;
  fileName?: string;
  children: React.ReactNode;
}

const MarketplaceEditorFormSection: React.FC<MarketplaceEditorFormSectionProps> = ({
  title,
  description,
  fileName,
  children,
}) => (
  <section className="space-y-4 border-t border-border pt-6 first:border-t-0 first:pt-0">
    <div className="flex items-center justify-between gap-3">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {fileName ? (
        <div className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
          {fileName}
        </div>
      ) : null}
    </div>
    {children}
  </section>
);

interface MarketplaceJsonDraftEditorProps {
  title: string;
  filePath: string;
  badgeSuffix?: string;
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}

interface MarketplaceRequiredJsonDocumentsProps {
  marketplaceFilePath: string;
  manifestFilePath: string;
  listingJson: string;
  listingJsonError: string | null;
  manifestJson: string;
  manifestJsonError: string | null;
  onListingJsonChange: (value: string) => void;
  onManifestJsonChange: (value: string) => void;
}

interface MarketplaceFormJsonTabsProps {
  formLabel: string;
  jsonLabel: string;
  form: React.ReactNode;
  json: React.ReactNode;
}

const MarketplaceFormJsonTabs: React.FC<MarketplaceFormJsonTabsProps> = ({
  formLabel,
  jsonLabel,
  form,
  json,
}) => {
  const [activeTab, setActiveTab] = React.useState<MarketplaceRequiredEditorTab>('form');

  return (
    <Tabs value={activeTab} onValueChange={value => setActiveTab(value as MarketplaceRequiredEditorTab)} className="space-y-6">
      <TabsList className="h-9 justify-start">
        <TabsTrigger value="form" className="h-7 px-3 text-xs">
          {formLabel}
        </TabsTrigger>
        <TabsTrigger value="json" className="h-7 px-3 text-xs">
          {jsonLabel}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="form" className="!m-0 pt-2">
        {form}
      </TabsContent>
      <TabsContent value="json" className="!m-0 pt-2">
        {json}
      </TabsContent>
    </Tabs>
  );
};

const MarketplaceRequiredJsonDocuments: React.FC<MarketplaceRequiredJsonDocumentsProps> = ({
  marketplaceFilePath,
  manifestFilePath,
  listingJson,
  listingJsonError,
  manifestJson,
  manifestJsonError,
  onListingJsonChange,
  onManifestJsonChange,
}) => {
  const [activeDocument, setActiveDocument] = React.useState<MarketplaceJsonDocument>(
    'listing',
  );
  const { t } = useI18n();
  const listingTitle = t('marketplace.editor.required.json.tabs.entry');
  const manifestTitle = t('marketplace.editor.required.json.tabs.plugin');

  return (
    <Tabs value={activeDocument} onValueChange={value => setActiveDocument(value as MarketplaceJsonDocument)} className="space-y-5">
      <TabsList className="h-10 justify-start gap-2 p-1">
        <MarketplaceJsonDocumentTab
          value="listing"
          title={listingTitle}
          infoLabel={t('marketplace.editor.required.json.infoLabel', { document: listingTitle })}
          info={t('marketplace.editor.required.json.popovers.entry')}
        />
        <MarketplaceJsonDocumentTab
          value="manifest"
          title={manifestTitle}
          infoLabel={t('marketplace.editor.required.json.infoLabel', { document: manifestTitle })}
          info={t('marketplace.editor.required.json.popovers.plugin')}
        />
      </TabsList>
      <TabsContent value="listing" className="!m-0 pt-2">
        <MarketplaceJsonDraftEditor
          title={listingTitle}
          filePath={marketplaceFilePath}
          badgeSuffix={t('marketplace.editor.required.json.fileBadge.thisEntryOnly')}
          value={listingJson}
          error={listingJsonError}
          onChange={onListingJsonChange}
        />
      </TabsContent>
      <TabsContent value="manifest" className="!m-0 pt-2">
        <MarketplaceJsonDraftEditor
          title={manifestTitle}
          filePath={manifestFilePath}
          value={manifestJson}
          error={manifestJsonError}
          onChange={onManifestJsonChange}
        />
      </TabsContent>
    </Tabs>
  );
};

interface MarketplaceJsonDocumentTabProps {
  value: MarketplaceJsonDocument;
  title: string;
  infoLabel: string;
  info: string;
}

const MarketplaceJsonDocumentTab: React.FC<MarketplaceJsonDocumentTabProps> = ({
  value,
  title,
  infoLabel,
  info,
}) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="inline-flex h-8 items-center rounded-sm">
      <TabsTrigger value={value} className="h-8 rounded-r-none px-3 text-xs">
        {title}
      </TabsTrigger>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={infoLabel}
            className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-sm text-muted-foreground hover:bg-background/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="text-xs leading-relaxed" side="bottom" align="start">
          {info}
        </PopoverContent>
      </Popover>
    </div>
  );
};

const MarketplaceJsonDraftEditor: React.FC<MarketplaceJsonDraftEditorProps> = ({
  title,
  filePath,
  badgeSuffix,
  value,
  error,
  onChange,
}) => (
  <div className="space-y-3 rounded-md border border-border bg-muted/20 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
          {filePath}
        </span>
        {badgeSuffix ? (
          <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
            {badgeSuffix}
          </span>
        ) : null}
      </div>
    </div>
    <div aria-label={title} className="h-[28rem] overflow-hidden rounded-md border border-border bg-background">
      <CodeTextEditor
        fileName={filePath}
        content={value}
        onContentChange={onChange}
      />
    </div>
    {error ? (
      <p className="text-xs font-medium text-destructive">{error}</p>
    ) : null}
  </div>
);

interface MarketplaceEditorReadonlyFieldProps {
  label: string;
  value: string;
  hint?: string;
}

const MarketplaceEditorReadonlyField: React.FC<MarketplaceEditorReadonlyFieldProps> = ({ label, value, hint }) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Input value={value} readOnly className="cursor-not-allowed bg-muted font-mono text-sm" />
    {hint ? (
      <p className="text-xs text-muted-foreground">{hint}</p>
    ) : null}
  </div>
);

interface MarketplaceEditorEditableFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

const MarketplaceEditorEditableField: React.FC<MarketplaceEditorEditableFieldProps> = ({ label, value, onChange }) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Input value={value} onChange={event => onChange(event.target.value)} />
  </div>
);

interface MarketplaceEditorTextAreaFieldProps {
  label: string;
  value: string;
  rows?: number;
  onChange: (value: string) => void;
}

const MarketplaceEditorTextAreaField: React.FC<MarketplaceEditorTextAreaFieldProps> = ({
  label,
  value,
  rows = 3,
  onChange,
}) => (
  <div className="space-y-2">
    <label className="text-sm font-semibold text-foreground">{label}</label>
    <Textarea value={value} rows={rows} onChange={event => onChange(event.target.value)} />
  </div>
);
