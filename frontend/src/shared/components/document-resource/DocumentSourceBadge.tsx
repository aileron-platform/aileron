import React from 'react';
import { Building, FolderGit, Info, Puzzle, User } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/utils/cn';
import type { DocumentResourceScope } from './model/documentResourceTypes';

export type DocumentSourceType = DocumentResourceScope | 'built_in' | 'inline_config' | 'hooks_json';

export interface DocumentSourceDescriptor {
  type: DocumentSourceType;
  label: string;
  pluginName?: string;
  marketplaceName?: string;
}

const sourceIconClasses = 'h-3 w-3';

const SOURCE_BADGE_CLASSES: Record<DocumentSourceType, string> = {
  project: 'bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary border-primary/20 dark:border-primary/30',
  user: 'bg-secondary dark:bg-secondary text-secondary-foreground dark:text-secondary-foreground border-border dark:border-border',
  local: 'bg-muted dark:bg-muted text-muted-foreground dark:text-muted-foreground border-border dark:border-border',
  plugin: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
  built_in: 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700',
  inline_config: 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-700',
  hooks_json: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700',
};

const SOURCE_ICONS: Record<DocumentSourceType, React.ComponentType<{ className?: string }>> = {
  project: FolderGit,
  user: User,
  local: Building,
  plugin: Puzzle,
  built_in: Info,
  inline_config: Info,
  hooks_json: Info,
};

export const normalizeDocumentSourceType = (
  sourceType: string | null | undefined,
  fallback: DocumentSourceType = 'project',
): DocumentSourceType => (
  sourceType && sourceType in SOURCE_BADGE_CLASSES
    ? sourceType as DocumentSourceType
    : fallback
);

export const getDocumentSourceBadgeClassName = (sourceType: string | null | undefined) =>
  SOURCE_BADGE_CLASSES[normalizeDocumentSourceType(sourceType)];

export const getDocumentSourceIcon = (sourceType: string | null | undefined) =>
  SOURCE_ICONS[normalizeDocumentSourceType(sourceType)];

export const DocumentSourceBadge: React.FC<{
  source: DocumentSourceDescriptor;
  className?: string;
}> = ({ source, className }) => {
  const normalizedType = normalizeDocumentSourceType(source.type);
  const Icon = SOURCE_ICONS[normalizedType];
  const label = normalizedType === 'plugin' && source.pluginName
    ? `${source.pluginName}@${source.marketplaceName ?? source.label}`
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
