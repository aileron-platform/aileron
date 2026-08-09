import React from 'react';
import { Info, Save } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { updateBasic } from '../../../api/marketplaceApi';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { parseMarketplaceJsonObject, type MarketplaceRequiredDraft } from '../marketplaceEditorRequiredDraft';
import { MarketplaceEditorBasicSection } from '../MarketplaceEditorBasicSection';
import type { MarketplacePackageMutationResult } from '../../../model/marketplaceMutation';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

interface MarketplaceBasicPageProps {
  packageDetail: MarketplacePackageDetail;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
}

export const MarketplaceBasicPage: React.FC<MarketplaceBasicPageProps> = ({
  packageDetail,
  onMutation,
}) => {
  const { t } = useI18n();
  const [displayName, setDisplayName] = React.useState(packageDetail.displayName);
  const [description, setDescription] = React.useState(packageDetail.description ?? '');
  const [requiredDraft, setRequiredDraft] = React.useState<MarketplaceRequiredDraft | null>(null);
  const [isSaving, setIsSaving] = React.useState(false);
  const savingRef = React.useRef(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    provider: packageDetail.provider,
    packageId: packageDetail.packageId,
    resourceType: 'basic',
  }, packageDetail.revision);

  React.useEffect(() => {
    setDisplayName(packageDetail.displayName);
    setDescription(packageDetail.description ?? '');
    setRequiredDraft(null);
    savingRef.current = false;
    setIsSaving(false);
  }, [
    identityGeneration,
    packageDetail.description,
    packageDetail.displayName,
  ]);

  const handleSave = async () => {
    if (savingRef.current) return;
    savingRef.current = true;
    setIsSaving(true);
    const catalogMetadata = parseMarketplaceJsonObject(requiredDraft?.listingJson ?? '')
      ?? packageDetail.catalogMetadata;
    const manifestMetadata = parseMarketplaceJsonObject(requiredDraft?.manifestJson ?? '')
      ?? packageDetail.manifestMetadata;
    await session.mutate(
      identityGeneration,
      'basic-mutation',
      () => updateBasic(packageDetail.provider, packageDetail.packageId, {
        revision: session.revision,
        displayName,
        description,
        catalogMetadata,
        manifestMetadata,
      }),
      onMutation,
      () => {
        savingRef.current = false;
        setIsSaving(false);
      },
    );
  };

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      <FeatureHeader
        title={t('marketplace.editor.tabs.basic')}
        icon={Info}
        actions={(
          <Button
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => { void handleSave(); }}
            disabled={isSaving}
          >
            <Save className="mr-1 h-3 w-3" />
            {t('marketplace.common.actions.save')}
          </Button>
        )}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        <MarketplaceEditorBasicSection
          mode="edit"
          provider={packageDetail.provider}
          packageId={packageDetail.packageId}
          displayName={displayName}
          description={description}
          detail={packageDetail}
          onPackageIdChange={() => undefined}
          onDisplayNameChange={setDisplayName}
          onDescriptionChange={setDescription}
          onRequiredDraftChange={setRequiredDraft}
          onReadmeChange={() => undefined}
          onDirty={() => undefined}
          showReadmeSection={false}
        />
      </div>
    </div>
  );
};
