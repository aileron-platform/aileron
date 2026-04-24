import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { buildFeatureFlags } from '@/features/template-management/utils/templateSelectors';
import type {
  Template,
  TemplateInstallOptions,
  TemplateWorkspaceTarget,
} from '@/shared/types/templates';
import { useI18n } from '@/shared/hooks/useI18n';
import { getTemplateCompilePreview, type TemplateCompilePreview } from '@/shared/services/templateApi';
import { Download } from 'lucide-react';

export interface TemplateInstallDialogProps {
  open: boolean;
  template: Template | null;
  workspaces: TemplateWorkspaceTarget[];
  onOpenChange: (open: boolean) => void;
  onInstall: (workspaceId: string, options: TemplateInstallOptions) => void;
}

const defaultOptions: TemplateInstallOptions = {
  mcp: true,
  commands: true,
  hooks: true,
  agentsMd: true,
  agents: true,
  outputStyle: true,
  scripts: true,
  skills: true,
};

export const TemplateInstallDialog: React.FC<TemplateInstallDialogProps> = ({
  open,
  template,
  workspaces,
  onOpenChange,
  onInstall,
}) => {
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [options, setOptions] = useState<TemplateInstallOptions>(defaultOptions);
  const [preview, setPreview] = useState<TemplateCompilePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const { t } = useI18n();

  const selectedWorkspaceInfo = useMemo(
    () => workspaces.find(item => item.id === selectedWorkspace),
    [selectedWorkspace, workspaces],
  );

  const optionLabels: Array<{
    key: keyof TemplateInstallOptions;
    label: string;
    description: string;
  }> = useMemo(
    () => [
      {
        key: 'mcp',
        label: t('template.common.features.mcp'),
        description: t('template.center.install.options.mcp.description'),
      },
      {
        key: 'commands',
        label: t('template.common.features.commands'),
        description: t('template.center.install.options.commands.description'),
      },
      {
        key: 'hooks',
        label: t('template.common.features.hooks'),
        description: t('template.center.install.options.hooks.description'),
      },
      {
        key: 'agentsMd',
        label: t('template.common.features.agentsMd'),
        description: t('template.center.install.options.agentsMd.description'),
      },
      {
        key: 'agents',
        label: t('template.common.features.agents'),
        description: t('template.center.install.options.agents.description'),
      },
      {
        key: 'outputStyle',
        label: t('template.common.features.outputStyle'),
        description: t('template.center.install.options.outputStyle.description'),
      },
      {
        key: 'scripts',
        label: t('template.common.features.scripts'),
        description: t('template.center.install.options.scripts.description'),
      },
      {
        key: 'skills',
        label: t('template.common.features.skills'),
        description: t('template.center.install.options.skills.description'),
      },
    ],
    [t],
  );

  const availableOptions = useMemo(() => {
    if (!template) {
      return optionLabels;
    }
    const flags = buildFeatureFlags(template);
    return optionLabels.filter(item => {
      switch (item.key) {
        case 'mcp':
          return flags.hasMcp;
        case 'commands':
          return flags.hasCommands;
        case 'hooks':
          return flags.hasHooks;
        case 'agentsMd':
          return flags.hasAgentsMd;
        case 'agents':
          return flags.hasAgents;
        case 'outputStyle':
          return flags.hasOutputStyle;
        case 'scripts':
          return flags.hasScripts;
        case 'skills':
          return flags.hasSkills;
        default:
          return false;
      }
    });
  }, [template, optionLabels]);

  useEffect(() => {
    if (open) {
      if (workspaces.length > 0) {
        setSelectedWorkspace(workspaces[0].id);
      } else {
        setSelectedWorkspace('');
      }
      setOptions(prev => ({ ...defaultOptions, ...prev }));
    } else {
      setSelectedWorkspace('');
    }
  }, [open, workspaces]);

  useEffect(() => {
    if (!template) {
      return;
    }
    const flags = buildFeatureFlags(template);
    setOptions({
      mcp: flags.hasMcp,
      commands: flags.hasCommands,
      hooks: flags.hasHooks,
      agentsMd: flags.hasAgentsMd,
      agents: flags.hasAgents,
      outputStyle: flags.hasOutputStyle,
      scripts: flags.hasScripts,
      skills: flags.hasSkills,
    });
  }, [template]);

  useEffect(() => {
    let active = true;
    const loadPreview = async () => {
      if (!open || !template || !selectedWorkspaceInfo?.cliType) {
        if (active) {
          setPreview(null);
          setPreviewError(null);
        }
        return;
      }
      try {
        const result = await getTemplateCompilePreview(template.id, selectedWorkspaceInfo.cliType);
        if (!active) return;
        setPreview(result);
        setPreviewError(null);
      } catch (error) {
        if (!active) return;
        setPreview(null);
        setPreviewError(error instanceof Error ? error.message : t('template.center.install.preview.loadFailed'));
      }
    };

    void loadPreview();
    return () => {
      active = false;
    };
  }, [open, selectedWorkspaceInfo?.cliType, selectedWorkspace, t, template]);

  const handleToggle = (key: keyof TemplateInstallOptions) => {
    setOptions(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleInstall = () => {
    if (!template || !selectedWorkspace) {
      return;
    }
    onInstall(selectedWorkspace, options);
  };

  const workspaceLabel = (workspaceId: string) => {
    const workspace = workspaces.find(item => item.id === workspaceId);
    if (!workspace) return t('template.center.install.workspace.placeholder');
    return workspace.name;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-primary" />
            {t('template.center.install.title', { name: template?.name ?? '' })}
          </DialogTitle>
          <DialogDescription>{t('template.center.install.description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">
              {t('template.center.install.workspace.label')}
            </p>
            <Select value={selectedWorkspace} onValueChange={setSelectedWorkspace}>
              <SelectTrigger>
              {selectedWorkspaceInfo ? (
                  <span className="flex min-w-0 flex-col items-start justify-center text-left leading-tight">
                    <span className="block w-full truncate text-sm font-medium text-foreground">
                      {selectedWorkspaceInfo.name}
                    </span>
                    {selectedWorkspaceInfo.description && (
                      <span className="mt-0.5 block w-full truncate text-xs text-muted-foreground">
                        {selectedWorkspaceInfo.description}
                      </span>
                    )}
                  </span>
                ) : (
                  <SelectValue placeholder={t('template.center.install.workspace.placeholder')} />
                )}
              </SelectTrigger>
              <SelectContent>
                {workspaces.map(workspace => (
                  <SelectItem key={workspace.id} value={workspace.id}>
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-sm font-medium text-foreground">
                        {workspace.name}
                      </span>
                      {workspace.description && (
                        <span className="truncate text-xs text-muted-foreground">
                          {workspace.description}
                        </span>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground">
                {t('template.center.install.components.label')}
              </p>
              <Badge variant="outline" className="text-xs">
                {t('template.center.install.components.selectedCount', {
                  selected: availableOptions.filter(item => options[item.key]).length,
                  total: availableOptions.length,
                })}
              </Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {availableOptions.map(item => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => handleToggle(item.key)}
                  className={`rounded border px-3 py-2 text-left text-sm transition-colors ${
                    options[item.key]
                      ? 'border-primary/80 bg-primary/5 text-foreground'
                      : 'border-border bg-background text-muted-foreground hover:bg-muted/40'
                  }`}
                >
                  <p className="font-medium">{item.label}</p>
                  <p className="text-xs mt-1 text-muted-foreground">{item.description}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground">
                {t('template.center.install.preview.title')}
              </p>
              {preview && (
                <Badge variant="outline" className="text-xs">
                  {t('template.center.install.preview.summary', {
                    files: preview.files.length,
                    warnings: preview.warnings.length,
                    unsupported: preview.unsupported.length,
                    degradation: preview.degradationNotes.length,
                  })}
                </Badge>
              )}
            </div>

            {previewError ? (
              <div className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                {previewError}
              </div>
            ) : preview ? (
              <div className="space-y-2 rounded border border-border bg-muted/20 p-3 text-xs">
                <div className="font-medium text-foreground">
                  {t('template.center.install.preview.target', {
                    target: selectedWorkspaceInfo?.cliType
                      ? t(`template.common.targets.${selectedWorkspaceInfo.cliType === 'claude-code' ? 'claudeCode' : selectedWorkspaceInfo.cliType}`)
                      : '',
                  })}
                </div>
                {preview.warnings.length > 0 && (
                  <div>
                    <div className="font-medium text-foreground">{t('template.center.install.preview.sections.warnings')}</div>
                    {preview.warnings.map((item, index) => (
                      <div key={`${item.feature}-${index}`} className="text-muted-foreground">
                        {item.message}
                      </div>
                    ))}
                  </div>
                )}
                {preview.unsupported.length > 0 && (
                  <div>
                    <div className="font-medium text-foreground">{t('template.center.install.preview.sections.unsupported')}</div>
                    {preview.unsupported.map((item, index) => (
                      <div key={`${item.feature}-${index}`} className="text-muted-foreground">
                        {item.message}
                      </div>
                    ))}
                  </div>
                )}
                {preview.degradationNotes.length > 0 && (
                  <div>
                    <div className="font-medium text-foreground">{t('template.center.install.preview.sections.degradation')}</div>
                    {preview.degradationNotes.map((item, index) => (
                      <div key={`${item.feature}-${index}`} className="text-muted-foreground">
                        {item.message}
                      </div>
                    ))}
                  </div>
                )}
                {preview.warnings.length === 0 &&
                  preview.unsupported.length === 0 &&
                  preview.degradationNotes.length === 0 && (
                    <div className="text-muted-foreground">
                      {t('template.center.install.preview.none')}
                    </div>
                  )}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">
                {t('template.center.install.preview.loading')}
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('template.center.install.actions.cancel')}
          </Button>
          <Button onClick={handleInstall} disabled={!template || !selectedWorkspace}>
            {t('template.center.install.actions.confirm', {
              workspace: workspaceLabel(selectedWorkspace),
            })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TemplateInstallDialog;
