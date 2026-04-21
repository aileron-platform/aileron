import type { TemplateFeatureKey } from '@/shared/types/templates';

export const WORKSPACE_TEMPLATE_INSTALLED_EVENT = 'workspace:template-installed';

export interface WorkspaceTemplateInstalledEventDetail {
  workspaceId: string;
  templateId: string;
  installedFeatures: TemplateFeatureKey[];
}

export const dispatchWorkspaceTemplateInstalledEvent = (
  detail: WorkspaceTemplateInstalledEventDetail,
): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<WorkspaceTemplateInstalledEventDetail>(WORKSPACE_TEMPLATE_INSTALLED_EVENT, {
      detail,
    }),
  );
};
