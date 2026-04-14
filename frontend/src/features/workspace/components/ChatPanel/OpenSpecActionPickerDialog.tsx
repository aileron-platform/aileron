import React, { useMemo, useState } from 'react';
import { BookOpen, CheckCircle2, CircleHelp, Compass, Play, Search, Wrench } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import type { OpenSpecActionGroup, OpenSpecActionItem, OpenSpecWorkspaceState } from './openSpecApi';

interface OpenSpecActionPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  actions: OpenSpecActionItem[];
  state: OpenSpecWorkspaceState | null;
  onSelect: (action: OpenSpecActionItem) => void;
}

const groupIcons: Record<OpenSpecActionGroup, React.ComponentType<{ className?: string }>> = {
  start: Compass,
  plan: BookOpen,
  implement: Play,
  finalize: CheckCircle2,
  learn: CircleHelp,
};

const groupOrder: OpenSpecActionGroup[] = ['start', 'plan', 'implement', 'finalize', 'learn'];

export const OpenSpecActionPickerDialog: React.FC<OpenSpecActionPickerDialogProps> = ({
  open,
  onOpenChange,
  actions,
  state,
  onSelect,
}) => {
  const { t } = useI18n();
  const [searchTerm, setSearchTerm] = useState('');

  const visibleActions = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    return actions.filter((action) => {
      if (action.availability === 'hidden') {
        return false;
      }
      if (!normalized) {
        return true;
      }
      return `${action.title} ${action.description}`.toLowerCase().includes(normalized);
    });
  }, [actions, searchTerm]);

  const groupedActions = useMemo(() => {
    return groupOrder
      .map((group) => ({
        group,
        items: visibleActions.filter((action) => action.group === group),
      }))
      .filter((entry) => entry.items.length > 0);
  }, [visibleActions]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl h-[80vh] flex flex-col">
        <DialogHeader className="space-y-1">
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            {t('workspace.chat.dialogs.openspec.title')}
          </DialogTitle>
          <DialogDescription>
            {t('workspace.chat.dialogs.openspec.description')}
          </DialogDescription>
          {state && (
            <div className="flex flex-wrap items-center gap-2 pt-2 text-xs text-muted-foreground">
              <Badge variant="secondary">{t(`workspace.chat.dialogs.openspec.profile.${state.profile}`)}</Badge>
              <span>
                {state.initialized
                  ? t('workspace.chat.dialogs.openspec.status.initialized')
                  : t('workspace.chat.dialogs.openspec.status.notInitialized')}
              </span>
              {state.cliVersion ? <span>{t('workspace.chat.dialogs.openspec.version', { version: state.cliVersion })}</span> : null}
            </div>
          )}
        </DialogHeader>

        <div className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder={t('workspace.chat.dialogs.openspec.searchPlaceholder')}
            className="h-8 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
          />
        </div>

        <div className="flex-1 min-h-0 py-2">
          <ScrollArea className="h-full rounded-md border border-border/60 bg-muted/20">
            <div className="flex flex-col gap-5 p-4">
              {groupedActions.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  {t('workspace.chat.dialogs.openspec.empty')}
                </div>
              ) : (
                groupedActions.map(({ group, items }) => {
                  const Icon = groupIcons[group];
                  return (
                    <section key={group} className="space-y-3">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <Icon className="h-4 w-4 text-primary" />
                        <span>{t(`workspace.chat.dialogs.openspec.groups.${group}`)}</span>
                      </div>
                      <div className="grid gap-3">
                        {items.map((action) => {
                          const disabled = action.availability !== 'enabled';
                          return (
                            <button
                              key={action.id}
                              type="button"
                              onClick={() => {
                                if (disabled) return;
                                onSelect(action);
                                onOpenChange(false);
                              }}
                              disabled={disabled}
                              className={cn(
                                'w-full rounded-xl border border-border bg-card/80 p-4 text-left shadow-sm transition-all duration-200',
                                disabled
                                  ? 'cursor-not-allowed opacity-60'
                                  : 'hover:border-primary/60 hover:bg-primary/5',
                              )}
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div className="space-y-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="font-mono text-sm text-primary">{action.draftTemplate.trim()}</span>
                                    <Badge variant="secondary" className="text-xs capitalize">
                                      {t(`workspace.chat.dialogs.openspec.profile.${action.profile}`)}
                                    </Badge>
                                    {action.recommended && (
                                      <Badge variant="outline" className="text-xs">
                                        {t('workspace.chat.dialogs.openspec.recommended')}
                                      </Badge>
                                    )}
                                  </div>
                                  <p className="text-sm font-medium text-foreground">{action.title}</p>
                                  <p className="text-sm text-muted-foreground">{action.description}</p>
                                  {action.reason ? (
                                    <p className="text-xs text-amber-700">{action.reason}</p>
                                  ) : null}
                                </div>
                                <span className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted-foreground">
                                  <Wrench className="h-4 w-4" />
                                </span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </section>
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

export default OpenSpecActionPickerDialog;
