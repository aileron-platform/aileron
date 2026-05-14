import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/utils/cn';
import { SlashCommandItem, SlashCommandScope } from '@/shared/types/slashCommands';
import { Command, FolderOpen, Search, User, Download, Puzzle, Sparkles } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

export interface SlashCommandPickerDialogLabels {
  title?: string;
  description?: string;
  searchPlaceholder?: string;
  empty?: string;
  scope?: Record<SlashCommandScope | 'all', string>;
  kind?: Record<'slash-command' | 'skill', string>;
}

export interface SlashCommandPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  commands: SlashCommandItem[];
  onSelect: (command: SlashCommandItem) => void;
  labels?: SlashCommandPickerDialogLabels;
  availableScopes?: string[];
}

const scopeIcons: Record<SlashCommandScope | 'all', React.ComponentType<{ className?: string }>> = {
  all: Command,
  project: FolderOpen,
  user: User,
  plugin: Puzzle,
};

export const SlashCommandPickerDialog: React.FC<SlashCommandPickerDialogProps> = ({
  open,
  onOpenChange,
  commands,
  onSelect,
  labels,
  availableScopes,
}) => {
  const { t } = useI18n();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedScope, setSelectedScope] = useState<SlashCommandScope | 'all'>('all');

  const scopeTabs = useMemo(() => {
    const tabs: (SlashCommandScope | 'all')[] = ['all'];
    if (!availableScopes || availableScopes.length === 0) {
      return ['all', 'project', 'user', 'plugin'] as const;
    }
    const displayableScopes: SlashCommandScope[] = ['project', 'user', 'plugin'];
    for (const s of displayableScopes) {
      if (availableScopes.includes(s)) tabs.push(s);
    }
    return tabs;
  }, [availableScopes]);

  useEffect(() => {
    if (!scopeTabs.includes(selectedScope)) {
      setSelectedScope('all');
    }
  }, [scopeTabs, selectedScope]);

  const defaultLabels: Required<SlashCommandPickerDialogLabels> = useMemo(() => ({
    title: t('common.slashCommand.picker.title'),
    description: t('common.slashCommand.picker.description'),
    searchPlaceholder: t('common.slashCommand.picker.searchPlaceholder'),
    empty: t('common.slashCommand.picker.empty'),
    scope: {
      all: t('common.slashCommand.picker.scope.all'),
      project: t('common.slashCommand.picker.scope.project'),
      user: t('common.slashCommand.picker.scope.user'),
      plugin: t('common.slashCommand.picker.scope.plugin'),
    },
    kind: {
      'slash-command': t('common.slashCommand.picker.kind.slash-command'),
      skill: t('common.slashCommand.picker.kind.skill'),
    },
  }), [t]);

  const filteredCommands = useMemo(() => {
    const normalized = searchTerm.toLowerCase();
    return commands.filter((command) => {
      const scopeMatch = selectedScope === 'all' || command.scope === selectedScope;
      if (!scopeMatch) {
        return false;
      }
      if (!normalized) {
        return true;
      }
      const displayName = command.displayName.toLowerCase();
      const fileName = command.fileName.toLowerCase();
      return (
        displayName.includes(normalized) ||
        fileName.includes(normalized) ||
        command.description.toLowerCase().includes(normalized) ||
        command.tags?.some((tag) => tag.toLowerCase().includes(normalized))
      );
    });
  }, [commands, searchTerm, selectedScope]);

  const resolvedLabels = useMemo(() => ({
    ...defaultLabels,
    ...labels,
    scope: { ...defaultLabels.scope, ...labels?.scope },
    kind: { ...defaultLabels.kind, ...labels?.kind },
  }), [defaultLabels, labels]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl h-[80vh] flex flex-col">
        <DialogHeader className="flex-shrink-0 space-y-1">
          <DialogHeading icon={Command}>
            {resolvedLabels.title}
          </DialogHeading>
          <DialogDescription>{resolvedLabels.description}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <Tabs value={selectedScope} onValueChange={(value) => setSelectedScope(value as SlashCommandScope | 'all')}>
            <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${scopeTabs.length}, minmax(0, 1fr))` }}>
              {scopeTabs.map(scope => {
                const Icon = scopeIcons[scope];
                return (
                  <TabsTrigger key={scope} value={scope} className="flex items-center gap-2">
                    <Icon className="h-4 w-4" />
                    {resolvedLabels.scope[scope]}
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder={resolvedLabels.searchPlaceholder}
              className="h-8 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            />
          </div>
        </div>

        <div className="flex-1 min-h-0 py-4">
          <ScrollArea className="h-full rounded-md border border-border/60 bg-muted/20">
            <div className="flex flex-col gap-3 p-4">
              {filteredCommands.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  {resolvedLabels.empty}
                </div>
              ) : (
                filteredCommands.map((command) => {
                  const kindLabel = command.kind === 'skill'
                    ? resolvedLabels.kind.skill
                    : resolvedLabels.kind['slash-command'];
                  const KindIcon = command.kind === 'skill' ? Sparkles : Command;

                  return (
                  <button
                    key={command.id}
                    type="button"
                    onClick={() => {
                      onSelect(command);
                      onOpenChange(false);
                    }}
                    className={cn(
                      'w-full rounded-xl border border-border bg-card/80 p-4 text-left shadow-sm transition-all duration-200',
                      'hover:border-primary/60 hover:bg-primary/5'
                    )}
                  >
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
                      <div className="min-w-0">
                        <span className="block break-words font-mono text-sm leading-6 text-primary">
                          /{command.displayName}
                        </span>
                      </div>
                      <div className="flex min-w-0 items-start justify-end gap-2">
                        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
                          <Badge
                            variant="outline"
                            className="max-w-28 text-[10px] uppercase tracking-wide"
                            title={kindLabel}
                          >
                            <span className="inline-flex min-w-0 items-center gap-1">
                              <KindIcon className="h-3 w-3 shrink-0" />
                              <span className="min-w-0 truncate">{kindLabel}</span>
                            </span>
                          </Badge>
                          <Badge
                            variant="secondary"
                            className="max-w-44 text-xs capitalize"
                            title={command.category}
                          >
                            <span className="min-w-0 truncate">{command.category}</span>
                          </Badge>
                        </div>
                        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground">
                          <Download className="h-4 w-4" />
                        </span>
                      </div>
                      <p className="col-span-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                        {command.description}
                      </p>
                      {command.tags && command.tags.length > 0 && (
                        <div className="col-span-2 flex flex-wrap gap-1.5">
                          {command.tags.slice(0, 4).map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className="max-w-40 text-[10px] capitalize"
                              title={tag}
                            >
                              <span className="min-w-0 truncate">{tag}</span>
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SlashCommandPickerDialog;
