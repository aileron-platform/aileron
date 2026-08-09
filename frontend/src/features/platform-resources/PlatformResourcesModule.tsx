import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ProductShell } from '@/shared/components/shell';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { PlatformResourcesPage } from './PlatformResourcesPage';

interface PlatformResourcesModuleProps {
  navigationSlot: React.ReactNode;
}

export const PlatformResourcesModule: React.FC<PlatformResourcesModuleProps> = ({ navigationSlot }) => {
  const { t } = useI18n();

  return (
    <ProductShell
      topBar={navigationSlot}
      body={{
        kind: 'regions',
        main: {
          accessibleLabel: t('platformResources.navigation'),
          content: (
            <Routes>
              <Route index element={<Navigate to={ROUTES.platformResources.workspaces} replace />} />
              <Route path="workspaces" element={<PlatformResourcesPage kind="workspaces" section="management" />} />
              <Route path="knowledge-bases" element={<PlatformResourcesPage kind="knowledge-bases" section="management" />} />
              <Route path="analytics" element={<Navigate to={ROUTES.platformResources.analytics.workspaces} replace />} />
              <Route path="analytics/workspaces" element={<PlatformResourcesPage kind="workspaces" section="analytics" />} />
              <Route path="analytics/knowledge-bases" element={<PlatformResourcesPage kind="knowledge-bases" section="analytics" />} />
              <Route path="*" element={<Navigate to={ROUTES.platformResources.workspaces} replace />} />
            </Routes>
          ),
        },
      }}
    />
  );
};

export default PlatformResourcesModule;
