export const loadMarketplaceModule = () =>
  import('./MarketplaceModule').then(({ MarketplaceModule }) => ({
    default: MarketplaceModule,
  }));
