import type { AgentScope } from '../types';

export const SCOPE_BADGE_CLASSES: Record<AgentScope, string> = {
  project: 'bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary border-primary/20 dark:border-primary/30',
  user: 'bg-secondary dark:bg-secondary text-secondary-foreground dark:text-secondary-foreground border-border dark:border-border',
  local: 'bg-muted dark:bg-muted text-muted-foreground dark:text-muted-foreground border-border dark:border-border',
  plugin: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
};
