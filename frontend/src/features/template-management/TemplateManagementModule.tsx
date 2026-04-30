/**
 * TemplateManagementModule - template management module root.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { TemplateManagementProvider } from './providers/TemplateManagementProvider';
import { TemplateManagementShell } from './components/TemplateManagementShell';
import { TemplateDeepLinkFallback } from './components/TemplateDeepLinkFallback';
import { TemplateRegistryOnboardingBoundary } from './components/TemplateRegistryOnboardingBoundary';
import { TemplateCenterView } from './features/template-center/TemplateCenterView';
import { TemplateCenterSettingsView } from './features/template-center-settings/TemplateCenterSettingsView';
import { TemplateDetailView } from './features/template-detail/TemplateDetailView';
import { TemplateEditorView } from './features/template-editor/TemplateEditorView';

export const TemplateManagementModule: React.FC = () => {
  return (
    <TemplateManagementShell>
      <TemplateRegistryOnboardingBoundary>
        <TemplateManagementProvider>
          <TemplateDeepLinkFallback>
            <Routes>
              <Route index element={<TemplateCenterView />} />
              <Route path="templates">
                <Route index element={<TemplateCenterView />} />
                <Route path="settings" element={<TemplateCenterSettingsView />} />
                <Route path="new" element={<TemplateEditorView mode="create" />} />
                <Route path=":templateId">
                  <Route index element={<TemplateDetailView />} />
                  <Route path="edit" element={<TemplateEditorView mode="edit" />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="." replace />} />
            </Routes>
          </TemplateDeepLinkFallback>
        </TemplateManagementProvider>
      </TemplateRegistryOnboardingBoundary>
    </TemplateManagementShell>
  );
};

export default TemplateManagementModule;
