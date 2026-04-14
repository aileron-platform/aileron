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

export interface TemplateInstallDialogProps {
  open: boolean;
  template: Template | null;
  workspaces: TemplateWorkspaceTarget[];
  onOpenChange: (open: boolean) => void;
  onInstall: (workspaceId: string, options: TemplateInstallOptions) => void;
}

const defaultOptions: TemplateInstallOptions = {
  mcp: true,
  slashCommands: true,
  hooks: true,
  claudeMd: true,
  subAgents: true,
  outputStyles: true,
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
  const { t } = useI18n();

  const optionLabels: Array<{
    key: keyof TemplateInstallOptions;
    label: string;
    description: string;
  }> = useMemo(
    () => [
      {
        key: 'mcp',
        label: t('template.center.install.options.mcp.label'),
        description: t('template.center.install.options.mcp.description'),
      },
      {
        key: 'slashCommands',
        label: t('template.center.install.options.slashCommands.label'),
        description: t('template.center.install.options.slashCommands.description'),
      },
      {
        key: 'hooks',
        label: t('template.center.install.options.hooks.label'),
        description: t('template.center.install.options.hooks.description'),
      },
      {
        key: 'claudeMd',
        label: t('template.center.install.options.claudeMd.label'),
        description: t('template.center.install.options.claudeMd.description'),
      },
      {
        key: 'subAgents',
        label: t('template.center.install.options.subAgents.label'),
        description: t('template.center.install.options.subAgents.description'),
      },
      {
        key: 'outputStyles',
        label: t('template.center.install.options.outputStyles.label'),
        description: t('template.center.install.options.outputStyles.description'),
      },
      {
        key: 'scripts',
        label: t('template.center.install.options.scripts.label'),
        description: t('template.center.install.options.scripts.description'),
      },
      {
        key: 'skills',
        label: t('template.center.install.options.skills.label'),
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
        case 'slashCommands':
          return flags.hasSlashCommands;
        case 'hooks':
          return flags.hasHooks;
        case 'claudeMd':
          return flags.hasClaudeMd;
        case 'subAgents':
          return flags.hasSubAgents;
        case 'outputStyles':
          return flags.hasOutputStyles;
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
      slashCommands: flags.hasSlashCommands,
      hooks: flags.hasHooks,
      claudeMd: flags.hasClaudeMd,
      subAgents: flags.hasSubAgents,
      scripts: flags.hasScripts,
      skills: flags.hasSkills,
    });
  }, [template]);

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
          <DialogTitle>
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
                <SelectValue placeholder={t('template.center.install.workspace.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {workspaces.map(workspace => (
                  <SelectItem key={workspace.id} value={workspace.id}>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium text-foreground">{workspace.name}</span>
                      {workspace.description && (
                        <span className="text-xs text-muted-foreground">{workspace.description}</span>
                      )}
                    </div>
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
