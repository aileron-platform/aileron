import React, { useEffect } from 'react';
import { ArrowLeft, Network, Plus, Settings, X } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useContainerImages } from '@/shared/hooks/useContainerImages';
import { RuntimeConfigForm } from '../../types';

export interface RuntimeHelperActions {
  addEnvVar: () => void;
  updateEnvVar: (id: string, patch: Partial<{ key: string; value: string }>) => void;
  removeEnvVar: (id: string) => void;
  addPortMapping: () => void;
  updatePortMapping: (id: string, patch: Partial<{ containerPort: number | ''; hostPort: number | ''; protocol: 'http' | 'https' | 'tcp' }>) => void;
  removePortMapping: (id: string) => void;
}

interface RuntimeConfigStepProps {
  data: RuntimeConfigForm;
  onChange: (next: RuntimeConfigForm) => void;
  kubernetesNamespaceOptions: string[];
  helpers: RuntimeHelperActions;
  onPrevious: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const PROTOCOL_OPTIONS: Array<'http' | 'https' | 'tcp'> = ['http', 'https', 'tcp'];

export const RuntimeConfigStep: React.FC<RuntimeConfigStepProps> = ({
  data,
  onChange,
  kubernetesNamespaceOptions,
  helpers,
  onPrevious,
  onSubmit,
  isSubmitting,
  t,
}) => {
  // 載入容器映像列表
  const { data: containerImagesData, isLoading: isLoadingImages } = useContainerImages();

  // 當映像載入完成且 runtime 為空時，設置預設值
  useEffect(() => {
    if (containerImagesData && !data.runtime && containerImagesData.defaultImageId) {
      onChange({ ...data, runtime: containerImagesData.defaultImageId });
    }
  }, [containerImagesData, data, onChange]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSubmitting) {
      onSubmit();
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <div className="flex items-center justify-center gap-2 text-primary">
          <Settings className="h-8 w-8" />
          <h1 className="text-2xl font-semibold text-foreground">
            {t('workspace.wizard.steps.runtimeConfig.title')}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('workspace.wizard.steps.runtimeConfig.subtitle', { current: 2, total: 4 })}
        </p>
      </div>

      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: '50%' }} />
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Settings className="h-5 w-5" />
            {t('workspace.wizard.steps.runtimeConfig.cardTitle')}
          </CardTitle>
          <CardDescription>{t('workspace.wizard.steps.runtimeConfig.cardDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {data.provisioner === 'kubernetes' && (
              <div className="space-y-2">
                <Label htmlFor="wizard-target-namespace-select" className="text-sm font-medium">
                  {t('workspace.wizard.steps.runtimeConfig.fields.targetNamespace.label')}
                </Label>
                <Select
                  value={data.targetNamespace ?? kubernetesNamespaceOptions[0] ?? 'default'}
                  onValueChange={(value) => onChange({ ...data, targetNamespace: value })}
                  disabled={isSubmitting}
                >
                  <SelectTrigger id="wizard-target-namespace-select" className="h-11">
                    <SelectValue
                      placeholder={t('workspace.wizard.steps.runtimeConfig.fields.targetNamespace.placeholder')}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {kubernetesNamespaceOptions.map((namespace) => (
                      <SelectItem key={namespace} value={namespace}>
                        {namespace}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {t('workspace.wizard.steps.runtimeConfig.fields.targetNamespace.helper')}
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="wizard-runtime-select" className="text-sm font-medium">
                {t('workspace.wizard.steps.runtimeConfig.fields.runtime.label')}
              </Label>
              <Select
                value={data.runtime}
                onValueChange={(value) => onChange({ ...data, runtime: value })}
                disabled={isSubmitting || isLoadingImages}
              >
                <SelectTrigger id="wizard-runtime-select" className="h-11">
                  <SelectValue placeholder={
                    isLoadingImages
                      ? t('workspace.wizard.steps.runtimeConfig.fields.runtime.loading')
                      : t('workspace.wizard.steps.runtimeConfig.fields.runtime.placeholder')
                  } />
                </SelectTrigger>
                <SelectContent>
                  {containerImagesData?.images.map((image) => (
                    <SelectItem key={image.id} value={image.id}>
                      <div className="flex items-center gap-2">
                        <span>{t(`workspace.containerManagement.runtime.environments.${image.id}.label`, image.name)}</span>
                        {image.recommended && (
                          <span className="ml-1 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                            {t('workspace.wizard.steps.runtimeConfig.fields.runtime.recommended')}
                          </span>
                        )}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {containerImagesData && data.runtime && (
                <p className="text-xs text-muted-foreground">
                  {(() => {
                  const img = containerImagesData.images.find(img => img.id === data.runtime);
                  return img ? t(`workspace.containerManagement.runtime.environments.${img.id}.description`, img.description) : '';
                })()}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="wizard-runtime-script" className="text-sm font-medium">
                {t('workspace.wizard.steps.runtimeConfig.fields.setupScript.label')}
                <span className="ml-1 text-muted-foreground">{t('workspace.wizard.steps.runtimeConfig.optional')}</span>
              </Label>
              <Textarea
                id="wizard-runtime-script"
                value={data.setupScript}
                onChange={(event) => onChange({ ...data, setupScript: event.target.value })}
                placeholder={t('workspace.wizard.steps.runtimeConfig.fields.setupScript.placeholder')}
                rows={4}
                disabled={isSubmitting}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.runtimeConfig.fields.setupScript.helper')}
              </p>
            </div>

            <div className="space-y-3">
              <Label className="text-sm font-medium">
                {t('workspace.wizard.steps.runtimeConfig.fields.envVars.label')}
                <span className="ml-1 text-muted-foreground">{t('workspace.wizard.steps.runtimeConfig.optional')}</span>
              </Label>

              {data.envVars.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  {t('workspace.wizard.steps.runtimeConfig.fields.envVars.empty')}
                </p>
              )}

              {data.envVars.map((envVar) => (
                <div key={envVar.id} className="flex items-center gap-2">
                  <Input
                    value={envVar.key}
                    onChange={(event) => helpers.updateEnvVar(envVar.id, { key: event.target.value })}
                    placeholder={t('workspace.wizard.steps.runtimeConfig.fields.envVars.namePlaceholder')}
                    disabled={isSubmitting}
                    className="flex-1"
                  />
                  <Input
                    value={envVar.value}
                    onChange={(event) => helpers.updateEnvVar(envVar.id, { value: event.target.value })}
                    placeholder={t('workspace.wizard.steps.runtimeConfig.fields.envVars.valuePlaceholder')}
                    disabled={isSubmitting}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => helpers.removeEnvVar(envVar.id)}
                    disabled={isSubmitting}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}

              <Button
                type="button"
                variant="outline"
                onClick={helpers.addEnvVar}
                disabled={isSubmitting}
                className="w-full"
              >
                <Plus className="mr-2 h-4 w-4" />
                {t('workspace.wizard.steps.runtimeConfig.fields.envVars.add')}
              </Button>
            </div>

            {data.provisioner === 'docker' ? (
              <div className="space-y-3">
                <Label className="flex items-center gap-2 text-sm font-medium">
                  <Network className="h-4 w-4" />
                  {t('workspace.wizard.steps.runtimeConfig.fields.portMappings.label')}
                  <span className="ml-1 text-muted-foreground">{t('workspace.wizard.steps.runtimeConfig.optional')}</span>
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t('workspace.wizard.steps.runtimeConfig.fields.portMappings.helper')}
                </p>

                {data.portMappings.map((mapping) => (
                  <div key={mapping.id} className="grid grid-cols-12 items-end gap-2 rounded-lg border p-3">
                    <div className="col-span-4">
                      <Label className="text-xs">{t('workspace.wizard.steps.runtimeConfig.fields.portMappings.containerPort')}</Label>
                    <Input
                      type="number"
                      value={mapping.containerPort === '' ? '' : mapping.containerPort}
                      onChange={(event) => helpers.updatePortMapping(mapping.id, { containerPort: event.target.value === '' ? '' : Number(event.target.value) })}
                      placeholder={t('workspace.wizard.steps.runtimeConfig.fields.portMappings.containerPlaceholder')}
                      disabled={isSubmitting}
                      min={1}
                      max={65535}
                    />
                  </div>
                    <div className="col-span-4">
                      <Label className="text-xs">{t('workspace.wizard.steps.runtimeConfig.fields.portMappings.hostPort')}</Label>
                      <Input
                        type="number"
                        value={mapping.hostPort === '' ? '' : mapping.hostPort}
                        onChange={(event) => helpers.updatePortMapping(mapping.id, { hostPort: event.target.value === '' ? '' : Number(event.target.value) })}
                        placeholder={t('workspace.wizard.steps.runtimeConfig.fields.portMappings.hostPlaceholder')}
                        disabled={isSubmitting}
                        min={1}
                        max={65535}
                      />
                    </div>
                    <div className="col-span-3">
                      <Label className="text-xs">{t('workspace.wizard.steps.runtimeConfig.fields.portMappings.protocol')}</Label>
                      <Select
                        value={mapping.protocol}
                        onValueChange={(value) => helpers.updatePortMapping(mapping.id, { protocol: value as typeof mapping.protocol })}
                        disabled={isSubmitting}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {PROTOCOL_OPTIONS.map((protocol) => (
                            <SelectItem key={protocol} value={protocol}>
                              {t(`workspace.wizard.steps.runtimeConfig.fields.portMappings.protocolOptions.${protocol}`)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => helpers.removePortMapping(mapping.id)}
                        disabled={isSubmitting}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}

                <Button
                  type="button"
                  variant="outline"
                  onClick={helpers.addPortMapping}
                  disabled={isSubmitting}
                  className="w-full"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.wizard.steps.runtimeConfig.fields.portMappings.add')}
                </Button>

                <div className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
                  <p>{t('workspace.wizard.steps.runtimeConfig.notes.autoAssign')}</p>
                  <p>{t('workspace.wizard.steps.runtimeConfig.notes.reserved')}</p>
                  <p>{t('workspace.wizard.steps.runtimeConfig.notes.examples')}</p>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                Workspace-level port exposure is only available for Docker workspaces.
              </div>
            )}

            <div className="flex items-center justify-between pt-4">
              <Button type="button" variant="outline" onClick={onPrevious} disabled={isSubmitting} className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                {t('workspace.wizard.buttons.previous')}
              </Button>
              <Button type="submit" disabled={isSubmitting} className="bg-primary text-primary-foreground">
                {isSubmitting ? t('workspace.wizard.buttons.processing') : t('workspace.wizard.buttons.next')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default RuntimeConfigStep;
