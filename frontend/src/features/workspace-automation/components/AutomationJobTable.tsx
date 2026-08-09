import React from 'react';
import {
  History,
  MoreHorizontal,
  Pencil,
  PlayCircle,
  Trash2,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AutomationJob } from '../model/automationTypes';

const STATUS_COLORS: Record<string, string> = {
  active: 'text-emerald-500',
  paused: 'text-amber-500',
  completed: 'text-sky-500',
};

type AutomationJobTableScope = 'global' | 'workspace';

interface AutomationJobTableProps {
  scope: AutomationJobTableScope;
  jobs: AutomationJob[];
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  locale?: string;
  onPageChange: (page: number) => void;
  onViewExecutions: (job: AutomationJob) => void;
  onEdit: (jobId: string) => void;
  onExecute: (job: AutomationJob) => void | Promise<void>;
  onDelete: (job: AutomationJob) => void | Promise<void>;
}

export const AutomationJobTable: React.FC<AutomationJobTableProps> = ({
  scope,
  jobs,
  page,
  totalPages,
  totalItems,
  pageSize,
  locale,
  onPageChange,
  onViewExecutions,
  onEdit,
  onExecute,
  onDelete,
}) => {
  const { t, state } = useI18n();
  const dateLocale = scope === 'workspace' ? locale : state?.currentLanguage;

  const tableKey = (globalKey: string, workspaceKey: string) =>
    t(scope === 'global' ? globalKey : workspaceKey);

  const statusLabel = (job: AutomationJob) => tableKey(
    `automation.dashboard.table.status.${job.status}`,
    `workspace.automation.status.${job.status}`,
  );

  return (
    <div className="rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border/40">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.name', 'workspace.automation.table.columns.name')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.schedule', 'workspace.automation.table.columns.schedule')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.nextRun', 'workspace.automation.table.columns.nextRun')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.status', 'workspace.automation.table.columns.status')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.view', 'workspace.automation.table.columns.view')}
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                {tableKey('automation.dashboard.table.headers.actions', 'workspace.automation.table.columns.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30 bg-background/40">
            {jobs.map(job => (
              <tr key={job.id}>
                <td className="px-4 py-3 align-top">
                  <div className="text-sm font-medium text-foreground">{job.name}</div>
                  {scope === 'global' && job.workspaceName && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      <span className="inline-flex items-center gap-1">
                        <span className="text-muted-foreground/60">
                          {t('automation.dashboard.table.workspaceLabel')}:
                        </span>
                        <span className="font-medium">{job.workspaceName}</span>
                      </span>
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">{job.description}</p>
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  <div className="font-medium text-sm">
                    {job.trigger === 'manual' || job.trigger === 'webhook'
                      ? tableKey(
                          `automation.form.trigger.${job.trigger}`,
                          `workspace.automation.triggers.${job.trigger}`,
                        )
                      : job.schedule || tableKey(
                          'automation.dashboard.table.noScheduled',
                          'workspace.automation.table.noScheduled',
                        )}
                  </div>
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  <div>
                    {job.nextRunAt
                      ? scope === 'global'
                        ? t('automation.dashboard.table.nextRunLabel', {
                            value: new Date(job.nextRunAt).toLocaleString(dateLocale),
                          })
                        : t('workspace.automation.table.nextRun', {
                            time: new Date(job.nextRunAt).toLocaleString(dateLocale),
                          })
                      : tableKey(
                          'automation.dashboard.table.noScheduled',
                          'workspace.automation.table.noScheduled',
                        )}
                  </div>
                  {job.lastRunAt && (
                    <div className="mt-1">
                      {scope === 'global'
                        ? t('automation.dashboard.table.lastRunLabel', {
                            value: new Date(job.lastRunAt).toLocaleString(dateLocale),
                          })
                        : t('workspace.automation.table.lastRun', {
                            time: new Date(job.lastRunAt).toLocaleString(dateLocale),
                          })}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-xs">
                  {scope === 'global' ? (
                    <div className="space-y-1">
                      <span className={`font-semibold ${STATUS_COLORS[job.status] ?? ''}`}>
                        {statusLabel(job)}
                      </span>
                    </div>
                  ) : (
                    <span className={`font-semibold ${STATUS_COLORS[job.status] ?? ''}`}>
                      {statusLabel(job)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-center">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 px-3 text-xs"
                    onClick={() => onViewExecutions(job)}
                  >
                    <History className="h-3.5 w-3.5 mr-1" />
                    {tableKey(
                      'automation.dashboard.table.viewTask',
                      'workspace.automation.table.viewButton',
                    )}
                  </Button>
                </td>
                <td className="px-4 py-3 align-top text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem onClick={() => onEdit(job.id)} className="gap-2 text-xs">
                        <Pencil className="h-3.5 w-3.5" />
                        {tableKey(
                          'automation.dashboard.table.edit',
                          'workspace.automation.table.editAction',
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onExecute(job)} className="gap-2 text-xs">
                        <PlayCircle className="h-3.5 w-3.5" />
                        {tableKey(
                          'automation.dashboard.table.runNow',
                          'workspace.automation.table.executeAction',
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => onDelete(job)}
                        className="gap-2 text-xs text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {tableKey(
                          'automation.dashboard.table.delete',
                          'workspace.automation.table.deleteAction',
                        )}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {tableKey(
                    'automation.dashboard.table.empty',
                    'workspace.automation.table.empty',
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <AutomationJobPagination
        scope={scope}
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        totalItems={totalItems}
        onPageChange={onPageChange}
      />
    </div>
  );
};

interface AutomationJobPaginationProps {
  scope: AutomationJobTableScope;
  page: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
}

const AutomationJobPagination: React.FC<AutomationJobPaginationProps> = ({
  scope,
  page,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
}) => {
  const { t } = useI18n();
  const safeTotalPages = Math.max(1, totalPages);
  const currentPage = Math.min(page, safeTotalPages);
  const hasData = totalItems > 0;
  const startItem = hasData ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = hasData ? Math.min(currentPage * pageSize, totalItems) : 0;
  const disablePrev = !hasData || currentPage <= 1;
  const disableNext = !hasData || currentPage >= safeTotalPages;
  const keyPrefix = scope === 'global'
    ? 'automation.dashboard.pagination'
    : 'workspace.automation.pagination';

  const handlePrev = () => {
    if (!disablePrev) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (!disableNext) {
      onPageChange(currentPage + 1);
    }
  };

  return (
    <div className="flex flex-col gap-3 border-t border-border/40 bg-background/60 px-4 py-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <span>
        {hasData
          ? t(`${keyPrefix}.${scope === 'global' ? 'summary' : 'range'}`, {
              start: startItem,
              end: endItem,
              total: totalItems,
            })
          : t(`${keyPrefix}.empty`)}
      </span>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handlePrev}
          disabled={disablePrev}
        >
          {t(`${keyPrefix}.previous`)}
        </Button>
        <span>{t(`${keyPrefix}.page`, { current: currentPage, total: safeTotalPages })}</span>
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handleNext}
          disabled={disableNext}
        >
          {t(`${keyPrefix}.next`)}
        </Button>
      </div>
    </div>
  );
};
