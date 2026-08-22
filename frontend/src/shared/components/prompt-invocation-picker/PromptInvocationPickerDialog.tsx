import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Command, Download, Search, Sparkles } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type {
  PromptInvocationCatalog,
  PromptInvocationItem,
  PromptInvocationScope,
} from '@/shared/types/promptInvocations';
import { Badge } from '@/shared/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

export interface PromptInvocationPickerDialogLabels {
  title?: string;
  description?: string;
  searchPlaceholder?: string;
  empty?: string;
}

export interface PromptInvocationPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  catalogKey: string;
  loadCatalog: () => Promise<PromptInvocationCatalog>;
  onSelect: (item: PromptInvocationItem) => void;
  labels?: PromptInvocationPickerDialogLabels;
}

const scopeIcons = {
  all: Command,
  project: Command,
  user: Command,
  plugin: Command,
};

export const PromptInvocationPickerDialog: React.FC<PromptInvocationPickerDialogProps> = ({
  open,
  onOpenChange,
  catalogKey,
  loadCatalog,
  onSelect,
  labels,
}) => {
  const { t } = useI18n();
  const [catalog, setCatalog] = useState<PromptInvocationCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedScope, setSelectedScope] = useState<PromptInvocationScope | 'all'>('all');

  useEffect(() => {
    if (!open) return;

    let active = true;
    setLoading(true);
    setFailed(false);
    setCatalog(null);
    void loadCatalog()
      .then((result) => {
        if (active) setCatalog(result);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [catalogKey, loadCatalog, open]);

  const scopeTabs = useMemo(() => (
    ['all', ...(catalog?.availableScopes ?? [])] as const
  ), [catalog?.availableScopes]);

  useEffect(() => {
    if (!scopeTabs.includes(selectedScope)) setSelectedScope('all');
  }, [scopeTabs, selectedScope]);

  const resolvedLabels = {
    title: labels?.title ?? t('common.promptInvocation.picker.title'),
    description: labels?.description ?? t('common.promptInvocation.picker.description'),
    searchPlaceholder: labels?.searchPlaceholder ?? t('common.promptInvocation.picker.searchPlaceholder'),
    empty: labels?.empty ?? t('common.promptInvocation.picker.empty'),
  };

  const filteredItems = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    return (catalog?.items ?? []).filter((item) => {
      if (selectedScope !== 'all' && item.scope !== selectedScope) return false;
      if (!normalized) return true;
      return item.displayName.toLowerCase().includes(normalized)
        || item.fileName.toLowerCase().includes(normalized)
        || item.description.toLowerCase().includes(normalized)
        || item.tags.some((tag) => tag.toLowerCase().includes(normalized));
    });
  }, [catalog?.items, searchTerm, selectedScope]);

  const renderItems = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <LoadingSpinner />
          {t('common.promptInvocation.picker.loading')}
        </div>
      );
    }
    if (failed) {
      return (
        <div role="alert" className="py-12 text-center text-sm text-destructive">
          {t('common.promptInvocation.picker.error')}
        </div>
      );
    }
    if (catalog?.completeness === 'degraded' && catalog.items.length === 0) {
      return (
        <div role="status" className="py-12 text-center text-sm text-warning-foreground">
          {t('common.promptInvocation.picker.degradedEmpty')}
        </div>
      );
    }
    if (filteredItems.length === 0) {
      return (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {resolvedLabels.empty}
        </div>
      );
    }
    return filteredItems.map((item) => {
      const kindLabel = t(`common.promptInvocation.picker.kind.${item.kind}`);
      const KindIcon = item.kind === 'skill' ? Sparkles : Command;
      return (
        <button
          key={item.id}
          type="button"
          onClick={() => {
            onSelect(item);
            onOpenChange(false);
          }}
          className={cn(
            'w-full rounded-xl border border-border bg-card/80 p-4 text-left shadow-sm transition-all duration-200',
            'hover:border-primary/60 hover:bg-primary/5',
          )}
        >
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
            <span className="block min-w-0 break-words font-mono text-sm leading-6 text-primary">
              {item.invocation}
            </span>
            <div className="flex min-w-0 items-start justify-end gap-2">
              <Badge variant="outline" className="max-w-28 text-[10px] uppercase tracking-wide" title={kindLabel}>
                <span className="inline-flex min-w-0 items-center gap-1">
                  <KindIcon className="h-3 w-3 shrink-0" />
                  <span className="min-w-0 truncate">{kindLabel}</span>
                </span>
              </Badge>
              <Badge variant="secondary" className="max-w-44 text-xs capitalize" title={item.category}>
                <span className="min-w-0 truncate">{item.category}</span>
              </Badge>
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground">
                <Download className="h-4 w-4" />
              </span>
            </div>
            <p className="col-span-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              {item.description}
            </p>
          </div>
        </button>
      );
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[80vh] flex-col sm:max-w-3xl">
        <DialogHeader className="flex-shrink-0 space-y-1">
          <DialogHeading icon={Command}>{resolvedLabels.title}</DialogHeading>
          <DialogDescription>{resolvedLabels.description}</DialogDescription>
        </DialogHeader>

        {catalog?.completeness === 'degraded' && (
          <div role="alert" className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-foreground">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {t('common.promptInvocation.picker.degraded')}
          </div>
        )}

        <div className="flex flex-col gap-4">
          <Tabs value={selectedScope} onValueChange={(value) => setSelectedScope(value as PromptInvocationScope | 'all')}>
            <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${scopeTabs.length}, minmax(0, 1fr))` }}>
              {scopeTabs.map((scope) => {
                const Icon = scopeIcons[scope];
                return (
                  <TabsTrigger key={scope} value={scope} className="flex items-center gap-2">
                    <Icon className="h-4 w-4" />
                    {t(`common.promptInvocation.picker.scope.${scope}`)}
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

        <div className="min-h-0 flex-1 py-4">
          <ScrollArea className="h-full rounded-md border border-border/60 bg-muted/20">
            <div className="flex flex-col gap-3 p-4">{renderItems()}</div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
};
