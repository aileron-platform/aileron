import React, { useMemo, useState } from 'react';
import { Command, FolderOpen, User, Puzzle } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { cn } from '@/shared/utils/cn';

export type CommandScope = 'project' | 'user' | 'plugin';

export interface CommandItem {
  id: string;
  fileName: string;
  scope: CommandScope;
  displayName: string;
  category: string;
  description: string;
  tags?: string[];
}

export interface CommandPickerDialogLabels {
  title?: string;
  description?: string;
  searchPlaceholder?: string;
  empty?: string;
  scope?: Record<CommandScope | 'all', string>;
}

export interface CommandPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  commands: CommandItem[];
  onSelect: (command: CommandItem) => void;
  labels?: CommandPickerDialogLabels;
}

const scopeIcons: Record<CommandScope | 'all', React.ComponentType<{ className?: string }>> = {
  all: Command,
  project: FolderOpen,
  user: User,
  plugin: Puzzle,
};

const defaultLabels: Required<CommandPickerDialogLabels> = {
  title: '選擇指令',
  description: '從指令庫中挑選適合的指令，快速填寫 Prompt。',
  searchPlaceholder: '輸入名稱、描述或標籤搜尋…',
  empty: '沒有符合條件的指令',
  scope: {
    all: '全部',
    project: '專案',
    user: '個人',
    plugin: '外掛',
  },
};

const getScopeLabel = (
  scope: CommandScope | 'all',
  labels: CommandPickerDialogLabels | undefined,
): string => {
  return labels?.scope?.[scope] ?? defaultLabels.scope[scope as keyof typeof defaultLabels.scope];
};

export const CommandPickerDialog: React.FC<CommandPickerDialogProps> = ({
  open,
  onOpenChange,
  commands,
  onSelect,
  labels,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedScope, setSelectedScope] = useState<CommandScope | 'all'>('all');

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

  const resolvedLabels = {
    ...defaultLabels,
    ...labels,
    scope: { ...defaultLabels.scope, ...labels?.scope },
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[80vh] max-w-4xl flex-col gap-0 p-0">
        <DialogHeader className="flex-shrink-0 space-y-3 border-b border-border/60 px-6 py-5">
          <DialogTitle className="text-xl font-semibold">{resolvedLabels.title}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {resolvedLabels.description}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 px-6 py-4">
          <Tabs value={selectedScope} onValueChange={(value) => setSelectedScope(value as CommandScope | 'all')}>
            <TabsList className="grid w-full grid-cols-4">
              {(['all', 'project', 'user', 'plugin'] as const).map(scope => {
                const Icon = scopeIcons[scope];
                return (
                  <TabsTrigger key={scope} value={scope} className="flex items-center gap-2">
                    <Icon className="h-4 w-4" />
                    {getScopeLabel(scope, resolvedLabels)}
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </Tabs>

          <Input
            type="text"
            placeholder={resolvedLabels.searchPlaceholder}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="h-10"
          />
        </div>

        <div className="flex-1 min-h-0 px-6 pb-6">
          <ScrollArea className="h-full rounded-md border border-border/60 bg-muted/20">
            <div className="flex flex-col gap-3 p-4">
              {filteredCommands.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  {resolvedLabels.empty}
                </div>
              ) : (
                filteredCommands.map((command) => (
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
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-medium text-foreground">
                            {command.displayName}
                          </span>
                          <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                            {command.category}
                          </span>
                        </div>
                        {command.description && (
                          <p className="text-sm leading-relaxed text-muted-foreground">
                            {command.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CommandPickerDialog;

