import React from 'react';
import { AlertCircle, Building, FolderGit, Info, Puzzle, User } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import {
  ScopeSelector,
  type ScopeOption,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { AgentScope } from '../types';

export type AgentSettingsSourceType = AgentScope | 'built_in' | 'inline_config' | 'hooks_json';

export interface AgentSettingsSourceDescriptor {
  type: AgentSettingsSourceType;
  label: string;
  pluginName?: string;
  marketplaceName?: string;
  extensionName?: string;
  extensionVersion?: string;
}

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

const sourceIconClasses = 'h-3 w-3';
const SOURCE_MENU_ORDER = [
  'all',
  'project',
  'user',
  'local',
  'extension',
  'built_in',
  'inline_config',
  'hooks_json',
  'built-in',
  'inline-config',
];

const getSourceMenuRank = (value: string) => {
  if (value === 'plugin') {
    return SOURCE_MENU_ORDER.indexOf('extension');
  }
  const index = SOURCE_MENU_ORDER.indexOf(value);
  return index === -1 ? SOURCE_MENU_ORDER.length : index;
};

const SOURCE_BADGE_CLASSES: Record<AgentSettingsSourceType, string> = {
  project: 'bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary border-primary/20 dark:border-primary/30',
  user: 'bg-secondary dark:bg-secondary text-secondary-foreground dark:text-secondary-foreground border-border dark:border-border',
  local: 'bg-muted dark:bg-muted text-muted-foreground dark:text-muted-foreground border-border dark:border-border',
  plugin: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
  extension: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-700',
  built_in: 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700',
  inline_config: 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-700',
  hooks_json: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700',
};

const SOURCE_ICONS: Record<AgentSettingsSourceType, React.ComponentType<{ className?: string }>> = {
  project: FolderGit,
  user: User,
  local: Building,
  plugin: Puzzle,
  extension: Puzzle,
  built_in: Info,
  inline_config: Info,
  hooks_json: Info,
};

const LEGACY_SOURCE_TYPE_MAP = {
  'built-in': 'built_in',
  'inline-config': 'inline_config',
} as const satisfies Record<string, AgentSettingsSourceType>;

export const normalizeAgentSettingsSourceType = (
  sourceType: string | null | undefined,
  fallback: AgentSettingsSourceType = 'project',
): AgentSettingsSourceType => {
  if (!sourceType) return fallback;
  if (sourceType in LEGACY_SOURCE_TYPE_MAP) {
    return LEGACY_SOURCE_TYPE_MAP[sourceType as keyof typeof LEGACY_SOURCE_TYPE_MAP];
  }
  if (sourceType in SOURCE_BADGE_CLASSES) {
    return sourceType as AgentSettingsSourceType;
  }
  return fallback;
};

export const getAgentSettingsSourceBadgeClassName = (sourceType: string | null | undefined) =>
  SOURCE_BADGE_CLASSES[normalizeAgentSettingsSourceType(sourceType)];

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

export const AgentSettingsSourceBadge: React.FC<{
  source: AgentSettingsSourceDescriptor;
  className?: string;
}> = ({ source, className }) => {
  const normalizedType = normalizeAgentSettingsSourceType(source.type);
  const Icon = SOURCE_ICONS[normalizedType];
  const label = normalizedType === 'plugin' && source.pluginName
    ? `${source.pluginName}@${source.marketplaceName ?? source.label}`
    : normalizedType === 'extension' && source.extensionName
      ? [source.extensionName, source.extensionVersion].filter(Boolean).join('@')
      : source.label;

  return (
    <Badge
      variant="outline"
      className={cn('inline-flex items-center gap-1 text-[11px]', SOURCE_BADGE_CLASSES[normalizedType], className)}
    >
      <Icon className={sourceIconClasses} />
      {label}
    </Badge>
  );
};

export const ReadOnlySourceNotice: React.FC<{
  sourceLabel: string;
  className?: string;
}> = ({ sourceLabel, className }) => {
  const { t } = useI18n();

  return (
    <Alert className={className}>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>{t('workspace.agentSettings.common.sourceNotices.readOnly.title')}</AlertTitle>
      <AlertDescription>
        {t('workspace.agentSettings.common.sourceNotices.readOnly.description', { source: sourceLabel })}
      </AlertDescription>
    </Alert>
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

export const getAgentSettingsSourceIcon = (sourceType: string | null | undefined) =>
  SOURCE_ICONS[normalizeAgentSettingsSourceType(sourceType)];
