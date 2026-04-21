import { useEffect, useMemo, useRef } from 'react';

import type { TemplateFeatureKey } from '@/shared/types/templates';

import {
  WORKSPACE_TEMPLATE_INSTALLED_EVENT,
  type WorkspaceTemplateInstalledEventDetail,
} from './templateInstallEvents';

type RefreshTargetRegistration = {
  enabled: boolean;
  features: Set<TemplateFeatureKey>;
  onRefresh: () => void | Promise<void>;
  onDeferredRefresh?: (detail: WorkspaceTemplateInstalledEventDetail) => void;
  shouldDeferRefresh?: () => boolean;
};

export interface WorkspaceTemplateInstallRefreshOptions {
  workspaceId: string | null | undefined;
  features: TemplateFeatureKey[];
  enabled?: boolean;
  onRefresh: () => void | Promise<void>;
  onDeferredRefresh?: (detail: WorkspaceTemplateInstalledEventDetail) => void;
  shouldDeferRefresh?: () => boolean;
}

export class WorkspaceTemplateInstallRefreshCoordinator {
  private targets = new Map<string, Map<number, RefreshTargetRegistration>>();
  private nextTargetId = 1;
  private isListening = false;

  private readonly handleEvent = (event: Event) => {
    const customEvent = event as CustomEvent<WorkspaceTemplateInstalledEventDetail>;
    const detail = customEvent.detail;
    if (!detail?.workspaceId || detail.installedFeatures.length === 0) {
      return;
    }

    const workspaceTargets = this.targets.get(detail.workspaceId);
    if (!workspaceTargets || workspaceTargets.size === 0) {
      return;
    }

    const affectedFeatures = new Set(detail.installedFeatures);
    workspaceTargets.forEach((target) => {
      if (!target.enabled) {
        return;
      }

      const shouldRefresh = Array.from(target.features).some((feature) => affectedFeatures.has(feature));
      if (!shouldRefresh) {
        return;
      }

      if (target.shouldDeferRefresh?.()) {
        target.onDeferredRefresh?.(detail);
        return;
      }

      void target.onRefresh();
    });
  };

  register(options: WorkspaceTemplateInstallRefreshOptions): () => void {
    const { workspaceId, enabled = true } = options;
    if (!workspaceId) {
      return () => {};
    }

    this.ensureListening();

    const targetId = this.nextTargetId++;
    const workspaceTargets = this.targets.get(workspaceId) ?? new Map<number, RefreshTargetRegistration>();
    workspaceTargets.set(targetId, {
      enabled,
      features: new Set(options.features),
      onRefresh: options.onRefresh,
      onDeferredRefresh: options.onDeferredRefresh,
      shouldDeferRefresh: options.shouldDeferRefresh,
    });
    this.targets.set(workspaceId, workspaceTargets);

    return () => {
      const currentWorkspaceTargets = this.targets.get(workspaceId);
      if (!currentWorkspaceTargets) {
        return;
      }

      currentWorkspaceTargets.delete(targetId);
      if (currentWorkspaceTargets.size === 0) {
        this.targets.delete(workspaceId);
      }

      this.teardownIfIdle();
    };
  }

  private ensureListening() {
    if (typeof window === 'undefined' || this.isListening) {
      return;
    }

    window.addEventListener(WORKSPACE_TEMPLATE_INSTALLED_EVENT, this.handleEvent);
    this.isListening = true;
  }

  private teardownIfIdle() {
    if (typeof window === 'undefined' || !this.isListening || this.targets.size > 0) {
      return;
    }

    window.removeEventListener(WORKSPACE_TEMPLATE_INSTALLED_EVENT, this.handleEvent);
    this.isListening = false;
  }
}

export const workspaceTemplateInstallRefreshCoordinator =
  new WorkspaceTemplateInstallRefreshCoordinator();

export function useWorkspaceTemplateInstallRefresh(
  options: WorkspaceTemplateInstallRefreshOptions,
): void {
  const onRefreshRef = useRef(options.onRefresh);
  const shouldDeferRefreshRef = useRef(options.shouldDeferRefresh);
  const onDeferredRefreshRef = useRef(options.onDeferredRefresh);

  onRefreshRef.current = options.onRefresh;
  shouldDeferRefreshRef.current = options.shouldDeferRefresh;
  onDeferredRefreshRef.current = options.onDeferredRefresh;

  const featureSignature = useMemo(
    () => Array.from(new Set(options.features)).sort().join('|'),
    [options.features],
  );

  useEffect(() => {
    return workspaceTemplateInstallRefreshCoordinator.register({
      workspaceId: options.workspaceId,
      enabled: options.enabled,
      features: featureSignature
        ? (featureSignature.split('|') as TemplateFeatureKey[])
        : [],
      onRefresh: () => onRefreshRef.current(),
      shouldDeferRefresh: () => shouldDeferRefreshRef.current?.() ?? false,
      onDeferredRefresh: (detail) => onDeferredRefreshRef.current?.(detail),
    });
  }, [options.workspaceId, options.enabled, featureSignature]);
}
