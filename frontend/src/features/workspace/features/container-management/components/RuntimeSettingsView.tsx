/**
 * RuntimeSettingsView - 執行環境設定組件
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Plus, X, Network, Settings, Save } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { apiClient } from '@/shared/api/apiClient';
import { useContainerImages } from '@/shared/hooks/useContainerImages';
import { workspaceLifecycleApi } from '@/features/workspace/services/workspaceLifecycleApi';
import type {
  WorkspaceDetailResponse,
  WorkspaceResourceRequirementsResponse,
} from '@/features/workspace/providers/workspaceState.types';

// 環境變數和端口映射類型
interface EnvVar {
  id: number;
  key: string;
  value: string;
}

interface PortMapping {
  id: number;
  containerPort: number;
  hostPort: number | null;
  protocol: 'tcp' | 'udp';
  description: string;
}

interface SystemPortMapping {
  id: number;
  name: string;
  containerPort: number;
  hostPort: number | null;
  protocol: string;
  description: string;
  editable: boolean;
}

interface RuntimeResourceField {
  cpu: string;
  memory: string;
}

interface RuntimeResourceFormState {
  requests: RuntimeResourceField;
  limits: RuntimeResourceField;
}

interface RuntimeFormState {
  runtime: string;
  provisioner: 'docker' | 'kubernetes';
  setupScript: string;
  envVars: EnvVar[];
  runtimeResources: RuntimeResourceFormState | null;
  systemPortMappings: SystemPortMapping[];
  portMappings: PortMapping[];
}

const mapResponseToFormState = (detail: WorkspaceDetailResponse): RuntimeFormState => {
  const envVars = (detail.envVars ?? []).map((envVar, index) => ({
    id: index + 1,
    key: envVar.key ?? '',
    value: envVar.value ?? '',
  }));

  const portMappings = (detail.portMappings ?? []).map((mapping, index) => ({
    id: index + 1,
    containerPort: mapping.containerPort ?? 0,
    hostPort: mapping.hostPort ?? null,
    protocol: mapping.protocol ?? 'tcp',
    description: mapping.description ?? '',
  }));
  const systemPortMappings = (detail.systemPortMappings ?? []).map((mapping, index) => ({
    id: index + 1,
    name: mapping.name ?? `system-${index + 1}`,
    containerPort: mapping.containerPort ?? 0,
    hostPort: mapping.hostPort ?? null,
    protocol: mapping.protocol ?? 'tcp',
    description: mapping.description ?? '',
    editable: mapping.editable ?? false,
  }));

  return {
    runtime: detail.runtime ?? '',
    provisioner: detail.provisioner ?? 'docker',
    setupScript: detail.setupScript ?? '',
    envVars,
    runtimeResources: detail.runtimeResources
      ? {
          requests: {
            cpu: detail.runtimeResources.requests.cpu ?? '',
            memory: detail.runtimeResources.requests.memory ?? '',
          },
          limits: {
            cpu: detail.runtimeResources.limits.cpu ?? '',
            memory: detail.runtimeResources.limits.memory ?? '',
          },
        }
      : null,
    systemPortMappings,
    portMappings,
  };
};

const toComparableState = (state: RuntimeFormState | null) => {
  if (!state) {
    return null;
  }
    return JSON.stringify({
      runtime: state.runtime,
      provisioner: state.provisioner,
      setupScript: state.setupScript,
      envVars: state.envVars.map(({ key, value }) => ({ key, value })),
      runtimeResources: state.runtimeResources,
      portMappings: state.portMappings.map(
        ({ containerPort, hostPort, protocol, description }) => ({
          containerPort,
        hostPort,
        protocol,
        description: description ?? '',
      })
    ),
  });
};

export const RuntimeSettingsView: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;

  // 載入容器映像列表
  const { data: containerImagesData, isLoading: isLoadingImages } = useContainerImages();

  const [formState, setFormState] = useState<RuntimeFormState | null>(null);
  const [initialState, setInitialState] = useState<RuntimeFormState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadRuntimeSettings = async () => {
      if (!workspaceId) {
        setFormState(null);
        setInitialState(null);
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

        const normalized = mapResponseToFormState(data);
        setFormState(normalized);
        setInitialState(normalized);
      } catch (err) {
        if (!isActive) {
          return;
        }
        const message =
          err instanceof Error && err.message
            ? err.message
            : t('workspace.containerManagement.runtime.notifications.loadFailed');
        setError(message);
        setFormState(null);
        setInitialState(null);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadRuntimeSettings();

    return () => {
      isActive = false;
    };
  }, [workspaceId, t]);

  const addEnvVar = () => {
    setFormState((current) => {
      if (!current) {
        return current;
      }
      const newId = Math.max(0, ...current.envVars.map((env) => env.id)) + 1;
      return {
        ...current,
        envVars: [...current.envVars, { id: newId, key: '', value: '' }],
      };
    });
  };

  const removeEnvVar = (id: number) => {
    setFormState((current) =>
      current
        ? {
            ...current,
            envVars: current.envVars.filter((envVar) => envVar.id !== id),
          }
        : current
    );
  };

  const updateEnvVar = (id: number, field: 'key' | 'value', value: string) => {
    setFormState((current) =>
      current
        ? {
            ...current,
            envVars: current.envVars.map((envVar) =>
              envVar.id === id ? { ...envVar, [field]: value } : envVar
            ),
          }
        : current
    );
  };

  const addPortMapping = () => {
    setFormState((current) => {
      if (!current) {
        return current;
      }
      const newId = Math.max(0, ...current.portMappings.map((port) => port.id)) + 1;
      return {
        ...current,
        portMappings: [
          ...current.portMappings,
          {
            id: newId,
            containerPort: 3000,
            hostPort: null,
            protocol: 'tcp',
            description: '',
          },
        ],
      };
    });
  };

  const removePortMapping = (id: number) => {
    setFormState((current) =>
      current
        ? {
            ...current,
            portMappings: current.portMappings.filter((port) => port.id !== id),
          }
        : current
    );
  };

  const updatePortMapping = (
    id: number,
    field: keyof PortMapping,
    value: string | number | null,
  ) => {
    setFormState((current) =>
      current
        ? {
            ...current,
            portMappings: current.portMappings.map((port) =>
              port.id === id
                ? {
                    ...port,
                    [field]:
                      field === 'containerPort'
                        ? Number(value)
                        : field === 'hostPort'
                        ? value === '' || value === null
                          ? null
                          : Number(value)
                        : value,
                  }
                : port
            ),
          }
        : current
    );
  };

  const isDirty = useMemo(() => {
    return toComparableState(formState) !== toComparableState(initialState);
  }, [formState, initialState]);

  const handleSaveSettings = async () => {
    if (!workspaceId || !formState) {
      return;
    }

    setIsSaving(true);
    setError(null);

    const payload = {
      runtime: formState.runtime,
      setupScript: formState.setupScript.trim() === '' ? null : formState.setupScript,
      envVars: formState.envVars
        .filter((envVar) => envVar.key.trim() !== '')
        .map(({ key, value }) => ({ key, value })),
      runtimeResources:
        formState.provisioner === 'kubernetes' && formState.runtimeResources
          ? formState.runtimeResources
          : null,
      ...(formState.provisioner === 'docker'
        ? {
            portMappings: formState.portMappings.map(
              ({ containerPort, hostPort, protocol, description }) => ({
                containerPort,
                hostPort,
                protocol,
                description: description.trim() === '' ? null : description,
              })
            ),
          }
        : {}),
    };

    try {
      const data = await apiClient.put<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
        payload
      );
      const normalized = mapResponseToFormState(data);
      setFormState(normalized);
      setInitialState(normalized);

      const onlyRuntimeResourcesChanged =
        formState.provisioner === 'kubernetes' &&
        formState.runtime === initialState?.runtime &&
        formState.setupScript === initialState?.setupScript &&
        JSON.stringify(formState.envVars.map(({ key, value }) => ({ key, value }))) ===
          JSON.stringify(initialState?.envVars.map(({ key, value }) => ({ key, value }))) &&
        JSON.stringify(
          formState.portMappings.map(
            ({ containerPort, hostPort, protocol, description }) => ({
              containerPort,
              hostPort,
              protocol,
              description,
            })
          )
        ) ===
          JSON.stringify(
            initialState?.portMappings.map(
              ({ containerPort, hostPort, protocol, description }) => ({
                containerPort,
                hostPort,
                protocol,
                description,
              })
            )
          );

      if (!onlyRuntimeResourcesChanged) {
        try {
          await workspaceLifecycleApi.rebuildWorkspace(workspaceId);
        } catch (rebuildError) {
          const message =
            rebuildError instanceof Error && rebuildError.message
              ? rebuildError.message
              : t('workspace.workspaceSettings.reset.rebuild.error.description');
          setError(message);
          toast({
            title: t('workspace.containerManagement.runtime.header.title'),
            description: message,
            variant: 'destructive',
          });
          return;
        }
      }

      toast({
        title: t('workspace.containerManagement.runtime.header.title'),
        description: t('workspace.containerManagement.runtime.notifications.saveSuccess'),
      });
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : t('workspace.containerManagement.runtime.notifications.saveFailed');
      setError(message);
      toast({
        title: t('workspace.containerManagement.runtime.header.title'),
        description: t('workspace.containerManagement.runtime.notifications.saveFailed'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const isSaveDisabled =
    isSaving ||
    isLoading ||
    !workspaceId ||
    !formState ||
    (formState.provisioner === 'kubernetes' &&
      (!formState.runtimeResources?.requests.cpu ||
        !formState.runtimeResources?.requests.memory ||
        !formState.runtimeResources?.limits.cpu ||
        !formState.runtimeResources?.limits.memory)) ||
    !isDirty;

  return (
    <div className="h-full flex flex-col bg-background">
      <FeatureHeader
        title={t('workspace.containerManagement.runtime.header.title')}
        icon={Settings}
        actions={
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleSaveSettings}
            disabled={isSaveDisabled}
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {isSaving
              ? t('workspace.containerManagement.runtime.header.actions.saving')
              : t('workspace.containerManagement.runtime.header.actions.save')}
          </Button>
        }
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
              {t('workspace.containerManagement.runtime.status.loading')}
            </p>
          ) : formState ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="runtime">
                  {t('workspace.containerManagement.runtime.form.runtime.label')}
                </Label>
                <Select
                  value={formState.runtime}
                  onValueChange={(value) =>
                    setFormState((current) =>
                      current ? { ...current, runtime: value } : current
                    )
                  }
                  disabled={isLoadingImages}
                >
                  <SelectTrigger id="runtime" className="h-10">
                    <SelectValue placeholder={
                      isLoadingImages
                        ? t('workspace.containerManagement.runtime.form.runtime.loading')
                        : t('workspace.containerManagement.runtime.form.runtime.placeholder')
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {containerImagesData?.images.map((image) => (
                      <SelectItem key={image.id} value={image.id}>
                        <div className="flex items-center gap-2">
                          <span>{image.icon}</span>
                          <span>{t(`workspace.containerManagement.runtime.environments.${image.id}.label`, image.name)}</span>
                          {image.recommended && (
                            <span className="ml-1 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                              {t('workspace.containerManagement.runtime.form.runtime.recommended')}
                            </span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {containerImagesData && formState.runtime && (
                  <p className="text-xs text-muted-foreground">
                    {(() => {
                      const img = containerImagesData.images.find(img => img.id === formState.runtime);
                      return img ? t(`workspace.containerManagement.runtime.environments.${img.id}.description`, img.description) : '';
                    })()}
                  </p>
                )}
              </div>
              {formState.provisioner === 'kubernetes' && formState.runtimeResources && (
                <div className="space-y-4 rounded-lg border border-border p-4">
                  <div className="space-y-1">
                    <Label>
                      {t('workspace.containerManagement.runtime.resources.title')}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.containerManagement.runtime.resources.description')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.containerManagement.runtime.resources.scope')}
                    </p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-3">
                      <Label>
                        {t('workspace.containerManagement.runtime.resources.requests.title')}
                      </Label>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.resources.fields.cpu')}
                          </Label>
                          <Input
                            value={formState.runtimeResources.requests.cpu}
                            onChange={(e) =>
                              setFormState((current) =>
                                current && current.runtimeResources
                                  ? {
                                      ...current,
                                      runtimeResources: {
                                        ...current.runtimeResources,
                                        requests: {
                                          ...current.runtimeResources.requests,
                                          cpu: e.target.value,
                                        },
                                      },
                                    }
                                  : current
                              )
                            }
                            placeholder="500m"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.resources.fields.memory')}
                          </Label>
                          <Input
                            value={formState.runtimeResources.requests.memory}
                            onChange={(e) =>
                              setFormState((current) =>
                                current && current.runtimeResources
                                  ? {
                                      ...current,
                                      runtimeResources: {
                                        ...current.runtimeResources,
                                        requests: {
                                          ...current.runtimeResources.requests,
                                          memory: e.target.value,
                                        },
                                      },
                                    }
                                  : current
                              )
                            }
                            placeholder="2Gi"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <Label>
                        {t('workspace.containerManagement.runtime.resources.limits.title')}
                      </Label>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.resources.fields.cpu')}
                          </Label>
                          <Input
                            value={formState.runtimeResources.limits.cpu}
                            onChange={(e) =>
                              setFormState((current) =>
                                current && current.runtimeResources
                                  ? {
                                      ...current,
                                      runtimeResources: {
                                        ...current.runtimeResources,
                                        limits: {
                                          ...current.runtimeResources.limits,
                                          cpu: e.target.value,
                                        },
                                      },
                                    }
                                  : current
                              )
                            }
                            placeholder="2000m"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.resources.fields.memory')}
                          </Label>
                          <Input
                            value={formState.runtimeResources.limits.memory}
                            onChange={(e) =>
                              setFormState((current) =>
                                current && current.runtimeResources
                                  ? {
                                      ...current,
                                      runtimeResources: {
                                        ...current.runtimeResources,
                                        limits: {
                                          ...current.runtimeResources.limits,
                                          memory: e.target.value,
                                        },
                                      },
                                    }
                                  : current
                              )
                            }
                            placeholder="4Gi"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="setupScript">
                  {t('workspace.containerManagement.runtime.form.setupScript.label')}
                </Label>
                <Textarea
                  id="setupScript"
                  placeholder={t('workspace.containerManagement.runtime.form.setupScript.placeholder')}
                  value={formState.setupScript}
                  onChange={(e) =>
                    setFormState((current) =>
                      current ? { ...current, setupScript: e.target.value } : current
                    )
                  }
                  rows={4}
                  className="font-mono"
                />
                <p className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.runtime.form.setupScript.description')}
                </p>
              </div>

              <div className="space-y-2">
                <Label>{t('workspace.containerManagement.runtime.envVars.label')}</Label>
                {formState.envVars.map((envVar) => (
                  <div key={envVar.id} className="flex items-center gap-2">
                    <Input
                      placeholder={t('workspace.containerManagement.runtime.envVars.keyPlaceholder')}
                      value={envVar.key}
                      onChange={(e) => updateEnvVar(envVar.id, 'key', e.target.value)}
                      className="flex-1"
                    />
                    <Input
                      placeholder={t('workspace.containerManagement.runtime.envVars.valuePlaceholder')}
                      value={envVar.value}
                      onChange={(e) => updateEnvVar(envVar.id, 'value', e.target.value)}
                      className="flex-1"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => removeEnvVar(envVar.id)}
                      className="border-border text-muted-foreground hover:bg-muted"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}

                <Button
                  variant="outline"
                  onClick={addEnvVar}
                  className="w-full border-border text-muted-foreground hover:bg-muted"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.containerManagement.runtime.envVars.add')}
                </Button>
              </div>

              {formState.provisioner === 'docker' ? (
                <>
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Network className="h-4 w-4" />
                      System Ports
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Default Docker ports managed by the platform.
                    </p>

                    {formState.systemPortMappings.map((portMapping) => (
                      <div
                        key={portMapping.id}
                        className="grid grid-cols-12 items-end gap-2 rounded-lg border border-border p-3 opacity-70"
                      >
                        <div className="col-span-2">
                          <Label className="text-xs text-muted-foreground">Name</Label>
                          <Input value={portMapping.name} disabled />
                        </div>
                        <div className="col-span-3">
                          <Label className="text-xs text-muted-foreground">Container Port</Label>
                          <Input type="number" value={portMapping.containerPort} disabled />
                        </div>
                        <div className="col-span-3">
                          <Label className="text-xs text-muted-foreground">Host Port</Label>
                          <Input type="number" value={portMapping.hostPort ?? ''} disabled />
                        </div>
                        <div className="col-span-2">
                          <Label className="text-xs text-muted-foreground">Protocol</Label>
                          <Input value={portMapping.protocol} disabled />
                        </div>
                        <div className="col-span-2">
                          <Label className="text-xs text-muted-foreground">Description</Label>
                          <Input value={portMapping.description || ''} disabled />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Network className="h-4 w-4" />
                      {t('workspace.containerManagement.runtime.portMappings.label')}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.containerManagement.runtime.portMappings.description')}
                    </p>

                    {formState.portMappings.map((portMapping) => (
                      <div
                        key={portMapping.id}
                        className="grid grid-cols-12 items-end gap-2 rounded-lg border border-border p-3"
                      >
                        <div className="col-span-3">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.portMappings.fields.containerPort.label')}
                          </Label>
                          <Input
                            type="number"
                            placeholder={t('workspace.containerManagement.runtime.portMappings.fields.containerPort.placeholder')}
                            value={portMapping.containerPort}
                            onChange={(e) =>
                              updatePortMapping(portMapping.id, 'containerPort', e.target.value)
                            }
                            min={1}
                            max={65535}
                          />
                        </div>
                        <div className="col-span-3">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.portMappings.fields.hostPort.label')}
                          </Label>
                          <Input
                            type="number"
                            placeholder={t('workspace.containerManagement.runtime.portMappings.fields.hostPort.placeholder')}
                            value={portMapping.hostPort ?? ''}
                            onChange={(e) =>
                              updatePortMapping(portMapping.id, 'hostPort', e.target.value)
                            }
                            min={1}
                            max={65535}
                          />
                        </div>
                        <div className="col-span-2">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.portMappings.fields.protocol.label')}
                          </Label>
                          <Select
                            value={portMapping.protocol}
                            onValueChange={(value) =>
                              updatePortMapping(portMapping.id, 'protocol', value)
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="tcp">
                                {t('workspace.containerManagement.runtime.portMappings.fields.protocol.options.tcp')}
                              </SelectItem>
                              <SelectItem value="udp">
                                {t('workspace.containerManagement.runtime.portMappings.fields.protocol.options.udp')}
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="col-span-3">
                          <Label className="text-xs text-muted-foreground">
                            {t('workspace.containerManagement.runtime.portMappings.fields.description.label')}
                          </Label>
                          <Input
                            placeholder={t('workspace.containerManagement.runtime.portMappings.fields.description.placeholder')}
                            value={portMapping.description || ''}
                            onChange={(e) =>
                              updatePortMapping(portMapping.id, 'description', e.target.value)
                            }
                          />
                        </div>
                        <div className="col-span-1">
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => removePortMapping(portMapping.id)}
                            className="border-border text-muted-foreground hover:bg-muted"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <Button
                    variant="outline"
                    onClick={addPortMapping}
                    className="w-full border-border text-muted-foreground hover:bg-muted"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    {t('workspace.containerManagement.runtime.portMappings.add')}
                  </Button>

                  <div className="space-y-1 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                    <p>{t('workspace.containerManagement.runtime.portMappings.hints.autoAssign')}</p>
                    <p>{t('workspace.containerManagement.runtime.portMappings.hints.defaultPort')}</p>
                    <p>{t('workspace.containerManagement.runtime.portMappings.hints.reservedPorts')}</p>
                  </div>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Workspace-level port exposure is not supported for Kubernetes workspaces.
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('workspace.containerManagement.runtime.status.empty')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default RuntimeSettingsView;
