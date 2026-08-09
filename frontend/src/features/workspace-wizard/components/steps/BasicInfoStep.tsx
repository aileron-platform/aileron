import React from 'react';
import { Check, ChevronRight, Folder, GitBranch, TriangleAlert } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { cn } from '@/shared/utils/cn';
import type { AgenticTool, BasicInfoForm } from '../../model/workspaceWizardTypes';

interface BasicInfoStepProps {
  data: BasicInfoForm;
  onChange: (next: BasicInfoForm) => void;
  onCancel: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const agenticToolOptions: Array<{
  value: AgenticTool;
  labelKey: string;
  descriptionKey: string;
  iconSrc: string;
}> = [
  {
    value: 'claude-code',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.options.claudeCode',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.claudeCode',
    iconSrc: '/marketplace/providers/claude-code.png',
  },
  {
    value: 'codex',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.options.codex',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.codex',
    iconSrc: '/marketplace/providers/codex.png',
  },
  {
    value: 'opencode',
    labelKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.options.opencode',
    descriptionKey: 'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.opencode',
    iconSrc: '/marketplace/providers/opencode.png',
  },
];

const BasicInfoStep: React.FC<BasicInfoStepProps> = ({
  data,
  onChange,
  onCancel,
  onSubmit,
  isSubmitting,
  t,
}) => {
  const updateField = (field: 'name' | 'description', value: string) => {
    onChange({ ...data, [field]: value });
  };

  const toggleAgenticTool = (tool: AgenticTool) => {
    const selected = data.agenticTools.includes(tool);
    const nextTools = selected
      ? data.agenticTools.filter((item) => item !== tool)
      : [...data.agenticTools, tool];

    if (nextTools.length === 0) {
      return;
    }

    onChange({ ...data, agenticTools: nextTools });
  };

  const isValid =
    data.name.trim().length > 0 &&
    data.description.trim().length > 0 &&
    data.agenticTools.length > 0;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSubmitting && isValid) {
      onSubmit();
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <div className="flex items-center justify-center gap-2 text-primary">
          <Folder className="h-8 w-8" />
          <h1 className="text-2xl font-semibold text-foreground">
            {t('workspace.wizard.steps.basicInfo.title')}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('workspace.wizard.steps.basicInfo.subtitle', { current: 1, total: 3 })}
        </p>
      </div>

      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: '33.3333%' }} />
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <GitBranch className="h-5 w-5" />
            {t('workspace.wizard.steps.basicInfo.cardTitle')}
          </CardTitle>
          <CardDescription>{t('workspace.wizard.steps.basicInfo.cardDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="wizard-basic-name" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.name.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <Input
                id="wizard-basic-name"
                value={data.name}
                onChange={(event) => updateField('name', event.target.value)}
                placeholder={t('workspace.wizard.steps.basicInfo.fields.name.placeholder')}
                disabled={isSubmitting}
                required
              />
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.name.helper')}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="wizard-basic-description" className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.description.label')}
                <span className="ml-1 text-destructive">*</span>
              </Label>
              <Textarea
                id="wizard-basic-description"
                value={data.description}
                onChange={(event) => updateField('description', event.target.value)}
                placeholder={t('workspace.wizard.steps.basicInfo.fields.description.placeholder')}
                disabled={isSubmitting}
                rows={4}
                required
                className="resize-none"
              />
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.description.helper')}
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">
                {t('workspace.wizard.steps.basicInfo.fields.agenticTool.label')}
              </Label>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {agenticToolOptions.map((option) => {
                  const isSelected = data.agenticTools.includes(option.value);

                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => toggleAgenticTool(option.value)}
                      disabled={isSubmitting}
                      className={cn(
                        'group flex min-h-[132px] flex-col rounded-lg border bg-card p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
                        isSelected
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-border hover:border-primary/60 hover:bg-accent/40'
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-md border border-border bg-background">
                            <img src={option.iconSrc} alt="" className="h-7 w-7 object-contain" />
                          </span>
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-foreground">
                              {t(option.labelKey)}
                            </div>
                            {isSelected && (
                              <div className="mt-1 inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                                <Check className="h-3 w-3" />
                                {t('workspace.wizard.steps.basicInfo.fields.agenticTool.selected')}
                              </div>
                            )}
                          </div>
                        </div>
                        <ChevronRight
                          className={cn(
                            'mt-1 h-4 w-4 text-muted-foreground transition-colors',
                            isSelected ? 'text-primary' : 'group-hover:text-primary'
                          )}
                        />
                      </div>
                      <p className="mt-3 text-xs leading-5 text-muted-foreground">
                        {t(option.descriptionKey)}
                      </p>
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.basicInfo.fields.agenticTool.helper')}
              </p>
            </div>

            {!isValid && (
              <Alert variant="warning">
                <TriangleAlert className="h-4 w-4" />
                <AlertDescription>
                  {t('workspace.wizard.validation.basicInfo')}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex items-center justify-between pt-4">
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                {t('workspace.wizard.buttons.cancel')}
              </Button>
              <Button type="submit" disabled={!isValid || isSubmitting} className={cn('bg-primary text-primary-foreground')}>
                {isSubmitting ? t('workspace.wizard.buttons.processing') : t('workspace.wizard.buttons.next')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default BasicInfoStep;
