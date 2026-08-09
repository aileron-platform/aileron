/**
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Settings, Save } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { apiClient } from '@/shared/api/apiClient';
import { cn } from '@/shared/utils/cn';
import type {
  WorkspaceComponentStatusResponse,
  WorkspaceDetailResponse,
} from '@/features/workspace/api/workspaceApiTypes';
import { WORKSPACE_ACCESS_SOURCE_BADGE_KEYS } from '@/features/workspace/model/workspaceTypes';
import type { AgenticTool } from '@/shared/types/agenticTool';
import { AGENTIC_TOOLS, normalizeAgenticTools } from '@/shared/types/agenticTool';
import {
  getWorkspaceCapacity,
  type WorkspaceCapacityResponse,
} from '../api/workspaceCapacityApi';
import { WorkspaceCapacityCard } from './WorkspaceCapacityCard';

interface WorkspaceFormValues {
  name: string;
  description: string;
  agenticTools: AgenticTool[];
}

const mapResponseToFormValues = (detail: WorkspaceDetailResponse): WorkspaceFormValues => ({
  name: detail.name ?? '',
  description: detail.description ?? '',
  agenticTools: normalizeAgenticTools(detail.agenticTools),
});

const agenticToolLabelKeys: Record<AgenticTool, string> = {
  'claude-code': 'workspace.workspaceSettings.basic.fields.agenticTool.options.claudeCode',
  codex: 'workspace.workspaceSettings.basic.fields.agenticTool.options.codex',
  opencode: 'workspace.workspaceSettings.basic.fields.agenticTool.options.opencode',
};

const areAgenticToolsEqual = (left: AgenticTool[], right: AgenticTool[]) =>
  left.length === right.length && left.every((tool, index) => tool === right[index]);

export const WorkspaceBasicSettings: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, permissions } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;

  const [formState, setFormState] = useState<WorkspaceFormValues | null>(null);
  const [initialState, setInitialState] = useState<WorkspaceFormValues | null>(null);
  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capacity, setCapacity] = useState<WorkspaceCapacityResponse | null>(null);
  const [isCapacityLoading, setIsCapacityLoading] = useState(false);
  const [capacityError, setCapacityError] = useState(false);

  const getProvisionerLabel = (provisioner?: WorkspaceDetailResponse['provisioner']) => {
    if (provisioner === 'kubernetes') {
      return t('workspace.workspaceSettings.basic.metadata.provisioners.kubernetes');
    }
    return t('workspace.workspaceSettings.basic.metadata.provisioners.docker');
  };

  const getPhaseLabel = (phase?: string | null) => {
    if (!phase) {
      return t('workspace.workspaceSettings.basic.metadata.phases.unknown');
    }
    const phaseKey = phase.toLowerCase();
    const localized = t(`workspace.workspaceSettings.basic.metadata.phases.${phaseKey}`);
    return localized === `workspace.workspaceSettings.basic.metadata.phases.${phaseKey}`
      ? phase
      : localized;
  };

  const getPhaseBadgeClassName = (phase?: string | null) => {
    switch (phase?.toLowerCase()) {
      case 'running':
        return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700';
      case 'starting':
      case 'reconciling':
      case 'pending':
        return 'border-amber-500/20 bg-amber-500/10 text-amber-700';
      case 'failed':
      case 'error':
        return 'border-destructive/20 bg-destructive/10 text-destructive';
      case 'disabled':
      case 'stopped':
        return 'border-slate-500/20 bg-slate-500/10 text-slate-700';
      default:
        return 'border-primary/20 bg-primary/10 text-primary';
    }
  };

  const renderUrlValue = (url?: string | null) => {
    if (!url) {
      return (
        <span className="text-sm text-muted-foreground">
          {t('workspace.workspaceSettings.basic.metadata.notAvailable')}
        </span>
      );
    }

    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="break-all text-sm text-primary underline-offset-4 hover:underline"
      >
        {url}
      </a>
    );
  };

  useEffect(() => {
    let isActive = true;

    const loadWorkspace = async () => {
      if (!workspaceId) {
        setFormState(null);
        setInitialState(null);
        setWorkspaceDetail(null);
        setError(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const data = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`
        );
        if (!isActive) {
          return;
        }
        const normalized = mapResponseToFormValues(data);
        setWorkspaceDetail(data);
        setFormState(normalized);
        setInitialState(normalized);
      } catch (err) {
        if (!isActive) {
          return;
        }
        const message =
          err instanceof Error && err.message
            ? err.message
            : t('workspace.workspaceSettings.basic.notifications.loadFailed');
        setError(message);
        setWorkspaceDetail(null);
        setFormState(null);
        setInitialState(null);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadWorkspace();

    return () => {
      isActive = false;
    };
  }, [workspaceId, t]);

  useEffect(() => {
    let isActive = true;
    if (!workspaceId) {
      setCapacity(null);
      setCapacityError(false);
      return () => { isActive = false; };
    }
    setIsCapacityLoading(true);
    setCapacityError(false);
    void getWorkspaceCapacity(workspaceId)
      .then((response) => {
        if (isActive) setCapacity(response);
      })
      .catch(() => {
        if (!isActive) return;
        setCapacity(null);
        setCapacityError(true);
      })
      .finally(() => {
        if (isActive) setIsCapacityLoading(false);
      });
    return () => { isActive = false; };
  }, [workspaceId]);

  const accessRole = permissions.accessRole;
  const accessSource = workspaceDetail?.accessSource;
  const canManageWorkspace = permissions.canUpdateMetadata;

  const handleChange = (field: keyof WorkspaceFormValues, value: string) => {
    setFormState((current) => (current ? { ...current, [field]: value } : current));
  };

  const toggleAgenticTool = (tool: AgenticTool) => {
    if (!canManageWorkspace) {
      return;
    }
    setFormState((current) => {
      if (!current) {
        return current;
      }
      const selected = current.agenticTools.includes(tool);
      const nextTools = selected
        ? current.agenticTools.filter((item) => item !== tool)
        : normalizeAgenticTools([...current.agenticTools, tool]);

      if (nextTools.length === 0) {
        return current;
      }
      return { ...current, agenticTools: nextTools };
    });
  };

  const isDirty = useMemo(() => {
    if (!initialState || !formState) {
      return false;
    }
    return (
      initialState.name !== formState.name ||
      initialState.description !== formState.description ||
      !areAgenticToolsEqual(initialState.agenticTools, formState.agenticTools)
    );
  }, [initialState, formState]);

  const handleSave = async () => {
    if (!workspaceId || !formState || !canManageWorkspace) {
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const data = await apiClient.put<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
        {
          name: formState.name,
          description: formState.description,
          agenticTools: formState.agenticTools,
        }
      );
      const normalized = mapResponseToFormValues(data);
      setWorkspaceDetail(data);
      setFormState(normalized);
      setInitialState(normalized);
      await workspaceRuntime.reload();
      toast({
        title: t('workspace.workspaceSettings.basic.header.title'),
        description: t('workspace.workspaceSettings.basic.notifications.saveSuccess'),
      });
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : t('workspace.workspaceSettings.basic.notifications.saveFailed');
      setError(message);
      toast({
        title: t('workspace.workspaceSettings.basic.header.title'),
        description: t('workspace.workspaceSettings.basic.notifications.saveFailed'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const isSaveDisabled =
    isSaving ||
    isLoading ||
    !formState ||
    !workspaceId ||
    !canManageWorkspace ||
    !isDirty;

  const componentItems = useMemo<Array<{
    key: 'runtime' | 'browser' | 'canvas';
    label: string;
    value: WorkspaceComponentStatusResponse | undefined;
    publicUrl: string | undefined;
  }>>(() => [
    {
      key: 'runtime',
      label: t('workspace.workspaceSettings.basic.components.runtime'),
      value: workspaceDetail?.components?.runtime,
      publicUrl: workspaceDetail?.runtimeStatus.runtimeUrl,
    },
    {
      key: 'browser',
      label: t('workspace.workspaceSettings.basic.components.browser'),
      value: workspaceDetail?.components?.browser,
      publicUrl: workspaceDetail?.runtimeStatus.browserUrl,
    },
    {
      key: 'canvas',
      label: t('workspace.workspaceSettings.basic.components.canvas'),
      value: workspaceDetail?.components?.canvas,
      publicUrl: workspaceDetail?.runtimeStatus.canvasUrl,
    },
  ], [t, workspaceDetail]);

  return (
    <div className="h-full flex flex-col">
      <FeatureHeader
        title={t('workspace.workspaceSettings.basic.header.title')}
        icon={Settings}
        actions={(
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleSave}
            disabled={isSaveDisabled}
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {isSaving
              ? t('workspace.workspaceSettings.basic.actions.save.saving')
              : t('workspace.workspaceSettings.basic.actions.save.label')}
          </Button>
        )}
      />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {error && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          {isLoading ? (
            <p className="text-sm text-muted-foreground">
              {t('workspace.workspaceSettings.basic.status.loading')}
            </p>
          ) : formState ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="workspaceName">
                  {t('workspace.workspaceSettings.basic.fields.name.label')}
                </Label>
                <Input
                  id="workspaceName"
                  value={formState.name}
                  disabled={!canManageWorkspace}
                  onChange={(e) => handleChange('name', e.target.value)}
                  placeholder={t('workspace.workspaceSettings.basic.fields.name.placeholder')}
                />
                <p className="text-xs text-muted-foreground">
                  {t('workspace.workspaceSettings.basic.fields.name.helper')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">
                  {t('workspace.workspaceSettings.basic.fields.description.label')}
                </Label>
                <Textarea
                  id="description"
                  value={formState.description}
                  disabled={!canManageWorkspace}
                  onChange={(e) => handleChange('description', e.target.value)}
                  placeholder={t('workspace.workspaceSettings.basic.fields.description.placeholder')}
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  {t('workspace.workspaceSettings.basic.fields.description.helper')}
                </p>
              </div>

              <div className="space-y-2">
                <Label>
                  {t('workspace.workspaceSettings.basic.fields.agenticTool.label')}
                </Label>
                <div className="flex flex-wrap gap-2">
                  {AGENTIC_TOOLS.map((tool) => {
                    const isSelected = formState.agenticTools.includes(tool);
                    return (
                      <button
                        key={tool}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => toggleAgenticTool(tool)}
                        disabled={!canManageWorkspace}
                        className={cn(
                          'inline-flex h-8 items-center rounded-md border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
                          isSelected
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border bg-background text-muted-foreground hover:border-primary/60 hover:text-foreground'
                        )}
                      >
                        {t(agenticToolLabelKeys[tool])}
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('workspace.workspaceSettings.basic.fields.agenticTool.helper')}
                </p>
              </div>

              <WorkspaceCapacityCard
                capacity={capacity}
                isLoading={isCapacityLoading}
                hasError={capacityError}
              />

              <div className="space-y-3 rounded-lg border border-border/60 bg-card/70 p-4">
                <div>
                  <h3 className="text-sm font-semibold">
                    {t('workspace.workspaceSettings.basic.metadata.title')}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.workspaceSettings.basic.metadata.description')}
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.basic.metadata.fields.provisioner')}
                    </p>
                    <Badge variant="outline" className="w-fit text-[11px]">
                      {getProvisionerLabel(workspaceDetail?.provisioner)}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.basic.metadata.fields.namespace')}
                    </p>
                    <p className="text-sm font-medium">
                      {workspaceDetail?.targetNamespace
                        || t('workspace.workspaceSettings.basic.metadata.namespaceFallback')}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.basic.metadata.fields.overallPhase')}
                    </p>
                    <Badge
                      variant="outline"
                      className={`w-fit text-[11px] ${getPhaseBadgeClassName(workspaceDetail?.overallPhase)}`}
                    >
                      {getPhaseLabel(workspaceDetail?.overallPhase)}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.workspaceSettings.basic.metadata.fields.access')}
                    </p>
                    {accessRole ? (
                      <Badge variant="secondary" className="w-fit text-[11px] uppercase">
                        {accessSource
                          ? t(WORKSPACE_ACCESS_SOURCE_BADGE_KEYS[accessSource], {
                              role: t(`workspace.workspaceSettings.access.roles.${accessRole}`),
                            })
                          : null}
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="space-y-3 rounded-lg border border-border/60 bg-card/70 p-4">
                <div>
                  <h3 className="text-sm font-semibold">
                    {t('workspace.workspaceSettings.basic.components.title')}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.workspaceSettings.basic.components.description')}
                  </p>
                </div>
                <div className="grid gap-3 lg:grid-cols-3">
                  {componentItems.map((component) => (
                    <div
                      key={component.key}
                      className="space-y-3 rounded-md border border-border/60 bg-background/70 p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">{component.label}</p>
                        <Badge
                          variant="outline"
                          className={`text-[11px] ${getPhaseBadgeClassName(component.value?.phase)}`}
                        >
                          {getPhaseLabel(component.value?.phase)}
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">
                            {t('workspace.workspaceSettings.basic.components.fields.publicUrl')}
                          </p>
                          {renderUrlValue(component.publicUrl)}
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">
                            {t('workspace.workspaceSettings.basic.components.fields.lastRestartRequestedAt')}
                          </p>
                          <p className="text-sm">
                            {component.value?.lastRestartRequestedAt
                              ? new Date(component.value.lastRestartRequestedAt).toLocaleString()
                              : t('workspace.workspaceSettings.basic.metadata.notAvailable')}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('workspace.workspaceSettings.empty.description')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
