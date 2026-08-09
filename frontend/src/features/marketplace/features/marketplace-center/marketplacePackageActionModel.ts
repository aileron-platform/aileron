import type {
  MarketplaceDeleteRequest,
  MarketplaceExportRequest,
  MarketplacePackageSummary,
} from '@/features/marketplace/model/marketplaceTypes';
import type {
  MarketplacePackageActionType,
} from '@/features/marketplace/model/marketplacePackageActionModel';

export interface MarketplaceActionTextKeys {
  titleKey: string;
  descriptionKey: string;
  resultFailedKey: string;
  actionKey: string;
}

export const getMarketplaceActionTextKeys = (
  actionType: MarketplacePackageActionType,
): MarketplaceActionTextKeys => {
  if (actionType === 'export') {
    return {
      titleKey: 'marketplace.export.title',
      descriptionKey: 'marketplace.export.description',
      resultFailedKey: 'marketplace.export.result.failed',
      actionKey: 'marketplace.export.actions.export',
    };
  }
  return {
    titleKey: 'marketplace.delete.title',
    descriptionKey: 'marketplace.delete.description',
    resultFailedKey: 'marketplace.delete.result.failed',
    actionKey: 'marketplace.delete.actions.delete',
  };
};

export const buildMarketplaceExportRequest = (
  item: MarketplacePackageSummary,
): MarketplaceExportRequest => ({
  provider: item.provider,
  packageId: item.packageId,
  revision: item.revision,
});

export const buildMarketplaceDeleteRequest = (
  item: MarketplacePackageSummary,
): MarketplaceDeleteRequest => ({
  provider: item.provider,
  packageId: item.packageId,
  revision: item.revision,
});

export const isMarketplaceDeleteBlocked = (
  actionType: MarketplacePackageActionType,
  confirmText: string,
  packageId: string,
) => actionType === 'delete' && confirmText !== packageId;
