import React from 'react';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';
import {
  loadWorkspaceModule,
  WorkspaceFileDeepLinkRoute,
} from '@/features/workspace/public';

const WorkspaceModule = React.lazy(loadWorkspaceModule);

export const WorkspaceRoute: React.FC = () => (
  <WorkspaceModule navigationSlot={<GlobalNavigation />} />
);

export const WorkspaceDeepLinkRoute: React.FC = () => (
  <WorkspaceFileDeepLinkRoute />
);
