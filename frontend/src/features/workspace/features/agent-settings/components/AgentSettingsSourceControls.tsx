import React from 'react';
import { Info } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import {
  ScopeSelector,
  type ScopeOption,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';

export interface AgentSettingsSourceOption<TValue extends string = string> {
  value: TValue;
  label: string;
  icon?: React.ReactNode;
}

export interface AgentSettingsLayerSelectorProps<TValue extends string = string> {
  value: TValue;
  onChange: (value: TValue) => void;
  options: AgentSettingsSourceOption<TValue>[];
  label: string;
  disabled?: boolean;
  width?: string | number;
  className?: string;
}

export interface AgentSettingsSourceFilterProps<TValue extends string = string> {
  value: TValue;
  onChange: (value: TValue) => void;
  options: AgentSettingsSourceOption<TValue>[];
  label: string;
  disabled?: boolean;
  width?: string | number;
  className?: string;
}

const SOURCE_MENU_ORDER = [
  'all',
  'project',
  'user',
  'local',
  'plugin',
  'built_in',
  'inline_config',
  'hooks_json',
];

const getSourceMenuRank = (value: string) => {
  const index = SOURCE_MENU_ORDER.indexOf(value);
  return index === -1 ? SOURCE_MENU_ORDER.length : index;
};

export const sortAgentSettingsScopeValues = <TValue extends string>(values: readonly TValue[]): TValue[] =>
  [...values].sort((first, second) => getSourceMenuRank(first) - getSourceMenuRank(second));

export const sortAgentSettingsSourceOptions = <TOption extends { value: string }>(options: readonly TOption[]): TOption[] =>
  [...options].sort((first, second) => getSourceMenuRank(first.value) - getSourceMenuRank(second.value));

export const AgentSettingsLayerSelector = <TValue extends string = string>({
  value,
  onChange,
  options,
  label,
  disabled,
  width,
  className,
}: AgentSettingsLayerSelectorProps<TValue>) => {
  const mappedOptions: ScopeOption[] = sortAgentSettingsSourceOptions(options).map((option) => ({
    value: option.value,
    label: option.label,
    icon: option.icon,
  }));

  return (
    <ScopeSelector
      value={value}
      onChange={(nextValue) => onChange(nextValue as TValue)}
      options={mappedOptions}
      label={label}
      disabled={disabled}
      width={width}
      className={className}
    />
  );
};

export const AgentSettingsSourceFilter = <TValue extends string = string>({
  value,
  onChange,
  options,
  label,
  disabled,
  width,
  className,
}: AgentSettingsSourceFilterProps<TValue>) => {
  const mappedOptions: ScopeOption[] = sortAgentSettingsSourceOptions(options).map((option) => ({
    value: option.value,
    label: option.label,
    icon: option.icon,
  }));

  return (
    <ScopeSelector
      value={value}
      onChange={(nextValue) => onChange(nextValue as TValue)}
      options={mappedOptions}
      label={label}
      disabled={disabled}
      width={width}
      className={className}
    />
  );
};

export const NewThreadNotice: React.FC<{
  className?: string;
}> = ({ className }) => {
  const { t } = useI18n();

  return (
    <Alert className={className}>
      <Info className="h-4 w-4" />
      <AlertTitle>{t('workspace.agentSettings.common.sourceNotices.newThread.title')}</AlertTitle>
      <AlertDescription>
        {t('workspace.agentSettings.common.sourceNotices.newThread.description')}
      </AlertDescription>
    </Alert>
  );
};
