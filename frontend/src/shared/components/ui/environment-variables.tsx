import React, { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Plus, Trash2 } from 'lucide-react';
import { ClaudeCodeEnvironmentVariable } from '@/shared/types/user';
import { useI18n } from '@/shared/hooks/useI18n';

interface EnvironmentVariablesProps {
  value: ClaudeCodeEnvironmentVariable[];
  onChange: (variables: ClaudeCodeEnvironmentVariable[]) => void;
  title?: string;
  description?: string;
}

export const EnvironmentVariables: React.FC<EnvironmentVariablesProps> = ({
  value,
  onChange,
  title,
  description
}) => {
  const { t } = useI18n();

  const resolvedTitle =
    title ?? t('pages.settings.sections.claudeCode.environmentVariables.title');
  const resolvedDescription =
    description ?? t('pages.settings.sections.claudeCode.environmentVariables.description');

  const addVariable = () => {
    const newVariable: ClaudeCodeEnvironmentVariable = {
      key: '',
      value: ''
    };
    onChange([...value, newVariable]);
  };

  const removeVariable = (index: number) => {
    const updatedVariables = value.filter((_, i) => i !== index);
    onChange(updatedVariables);
  };

  const updateVariable = (index: number, field: keyof ClaudeCodeEnvironmentVariable, newValue: string) => {
    const updatedVariables = value.map((variable, i) => {
      if (i === index) {
        return { ...variable, [field]: newValue };
      }
      return variable;
    });
    onChange(updatedVariables);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{resolvedTitle}</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addVariable}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            {t('pages.settings.sections.claudeCode.environmentVariables.addButton')}
          </Button>
        </CardTitle>
        {resolvedDescription && (
          <p className="text-sm text-muted-foreground">{resolvedDescription}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {value.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>{t('pages.settings.sections.claudeCode.environmentVariables.emptyState.title')}</p>
            <p className="text-sm">
              {t('pages.settings.sections.claudeCode.environmentVariables.emptyState.description')}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {value.map((variable, index) => (
              <div key={index} className="flex gap-3 items-center">
                <div className="grid grid-cols-2 gap-3 flex-1">
                  <div className="space-y-1">
                    {index === 0 && (
                      <Label className="text-xs text-muted-foreground">
                        {t('pages.settings.sections.claudeCode.environmentVariables.keyLabel')}
                      </Label>
                    )}
                    <Input
                      placeholder={t('pages.settings.sections.claudeCode.environmentVariables.keyPlaceholder')}
                      value={variable.key}
                      onChange={(e) => updateVariable(index, 'key', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    {index === 0 && (
                      <Label className="text-xs text-muted-foreground">
                        {t('pages.settings.sections.claudeCode.environmentVariables.valueLabel')}
                      </Label>
                    )}
                    <Input
                      type="password"
                      placeholder={t('pages.settings.sections.claudeCode.environmentVariables.valuePlaceholder')}
                      value={variable.value}
                      onChange={(e) => updateVariable(index, 'value', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => removeVariable(index)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
        {value.length > 0 && (
          <div className="text-xs text-muted-foreground space-y-1">
            <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.loaded')}</p>
            <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.required')}</p>
            <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.naming')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
