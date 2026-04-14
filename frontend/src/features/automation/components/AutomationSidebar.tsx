/**
 * AutomationSidebar - Scheduler center sidebar filters
 */

import React, { useMemo } from 'react';
import { Filter, PauseCircle, PlayCircle, AlertTriangle, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useAutomation, AutomationFilter } from '../providers/AutomationProvider';
import { useI18n } from '@/shared/hooks/useI18n';

const FILTER_ITEMS: Array<{ value: AutomationFilter; labelKey: string; icon: React.ComponentType<any> }> = [
  { value: 'all', labelKey: 'automation.sidebar.filters.all', icon: Filter },
  { value: 'active', labelKey: 'automation.sidebar.filters.active', icon: PlayCircle },
  { value: 'paused', labelKey: 'automation.sidebar.filters.paused', icon: PauseCircle },
  { value: 'failed', labelKey: 'automation.sidebar.filters.failed', icon: AlertTriangle },
];

export const AutomationSidebar: React.FC = () => {
  const { state, setFilter } = useAutomation();
  const { t } = useI18n();

  const counterMap = useMemo(() => {
    return state.automationJobs.reduce<Record<AutomationFilter, number>>((acc, task) => {
      if (task.status === 'active') acc.active += 1;
      if (task.status === 'paused') acc.paused += 1;
      if (task.status === 'failed') acc.failed += 1;
      acc.all += 1;
      return acc;
    }, { all: 0, active: 0, paused: 0, failed: 0 });
  }, [state.automationJobs]);

  return (
    <aside className="w-72 border-r border-border/60 bg-card/60 backdrop-blur-sm">
      <div className="border-b border-border/60 bg-muted/40 px-5 py-4">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">{t('automation.sidebar.title')}</h2>
        </div>
        <p className="mt-1 pl-6 text-xs text-muted-foreground">
          {t('automation.sidebar.description')}
        </p>
      </div>

      <ScrollArea className="h-[calc(100vh-4rem)]">
        <div className="px-4 py-4 space-y-3">
          {FILTER_ITEMS.map(item => {
            const Icon = item.icon;
            const isActive = state.filter === item.value;
            return (
              <Button
                key={item.value}
                variant={isActive ? 'default' : 'ghost'}
                size="sm"
                className={`w-full justify-between ${isActive ? 'shadow-sm' : 'hover:bg-muted'}`}
                onClick={() => setFilter(item.value)}
              >
                <span className="flex items-center gap-2 text-sm">
                  <Icon className="h-4 w-4" />
                  {t(item.labelKey)}
                </span>
                <Badge variant={isActive ? 'secondary' : 'outline'}>{counterMap[item.value]}</Badge>
              </Button>
            );
          })}
        </div>

        <div className="px-4 py-4 border-t border-border/60 space-y-2">
          <h3 className="text-xs font-semibold text-muted-foreground">{t('automation.sidebar.summary.title')}</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2">
              <p className="text-muted-foreground">{t('automation.sidebar.summary.successRate')}</p>
              <p className="mt-1 text-base font-semibold text-emerald-500">
                {state.metrics ? `${Math.round(state.metrics.successRate * 100)}%` : '--'}
              </p>
            </div>
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2">
              <p className="text-muted-foreground">{t('automation.sidebar.summary.averageDuration')}</p>
              <p className="mt-1 text-base font-semibold">
                {state.metrics
                  ? t('automation.sidebar.summary.seconds', {
                      value: Math.round(state.metrics.averageDuration),
                    })
                  : '--'}
              </p>
            </div>
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2">
              <p className="text-muted-foreground">{t('automation.sidebar.summary.running')}</p>
              <p className="mt-1 text-base font-semibold">
                {state.metrics?.runningExecutions ?? '--'}
              </p>
            </div>
            <div className="rounded-md border border-border/60 bg-background/60 px-3 py-2">
              <p className="text-muted-foreground">{t('automation.sidebar.summary.queued')}</p>
              <p className="mt-1 text-base font-semibold">
                {state.metrics?.queuedExecutions ?? '--'}
              </p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  );
};

export default AutomationSidebar;
