import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Plus, Trash2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { SettingsFlatSection } from './SettingsFlatSection';

export interface EnvironmentVariable {
  key: string;
  value: string;
}

export interface EnvironmentVariablesProps {
  value: EnvironmentVariable[];
  onChange: (variables: EnvironmentVariable[]) => void;
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
    const newVariable: EnvironmentVariable = {
      key: '',
      value: ''
    };
    onChange([...value, newVariable]);
  };

  const removeVariable = (index: number) => {
    const updatedVariables = value.filter((_, i) => i !== index);
    onChange(updatedVariables);
  };

  const updateVariable = (index: number, field: keyof EnvironmentVariable, newValue: string) => {
    const updatedVariables = value.map((variable, i) => {
      if (i === index) {
        return { ...variable, [field]: newValue };
      }
      return variable;
    });
    onChange(updatedVariables);
  };

  return (
    <SettingsFlatSection
      title={resolvedTitle}
      description={resolvedDescription}
    >
      <div className="flex justify-end">
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
      </div>
      {value.length === 0 ? (
        <div className="py-4 text-sm text-muted-foreground">
          <p>{t('pages.settings.sections.claudeCode.environmentVariables.emptyState.title')}</p>
          <p className="text-xs">
            {t('pages.settings.sections.claudeCode.environmentVariables.emptyState.description')}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {value.map((variable, index) => (
            <div key={index} className="flex items-center gap-3">
              <div className="grid flex-1 gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  {index === 0 && (
                    <Label className="text-xs text-muted-foreground">
                      {t('pages.settings.sections.claudeCode.environmentVariables.keyLabel')}
                    </Label>
                  )}
                  <Input
                    placeholder={t('pages.settings.sections.claudeCode.environmentVariables.keyPlaceholder')}
                    value={variable.key}
                    onChange={(event) => updateVariable(index, 'key', event.target.value)}
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
                    onChange={(event) => updateVariable(index, 'value', event.target.value)}
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
        <div className="space-y-1 text-xs text-muted-foreground">
          <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.loaded')}</p>
          <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.required')}</p>
          <p>• {t('pages.settings.sections.claudeCode.environmentVariables.hints.naming')}</p>
        </div>
      )}
    </SettingsFlatSection>
  );
};
