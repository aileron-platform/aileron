import { ROUTES } from '@/shared/constants/routes';

export type GlobalNavigationModule =
  | 'workspace'
  | 'marketplace'
  | 'automation'
  | 'knowledge-base'
  | 'user-management'
  | 'platform-resources';

const isPathWithin = (pathname: string, root: string): boolean => (
  pathname === root || pathname.startsWith(`${root}/`)
);

export const getGlobalNavigationModule = (pathname: string): GlobalNavigationModule => {
  if (isPathWithin(pathname, ROUTES.marketplace.root)) return 'marketplace';
  if (isPathWithin(pathname, ROUTES.automation)) return 'automation';
  if (isPathWithin(pathname, ROUTES.knowledgeBase.root)) return 'knowledge-base';
  if (isPathWithin(pathname, ROUTES.userManagement.root)) return 'user-management';
  if (isPathWithin(pathname, ROUTES.platformResources.root)) return 'platform-resources';
  return 'workspace';
};
