import React from 'react';
import { Copy, Download } from 'lucide-react';
import { MarkdownDocumentShell } from '@/shared/components/document-workflow';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { getRootDocument, saveRootDocument } from '../../../api/marketplaceApi';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { downloadBlob } from '../../../utils/downloadBlob';
import type { MarketplacePackageMutationResult } from '../../../model/marketplaceMutation';
import { MarketplaceResourceLoadError } from '../../../components/MarketplaceResourceLoadError';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

interface MarketplaceRootDocumentPageProps {
  packageDetail: MarketplacePackageDetail;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
}

export const MarketplaceRootDocumentPage: React.FC<MarketplaceRootDocumentPageProps> = ({
  packageDetail,
  onMutation,
}) => {
  const { t } = useI18n();
  const [content, setContent] = React.useState('');
  const [savedContent, setSavedContent] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSaving, setIsSaving] = React.useState(false);
  const [loadError, setLoadError] = React.useState(false);
  const fileName = packageDetail.provider === 'claude-code' ? 'CLAUDE.md' : 'AGENTS.md';
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    provider: packageDetail.provider,
    packageId: packageDetail.packageId,
    resourceType: 'root-document',
  }, packageDetail.revision);

  React.useLayoutEffect(() => {
    setContent('');
    setSavedContent('');
    setIsLoading(true);
    setIsSaving(false);
    setLoadError(false);
  }, [identityGeneration]);

  const loadContent = React.useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    await session.query(
      identityGeneration,
      'root-document-load',
      () => getRootDocument(packageDetail.provider, packageDetail.packageId),
      {
        onSuccess: (resource) => {
          setContent(resource.content);
          setSavedContent(resource.content);
        },
        onError: () => {
          setLoadError(true);
        },
        onSettled: () => {
          setIsLoading(false);
        },
      },
    );
  }, [
    identityGeneration,
    packageDetail.packageId,
    packageDetail.provider,
    session,
  ]);

  React.useEffect(() => {
    void loadContent();
  }, [loadContent]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    downloadBlob(blob, fileName);
  };

  const handleSave = async () => {
    setIsSaving(true);
    await session.mutate(
      identityGeneration,
      'root-document-mutation',
      () => saveRootDocument(packageDetail.provider, packageDetail.packageId, {
        revision: session.revision,
        content,
      }),
      async (result) => {
        setSavedContent(content);
        await onMutation(result);
      },
      () => {
        setIsSaving(false);
      },
    );
  };

  if (loadError) {
    return (
      <div className="flex h-full min-w-0 flex-1 bg-background">
        <MarketplaceResourceLoadError onRetry={() => { void loadContent(); }} />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      <MarkdownDocumentShell
        title={t('marketplace.editor.agentsMd.title')}
        refreshLabel={t('marketplace.common.actions.refresh')}
        saveLabel={t('marketplace.common.actions.save')}
        runtimeLoadingLabel={t('marketplace.editor.agentsMd.status.loading')}
        loadingLabel={t('marketplace.editor.agentsMd.status.loading')}
        isRuntimeReady
        isLoading={isLoading}
        isSaving={isSaving}
        value={content}
        onChange={setContent}
        onRefresh={() => { void loadContent(); }}
        onSave={() => { void handleSave(); }}
        saveDisabled={isLoading || isSaving || content === savedContent}
        statusMessage={(
          <span className="font-mono text-xs text-muted-foreground">
            {fileName}
          </span>
        )}
        placeholder={t('marketplace.editor.agentsMd.placeholder')}
        headerExtras={(
          <>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={() => { void handleCopy(); }}
            >
              <Copy className="mr-1.5 h-3.5 w-3.5" />
              {t('marketplace.editor.agentsMd.actions.copy')}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleDownload}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {t('marketplace.editor.agentsMd.actions.download')}
            </Button>
          </>
        )}
      />
    </div>
  );
};
