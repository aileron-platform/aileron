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
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';

export type AgentSettingsSourceType = AgentScope | 'managed' | 'built-in' | 'inline-config';

export interface AgentSettingsSourceDescriptor {
  type: AgentSettingsSourceType;
  label: string;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentSettingsLayerSelectorProps<TValue extends string = string> {
  value: TValue;
  onChange: (value: TValue) => void;
  options: Array<{
    value: TValue;
    label: string;
    icon?: React.ReactNode;
  }>;
  label: string;
  className?: string;
}

const sourceIconClasses = 'h-3 w-3';

const SOURCE_BADGE_CLASSES: Record<AgentSettingsSourceType, string> = {
  ...SCOPE_BADGE_CLASSES,
  managed: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700',
  'built-in': 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700',
  'inline-config': 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-700',
};

const SOURCE_ICONS: Record<AgentSettingsSourceType, React.ComponentType<{ className?: string }>> = {
  project: FolderGit,
  user: User,
  local: Building,
  plugin: Puzzle,
  managed: AlertCircle,
  'built-in': Info,
  'inline-config': Info,
};

export const AgentSettingsLayerSelector = <TValue extends string = string>({
  value,
  onChange,
  options,
  label,
  className,
}: AgentSettingsLayerSelectorProps<TValue>) => {
  const mappedOptions: ScopeOption[] = options.map((option) => ({
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
      className={className}
    />
  );
};

export const AgentSettingsSourceBadge: React.FC<{
  source: AgentSettingsSourceDescriptor;
  className?: string;
}> = ({ source, className }) => {
  const Icon = SOURCE_ICONS[source.type];
  const label = source.type === 'plugin' && source.pluginName
    ? `${source.pluginName}@${source.marketplaceName ?? source.label}`
    : source.label;

  return (
    <Badge
      variant="outline"
      className={cn('inline-flex items-center gap-1 text-[11px]', SOURCE_BADGE_CLASSES[source.type], className)}
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

export const getAgentSettingsSourceIcon = (sourceType: AgentSettingsSourceType) => SOURCE_ICONS[sourceType];
