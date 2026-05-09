import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Bot, Command, Info, Wand2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import type { MarketplacePackageDetail, MarketplaceProvider } from '@/shared/types/marketplace';
import { resolveMarketplacePermissions } from '../../permissions';
import { getPackage } from '../../api/marketplaceApi';
import {
  MarketplaceDeleteDialog,
  MarketplaceExportDialog,
  MarketplaceInstallDialog,
} from '../../components/MarketplaceDetailActionDialogs';
import {
  getMarketplaceDetailFeatureItems,
  MarketplaceAgentsMdPanel,
  MarketplaceBasicInfoPanel,
  MarketplaceHooksWorkflow,
  MarketplaceMcpWorkflow,
  type MarketplaceDetailFeatureItem,
} from '../../components/MarketplaceDetailContentPanels';
import { MarketplaceDetailFeatureContentSection } from '../../components/MarketplaceDetailFeatureContentSection';
import { MarketplaceDetailTopTabs } from '../../components/MarketplaceDetailTopTabs';
import { MarketplaceFilesSection } from '../../components/MarketplaceFilesSection';
import { MarketplacePackageDetailHeader } from '../../components/MarketplacePackageDetailHeader';
import { getMarketplaceFeatureLabelKey } from '../../utils/featureLabels';

type MarketplaceDetailTab = 'basic-info' | MarketplaceDetailFeatureItem['id'];

const LEFT_WIDTH = 280;

const isProvider = (value: string | undefined): value is MarketplaceProvider =>
  value === 'claude-code' || value === 'codex' || value === 'gemini';

export const MarketplaceDetailView: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { provider, packageId } = useParams();
  const [activeTab, setActiveTab] = React.useState<MarketplaceDetailTab>('basic-info');
  const [detail, setDetail] = React.useState<MarketplacePackageDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [activeAction, setActiveAction] = React.useState<'install' | 'export' | 'delete' | null>(null);
  const permissions = React.useMemo(() => resolveMarketplacePermissions(), []);

  React.useEffect(() => {
    let isActive = true;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      if (!isProvider(provider) || !packageId) {
        setError('marketplace.errors.packageNotFound');
        setIsLoading(false);
        return;
      }
      try {
        const data = await getPackage(provider, packageId);
        if (isActive) setDetail(data);
      } catch (err) {
        if (isActive) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (isActive) setIsLoading(false);
      }
    };
    void load();
    return () => { isActive = false; };
  }, [packageId, provider]);

  const tabs = React.useMemo(
    () => detail ? [
      { id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 },
      ...getMarketplaceDetailFeatureItems(detail, t),
    ] : [{ id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 }],
    [
      detail?.featureContent.agents.length,
      detail?.featureContent.agentsMd,
      detail?.featureContent.commands.length,
      detail?.featureContent.hooks.length,
      detail?.featureContent.mcpServers.length,
      detail?.featureContent.outputStyles.length,
      detail?.featureContent.skills.length,
      detail?.packageFiles.length,
      detail?.provider,
      t,
    ],
  );

  if (isLoading) {
    return (
      <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />
    );
  }

  if (error || !detail) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-sm text-muted-foreground">
        <p>{t('marketplace.errors.packageNotFound')}</p>
        <Button onClick={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}>
          {t('marketplace.detail.actions.backToCenter')}
        </Button>
      </div>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'basic-info':
        return (
          <MarketplaceBasicInfoPanel
            detail={detail}
            onOpenVariant={(variantProvider, variantPackageId) => {
              navigate(ROUTES.MARKETPLACE_PACKAGE_DETAIL(variantProvider, variantPackageId));
            }}
          />
        );
      case 'agents-md':
        return (
          <MarketplaceAgentsMdPanel
            title={t(getMarketplaceFeatureLabelKey(detail.provider, 'agentsMd'))}
            content={detail.featureContent.agentsMd ?? ''}
          />
        );
      case 'hooks':
        return <MarketplaceHooksWorkflow provider={detail.provider} hooks={detail.featureContent.hooks} />;
      case 'mcp':
        return <MarketplaceMcpWorkflow servers={detail.featureContent.mcpServers} />;
      case 'agent':
        return (
          <MarketplaceDetailFeatureContentSection
            title={t('marketplace.features.subagents')}
            items={detail.featureContent.agents}
            icon={Bot}
            emptyLabel={t('marketplace.detail.featureEmpty')}
          />
        );
      case 'commands':
        return (
          <MarketplaceDetailFeatureContentSection
            title={t('marketplace.features.slashCommands')}
            items={detail.featureContent.commands}
            icon={Command}
            emptyLabel={t('marketplace.detail.featureEmpty')}
          />
        );
      case 'output-style':
        return (
          <MarketplaceDetailFeatureContentSection
            title={t('marketplace.features.outputStyle')}
            items={detail.featureContent.outputStyles}
            icon={Wand2}
            emptyLabel={t('marketplace.detail.featureEmpty')}
          />
        );
      case 'skills':
        return <MarketplaceFilesSection mode="skills" items={detail.featureContent.skills} />;
      case 'files':
        return <MarketplaceFilesSection mode="package" detail={detail} />;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-full flex-col">
      <MarketplacePackageDetailHeader
        detail={detail}
        permissions={permissions}
        onBack={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}
        onEdit={() => navigate(ROUTES.MARKETPLACE_PACKAGE_EDIT(detail.provider, detail.packageId))}
        onExport={() => setActiveAction('export')}
        onInstall={() => setActiveAction('install')}
        onDelete={() => setActiveAction('delete')}
      />

      <div className="flex-1 overflow-hidden">
        <div className="flex h-full">
          <MarketplaceDetailTopTabs
            detail={detail}
            tabs={tabs}
            activeTab={activeTab}
            leftWidth={LEFT_WIDTH}
            onChange={setActiveTab}
          />

          <div className="flex-1 overflow-hidden bg-background">
            {renderContent()}
          </div>
        </div>
      </div>

      <MarketplaceInstallDialog
        open={activeAction === 'install'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'install' : null)}
      />
      <MarketplaceExportDialog
        open={activeAction === 'export'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'export' : null)}
      />
      <MarketplaceDeleteDialog
        open={activeAction === 'delete'}
        detail={detail}
        onOpenChange={open => setActiveAction(open ? 'delete' : null)}
        onDeleted={() => navigate(ROUTES.MARKETPLACE_PACKAGES)}
      />
    </div>
  );
};

export default MarketplaceDetailView;
