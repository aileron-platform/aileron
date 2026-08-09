import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { SettingsFlatRow, SettingsFlatSection } from '@/shared/components/settings-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserToolModelSelection } from '@/shared/types/user';

export interface SettingsModelSelectionSectionProps {
  value: UserToolModelSelection;
  onChange: (value: UserToolModelSelection) => void;
  i18nPrefix: string;
}

const unique = (items: string[]) => Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)));

const nextDefault = (allowedModels: string[], current: string) =>
  allowedModels.includes(current) ? current : allowedModels[0] || current;

export const SettingsModelSelectionSection = ({
  value,
  onChange,
  i18nPrefix,
}: SettingsModelSelectionSectionProps) => {
  const { t } = useI18n();
  const [customModel, setCustomModel] = useState('');

  const addCustomModel = () => {
    const model = customModel.trim();
    if (!model || value.availableModels.includes(model)) return;

    onChange({
      customModels: unique([...value.customModels, model]),
      availableModels: unique([...value.availableModels, model]),
      allowedModels: unique([...value.allowedModels, model]),
      defaultModel: value.defaultModel,
    });
    setCustomModel('');
  };

  const toggleAllowedModel = (model: string) => {
    if (value.allowedModels.includes(model)) {
      const allowedModels = value.allowedModels.filter((item) => item !== model);
      if (allowedModels.length === 0) return;

      onChange({
        ...value,
        allowedModels,
        defaultModel: nextDefault(allowedModels, value.defaultModel === model ? '' : value.defaultModel),
      });
      return;
    }

    onChange({
      ...value,
      allowedModels: unique([...value.allowedModels, model]),
    });
  };

  const removeCustomModel = (target: string) => {
    const allowedModels = value.allowedModels.filter((model) => model !== target);
    if (allowedModels.length === 0) return;

    onChange({
      customModels: value.customModels.filter((model) => model !== target),
      availableModels: value.availableModels.filter((model) => model !== target),
      allowedModels,
      defaultModel: nextDefault(allowedModels, value.defaultModel === target ? '' : value.defaultModel),
    });
  };

  return (
    <SettingsFlatSection
      title={t(`${i18nPrefix}.title`)}
      description={t(`${i18nPrefix}.description`)}
    >
      <SettingsFlatRow label={t(`${i18nPrefix}.allowedLabel`)}>
        <div className="space-y-2">
          {value.availableModels.map((model) => {
            const isCustom = value.customModels.includes(model);

            return (
              <div key={model} className="flex min-h-8 items-center gap-3">
                <Checkbox
                  id={`${i18nPrefix}-${model}`}
                  checked={value.allowedModels.includes(model)}
                  onCheckedChange={() => toggleAllowedModel(model)}
                  aria-label={model}
                />
                <Label htmlFor={`${i18nPrefix}-${model}`} className="flex flex-1 items-center gap-2 font-mono">
                  {model}
                  {isCustom && <Badge variant="secondary">{t(`${i18nPrefix}.customBadge`)}</Badge>}
                </Label>
                {isCustom && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => removeCustomModel(model)}
                    aria-label={model}
                    title={t(`${i18nPrefix}.removeCustom`)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      </SettingsFlatRow>

      <SettingsFlatRow label={t(`${i18nPrefix}.defaultLabel`)}>
        <Select value={value.defaultModel} onValueChange={(defaultModel) => onChange({ ...value, defaultModel })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {value.allowedModels.map((model) => (
              <SelectItem key={model} value={model}>{model}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingsFlatRow>

      <SettingsFlatRow label={t(`${i18nPrefix}.addButton`)}>
        <div className="flex gap-2">
          <Input
            value={customModel}
            onChange={(event) => setCustomModel(event.target.value)}
            placeholder={t(`${i18nPrefix}.addPlaceholder`)}
            className="font-mono"
          />
          <Button type="button" onClick={addCustomModel}>{t(`${i18nPrefix}.addButton`)}</Button>
        </div>
      </SettingsFlatRow>
    </SettingsFlatSection>
  );
};
