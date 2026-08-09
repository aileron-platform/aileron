import React from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  PlatformKnowledgeBaseSummary,
  PlatformResourceKind,
  PlatformResourceSummary,
  PlatformWorkspaceSummary,
} from '../model/platformResourceTypes';
import { formatPlatformResourceCapacity } from '../model/formatPlatformResourceCapacity';

interface Props {
  kind: PlatformResourceKind;
  items: PlatformResourceSummary[];
  isLoading: boolean;
  hasError: boolean;
  detailRoute: (resource: PlatformResourceSummary) => string;
  onReassign: (resource: PlatformResourceSummary) => void;
  onManageQuota: (resource: PlatformKnowledgeBaseSummary) => void;
  onExpand: (resource: PlatformWorkspaceSummary) => void;
  canReassignOwner: boolean;
  canManageKnowledgeBaseQuota: boolean;
  canExpandWorkspaceCapacity: boolean;
}

const isWorkspace = (resource: PlatformResourceSummary): resource is PlatformWorkspaceSummary => (
  'runtimeStatus' in resource
);

const capacityText = (used: number | null, allocated: number | null): string => (
  allocated == null
    ? formatPlatformResourceCapacity(used)
    : `${formatPlatformResourceCapacity(used)} / ${formatPlatformResourceCapacity(allocated)}`
);

const riskBadge = (risk: string): { variant: 'secondary' | 'outline' | 'destructive'; className?: string } => {
  if (risk === 'critical') return { variant: 'destructive' };
  if (risk === 'warning') {
    return { variant: 'outline', className: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300' };
  }
  if (risk === 'stale') {
    return { variant: 'outline', className: 'border-orange-500/35 bg-orange-500/10 text-orange-700 dark:text-orange-300' };
  }
  if (risk === 'unknown') return { variant: 'outline', className: 'border-muted-foreground/30 text-muted-foreground' };
  return { variant: 'secondary' };
};

export const PlatformResourceInventoryTable: React.FC<Props> = ({
  kind,
  items,
  isLoading,
  hasError,
  detailRoute,
  onReassign,
  onManageQuota,
  onExpand,
  canReassignOwner,
  canManageKnowledgeBaseQuota,
  canExpandWorkspaceCapacity,
}) => {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full min-w-[960px] text-sm">
        <thead className="border-b bg-muted/40 text-left">
          <tr>
            <th className="px-4 py-3 font-medium">{t('platformResources.columns.name')}</th>
            <th className="px-4 py-3 font-medium">{t('platformResources.columns.owner')}</th>
            <th className="px-4 py-3 font-medium">
              {kind === 'workspaces'
                ? t('platformResources.columns.runtimeStatus')
                : t('platformResources.columns.visibility')}
            </th>
            <th className="px-4 py-3 font-medium">{t('platformResources.columns.capacity')}</th>
            <th className="px-4 py-3 font-medium">{t('platformResources.columns.capacityRisk')}</th>
            <th className="px-4 py-3 text-right font-medium">{t('platformResources.columns.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr><td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>{t('common.loading')}</td></tr>
          ) : hasError ? (
            <tr><td className="px-4 py-10 text-center text-destructive" colSpan={6}>{t('platformResources.errors.load')}</td></tr>
          ) : items.length === 0 ? (
            <tr><td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>{t('platformResources.empty')}</td></tr>
          ) : items.map(resource => {
            const workspace = isWorkspace(resource) ? resource : null;
            const knowledgeBase = workspace ? null : resource as PlatformKnowledgeBaseSummary;
            const state = workspace
              ? (workspace.runtimeStatus
                  ? t(`platformResources.runtimeStatus.${workspace.runtimeStatus}`)
                  : t('platformResources.runtimeStatus.unknown'))
              : t(`platformResources.visibility.${knowledgeBase.visibility}`);
            const risk = workspace ? workspace.capacityRisk : knowledgeBase.capacityRisk;
            const riskAppearance = riskBadge(risk);
            return (
              <tr key={resource.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{resource.name}</td>
                <td className="px-4 py-3">
                  <div>{resource.owner.displayName || resource.owner.username}</div>
                  <div className="text-xs text-muted-foreground">@{resource.owner.username}</div>
                </td>
                <td className="px-4 py-3"><Badge variant="outline">{state}</Badge></td>
                <td className="px-4 py-3">
                  {workspace ? (
                    <div className="space-y-1">
                      <div>{workspace.workspaceData
                        ? capacityText(workspace.workspaceData.usedBytes, workspace.workspaceData.allocatedBytes)
                        : '—'}</div>
                      <div className="text-xs text-muted-foreground">
                        {t('platformResources.capacity.runtimeHome')}: {workspace.runtimeHome
                          ? capacityText(workspace.runtimeHome.usedBytes, workspace.runtimeHome.allocatedBytes)
                          : '—'}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <div>{capacityText(knowledgeBase.currentSizeBytes, knowledgeBase.effectiveQuotaBytes)}</div>
                      <div className="text-xs text-muted-foreground">
                        {t(`platformResources.capacity.quotaSources.${knowledgeBase.quotaSource}`)}
                      </div>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={riskAppearance.variant} className={riskAppearance.className}>
                    {t(`platformResources.capacity.risks.${risk}`)}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <Button asChild variant="outline" size="sm">
                      <Link to={detailRoute(resource)}>{t('platformResources.actions.viewDetails')}</Link>
                    </Button>
                    {workspace && canExpandWorkspaceCapacity ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!workspace.workspaceData?.expansionSupported && !workspace.runtimeHome?.expansionSupported}
                        onClick={() => onExpand(workspace)}
                      >
                        {t('platformResources.actions.expandCapacity')}
                      </Button>
                    ) : knowledgeBase && canManageKnowledgeBaseQuota ? (
                      <Button variant="outline" size="sm" onClick={() => onManageQuota(knowledgeBase)}>
                        {t('platformResources.actions.manageQuota')}
                      </Button>
                    ) : null}
                    {canReassignOwner ? (
                      <Button variant="outline" size="sm" onClick={() => onReassign(resource)}>
                        {t('platformResources.actions.reassignOwner')}
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
