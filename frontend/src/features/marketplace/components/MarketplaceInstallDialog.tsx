import React from 'react';
import {
  CheckCircle2,
  Copy,
  Download,
  Info,
  PackageCheck,
  RefreshCw,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageSummary } from '../model/marketplaceTypes';
import {
  getMarketplaceFeatureLabelKey,
  getMarketplacePackageFeatures,
} from '../model/marketplaceFeatureLabels';
import { getMarketplaceInstallCommandName } from '../model/marketplacePackageActionModel';
import { useMarketplaceInstallWorkflow } from '../install-workflow/useMarketplaceInstallWorkflow';
import { MarketplaceInstallOutput } from './MarketplaceInstallOutput';
import {
  getMarketplaceInstallErrorKey,
  getMarketplaceInstallResourceTypeLabelKey,
  getMarketplaceSkippedReasonKey,
  MARKETPLACE_DELIVERY_METHODS,
  marketplaceBlockingIssueGroups,
  marketplaceResourceTypeCounts,
} from './marketplaceInstallModel';

interface MarketplaceInstallDialogProps {
  open: boolean;
  item: MarketplacePackageSummary;
  onOpenChange: (open: boolean) => void;
  onItemRefresh?: (item: MarketplacePackageSummary) => void;
}

export const MarketplaceInstallDialog: React.FC<MarketplaceInstallDialogProps> = ({
  open,
  item,
  onOpenChange,
  onItemRefresh,
}) => {
  const { t } = useI18n();
  const { state, send } = useMarketplaceInstallWorkflow({
    open,
    item,
    onItemRefresh,
  });
  const currentItem = state.item ?? item;
  const {
    workspaceId,
    workspaceOptions,
    workspaceLoading: isLoadingWorkspaces,
    workspaceLoadFailed,
    deliveryMethod,
    preflight: userCopyPreflight,
    preflightLoading: isLoadingPreflight,
    preflightErrorCode,
    pluginResult,
    userCopyResult,
    overwriteConfirmed,
    releaseVersion,
    releaseVersionValid,
    installErrorContext,
    isWorkspaceTargetClientEnabled,
    requiresOverwriteConfirmation,
    isPreflightEligible,
    canRun,
    visibleErrorCode,
    succeeded,
  } = state;
  const deliveryFailed =
    state.status === 'failed' && state.failureKind === 'delivery';
  const commandName = getMarketplaceInstallCommandName(
    currentItem.userCopyTargetClient,
    t,
  );
  const resourceTypeCounts =
    marketplaceResourceTypeCounts(userCopyPreflight ?? null);
  const blockingIssueGroups =
    marketplaceBlockingIssueGroups(userCopyPreflight ?? null);
  const pluginFeatureBadges = getMarketplacePackageFeatures(currentItem);
  const plannedCreatedResourceCount = userCopyPreflight?.resources.filter(
    resource => resource.operation === 'create',
  ).length ?? 0;
  const plannedMergedResourceCount = userCopyPreflight?.resources.filter(
    resource => resource.operation === 'merge',
  ).length ?? 0;
  const plannedUnchangedResourceCount = userCopyPreflight?.resources.filter(
    resource => resource.operation === 'unchanged',
  ).length ?? 0;
  const hasDetailedBlockingIssues = (
    deliveryMethod === 'user-copy'
    && Boolean(userCopyPreflight?.blockingIssues.length)
  );
  const visibleErrorKey = getMarketplaceInstallErrorKey(visibleErrorCode);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,760px)] max-w-2xl flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogHeading icon={Download}>
            {t('marketplace.install.title')}
          </DialogHeading>
          <DialogDescription>
            {t('marketplace.install.description')}
          </DialogDescription>
        </DialogHeader>

        <div
          className="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1"
          data-testid="marketplace-install-scroll-body"
        >
          <div className="grid gap-3 rounded-md border border-border p-3 text-sm md:grid-cols-2">
            <div>
              <div className="text-xs text-muted-foreground">
                {t('marketplace.install.fields.packageFormat')}
              </div>
              <div className="font-mono">{currentItem.packageFormat}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">
                {t('marketplace.install.fields.package')}
              </div>
              <div className="font-mono">{currentItem.packageId}</div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="marketplace-install-workspace">
              {t('marketplace.install.fields.workspace')}
            </Label>
            <Select
              value={workspaceId}
              onValueChange={value => void send({
                type: 'select-workspace',
                workspaceId: value,
              })}
              disabled={state.workspaceSelectionDisabled}
            >
              <SelectTrigger id="marketplace-install-workspace">
                <SelectValue
                  placeholder={t('marketplace.install.workspaceSelect.placeholder')}
                />
              </SelectTrigger>
              <SelectContent>
                {workspaceOptions.length > 0 ? (
                  workspaceOptions.map(workspace => (
                    <SelectItem key={workspace.id} value={workspace.id}>
                      {workspace.label}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value={workspaceId}>
                    {isLoadingWorkspaces
                      ? t('marketplace.install.workspaceSelect.loading')
                      : t('marketplace.install.workspaceSelect.currentWorkspace')}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
            {workspaceLoadFailed ? (
              <Alert variant="destructive">
                <Info className="h-4 w-4" />
                <AlertDescription className="flex items-center justify-between gap-3">
                  <span>{t('marketplace.install.workspaceSelect.loadFailed')}</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void send({ type: 'reload-workspaces' })}
                    disabled={isLoadingWorkspaces}
                  >
                    <RefreshCw
                      className={`mr-1.5 h-4 w-4 ${
                        isLoadingWorkspaces ? 'animate-spin' : ''
                      }`}
                    />
                    {t('marketplace.install.actions.refresh')}
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label>{t('marketplace.install.fields.deliveryMethod')}</Label>
            <div
              className="grid gap-3 md:grid-cols-2"
              role="radiogroup"
              aria-label={t('marketplace.install.fields.deliveryMethod')}
            >
              {MARKETPLACE_DELIVERY_METHODS.map(method => {
                const selected = deliveryMethod === method;
                const Icon = method === 'plugin' ? PackageCheck : Copy;
                return (
                  <button
                    key={method}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={`rounded-md border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                      selected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    }`}
                    onClick={() => void send({
                      type: 'select-delivery',
                      deliveryMethod: method,
                    })}
                    disabled={state.deliverySelectionDisabled}
                  >
                    <span className="flex items-center gap-2 font-medium">
                      <Icon className="h-4 w-4" />
                      {t(`marketplace.install.deliveryMethods.${method}.title`)}
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {method === 'plugin'
                        ? t('marketplace.install.deliveryMethods.plugin.description', {
                          commandName,
                        })
                        : t(
                          'marketplace.install.deliveryMethods.user-copy.description',
                        )}
                    </span>
                    {method === 'plugin' ? (
                      <span className="mt-3 block space-y-2">
                        <span className="block text-xs font-medium">
                          {pluginFeatureBadges.length > 0
                            ? t(
                              'marketplace.install.deliveryMethods.plugin.inventory',
                            )
                            : t(
                              'marketplace.install.deliveryMethods.plugin.capabilitySummary',
                            )}
                        </span>
                        {pluginFeatureBadges.length > 0 ? (
                          <span className="flex flex-wrap gap-1.5">
                            {pluginFeatureBadges.map(feature => (
                              <Badge key={feature} variant="secondary">
                                {t(getMarketplaceFeatureLabelKey(
                                  currentItem.targetClient,
                                  feature,
                                ))}
                              </Badge>
                            ))}
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>

          {deliveryMethod === 'plugin' ? (
            <div className="space-y-2">
              <Label htmlFor="marketplace-install-release-version">
                {t('marketplace.install.fields.releaseVersion')}
              </Label>
              <Input
                id="marketplace-install-release-version"
                value={releaseVersion}
                onChange={event => void send({
                  type: 'set-release-version',
                  version: event.target.value,
                })}
                disabled={state.deliverySelectionDisabled}
                aria-invalid={!releaseVersionValid}
                placeholder="1.2.3"
              />
              <p className="text-xs text-muted-foreground">
                {t('marketplace.install.plugin.releaseVersionDescription')}
              </p>
              {!releaseVersionValid ? (
                <p className="text-xs text-destructive">
                  {t('marketplace.install.errors.releaseVersionInvalid')}
                </p>
              ) : null}
            </div>
          ) : null}

          {!isLoadingWorkspaces && !isWorkspaceTargetClientEnabled ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t('marketplace.install.targetClientNotEnabled')}
              </AlertDescription>
            </Alert>
          ) : null}

          {isWorkspaceTargetClientEnabled && !hasDetailedBlockingIssues ? (
            <Alert
              variant={
                preflightErrorCode
                || userCopyPreflight?.status === 'blocked'
                  ? 'destructive'
                  : 'default'
              }
            >
              {isPreflightEligible ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <Info className="h-4 w-4" />
              )}
              <AlertDescription>
                {deliveryMethod === 'plugin'
                  ? t('marketplace.install.plugin.publishReady')
                  : isLoadingPreflight
                  ? t('marketplace.install.preflight.loading')
                  : requiresOverwriteConfirmation
                    ? t('marketplace.install.preflight.confirmationRequired')
                    : isPreflightEligible
                      ? t('marketplace.install.preflight.ready')
                      : t(visibleErrorKey)}
              </AlertDescription>
            </Alert>
          ) : null}

          {preflightErrorCode ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void send({ type: 'refresh-preflight' })}
              disabled={isLoadingPreflight}
            >
              <RefreshCw
                className={`mr-1.5 h-4 w-4 ${
                  isLoadingPreflight ? 'animate-spin' : ''
                }`}
              />
              {t('marketplace.install.actions.refresh')}
            </Button>
          ) : null}

          {userCopyPreflight ? (
            <section className="space-y-3 rounded-md border border-border p-3">
              <div>
                <h3 className="text-sm font-medium">
                  {t('marketplace.install.profile.title')}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {t('marketplace.install.profile.summary', {
                    count: userCopyPreflight.resources.length,
                  })}
                </p>
                <dl className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                  <div><dt className="inline">{t('marketplace.install.fields.packageFormat')}: </dt><dd className="inline font-mono">{userCopyPreflight.packageFormat}</dd></div>
                  <div><dt className="inline">{t('marketplace.install.fields.targetClient')}: </dt><dd className="inline font-mono">{userCopyPreflight.targetClient}</dd></div>
                </dl>
                <p className="mt-2 text-xs text-muted-foreground">
                  {t('marketplace.install.profile.workspaceSharedStandalone')}
                </p>
              </div>
              {resourceTypeCounts.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {resourceTypeCounts.map(([resourceType, count]) => (
                    <Badge key={resourceType} variant="secondary">
                      {t(getMarketplaceInstallResourceTypeLabelKey(
                        currentItem.userCopyTargetClient,
                        resourceType,
                      ))}: {count}
                    </Badge>
                  ))}
                </div>
              ) : null}
              <p className="text-xs">
                {t('marketplace.install.profile.operationSummary', {
                  created: plannedCreatedResourceCount,
                  merged: plannedMergedResourceCount,
                  unchanged: plannedUnchangedResourceCount,
                })}
              </p>
              {userCopyPreflight.resources.length > 0 ? (
                <ul className="max-h-48 space-y-2 overflow-y-auto text-xs">
                  {userCopyPreflight.resources.map(resource => (
                    <li
                      key={[
                        resource.resourceType,
                        resource.resourceId,
                        resource.targetLocator,
                      ].join(':')}
                      className="rounded bg-muted/40 px-2 py-1.5"
                    >
                      <div className="font-medium">
                        {t(getMarketplaceInstallResourceTypeLabelKey(
                          currentItem.userCopyTargetClient,
                          resource.resourceType,
                        ))}
                        {' · '}
                        {resource.resourceId}
                        {' · '}
                        {t(`marketplace.install.operations.${resource.operation}`)}
                      </div>
                      <div className="font-mono text-muted-foreground">
                        {resource.targetLocator}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
              {userCopyPreflight.conflicts.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">
                    {t('marketplace.install.conflicts.title')}
                  </h4>
                  <p className="text-xs text-muted-foreground">
                    {t('marketplace.install.conflicts.description')}
                  </p>
                  <ul className="max-h-48 space-y-2 overflow-y-auto text-xs">
                    {userCopyPreflight.conflicts.map(conflict => (
                      <li
                        key={conflict.targetIdentity}
                        className="rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5"
                      >
                        <div className="font-medium">
                          {t(getMarketplaceInstallResourceTypeLabelKey(
                            currentItem.userCopyTargetClient,
                            conflict.resourceType,
                          ))}
                          {' · '}
                          {conflict.resourceId}
                        </div>
                        <dl className="mt-1 grid gap-1 text-muted-foreground">
                          <div>
                            <dt className="inline">
                              {t('marketplace.install.conflicts.source')}
                              {': '}
                            </dt>
                            <dd className="inline font-mono">
                              {conflict.sourceLocator}
                            </dd>
                          </div>
                          <div>
                            <dt className="inline">
                              {t('marketplace.install.conflicts.target')}
                              {': '}
                            </dt>
                            <dd className="inline font-mono">
                              {conflict.targetLocator}
                            </dd>
                          </div>
                        </dl>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {userCopyPreflight.skippedResources.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">
                    {t('marketplace.install.skipped.title')}
                  </h4>
                  <ul className="space-y-2 text-xs">
                    {userCopyPreflight.skippedResources.map(resource => (
                      <li key={`${resource.resourceType}:${resource.resourceId}`} className="rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5">
                        <div className="font-medium">{resource.resourceId}</div>
                        <div className="text-muted-foreground">
                          <span className="font-mono">{resource.sourceLocator}</span>
                          {' · '}
                          {t(getMarketplaceSkippedReasonKey(resource.code))}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {requiresOverwriteConfirmation ? (
                <div className="flex items-start gap-3 rounded-md border border-amber-500/40 p-3">
                  <Checkbox
                    id="marketplace-user-copy-confirm"
                    checked={overwriteConfirmed}
                    onCheckedChange={checked => void send({
                      type: 'set-overwrite-confirmed',
                      confirmed: checked === true,
                    })}
                  />
                  <Label htmlFor="marketplace-user-copy-confirm">
                    {userCopyPreflight.skippedResources.length > 0
                      ? t('marketplace.install.skipped.confirmPartial')
                      : t('marketplace.install.conflicts.confirmOverwrite')}
                  </Label>
                </div>
              ) : null}
              {blockingIssueGroups.map(issue => (
                <Alert
                  key={issue.errorCode}
                  variant="destructive"
                >
                  <Info className="h-4 w-4" />
                  <AlertDescription className="space-y-1">
                    <div>{t(getMarketplaceInstallErrorKey(issue.errorCode))}</div>
                    {issue.count > 1 ? (
                      <div className="text-xs">
                        {t(
                          'marketplace.install.blockingIssues.affectedResources',
                          { count: issue.count },
                        )}
                      </div>
                    ) : null}
                  </AlertDescription>
                </Alert>
              ))}
            </section>
          ) : null}

          {succeeded ? (
            <div className="space-y-3">
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>
                  {pluginResult
                    ? t('marketplace.install.result.success.plugin')
                    : t('marketplace.install.result.success.user-copy')}
                </AlertDescription>
              </Alert>
              {userCopyResult ? (
                <section className="rounded-md border border-border p-3">
                  <dl className="grid gap-3 text-xs sm:grid-cols-2">
                    {([
                      ['created', userCopyResult.createdCount],
                      ['merged', userCopyResult.mergedCount],
                      ['unchanged', userCopyResult.unchangedCount],
                      ['overwritten', userCopyResult.overwrittenCount],
                      ['skipped', userCopyResult.skippedCount],
                    ] as const).map(([operation, count]) => (
                      <div key={operation}>
                        <dt className="text-muted-foreground">
                          {t(`marketplace.install.result.counts.${operation}`)}
                        </dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ) : null}
            </div>
          ) : null}

          {deliveryFailed ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {pluginResult?.cliMessage
                  ?? (
                    pluginResult
                      ? t('marketplace.install.result.failure.plugin')
                      : t(visibleErrorKey)
                  )}
              </AlertDescription>
            </Alert>
          ) : null}

          {visibleErrorCode || installErrorContext ? (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">
                {t('marketplace.install.diagnostics.title')}
              </summary>
              {visibleErrorCode ? (
                <code className="mt-2 block break-all rounded bg-muted p-2">
                  {visibleErrorCode}
                </code>
              ) : null}
              {installErrorContext ? (
                <dl className="mt-2 grid gap-1 rounded bg-muted p-2">
                  <div>
                    <dt className="inline font-medium">
                      {t('marketplace.install.diagnostics.stage')}:
                    </dt>{' '}
                    <dd className="inline font-mono">{installErrorContext.stage}</dd>
                  </div>
                  <div>
                    <dt className="inline font-medium">
                      {t('marketplace.install.diagnostics.category')}:
                    </dt>{' '}
                    <dd className="inline font-mono">{installErrorContext.category}</dd>
                  </div>
                  {installErrorContext.source ? (
                    <div>
                      <dt className="inline font-medium">
                        {t('marketplace.install.diagnostics.source')}:
                      </dt>{' '}
                      <dd className="inline break-all font-mono">
                        {installErrorContext.source}
                      </dd>
                    </div>
                  ) : null}
                  {installErrorContext.destination ? (
                    <div>
                      <dt className="inline font-medium">
                        {t('marketplace.install.diagnostics.destination')}:
                      </dt>{' '}
                      <dd className="inline break-all font-mono">
                        {installErrorContext.destination}
                      </dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </details>
          ) : null}

          {pluginResult ? (
            <MarketplaceInstallOutput result={pluginResult} />
          ) : null}
        </div>

        <DialogFooter className="shrink-0">
          {succeeded ? (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('marketplace.common.actions.close')}
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t('marketplace.common.actions.cancel')}
              </Button>
              <Button
                onClick={() => void send({ type: 'run' })}
                disabled={
                  state.status === 'running'
                  || isLoadingPreflight
                  || !canRun
                }
              >
                {state.status === 'running' ? (
                  <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" />
                ) : deliveryMethod === 'plugin' ? (
                  <Download className="mr-1.5 h-4 w-4" />
                ) : (
                  <Copy className="mr-1.5 h-4 w-4" />
                )}
                {deliveryFailed
                  ? t('marketplace.install.actions.retry')
                  : deliveryMethod === 'plugin'
                  ? t('marketplace.install.actions.install')
                  : userCopyPreflight?.skippedResources.length
                    ? t('marketplace.install.actions.acceptPartialAndCopy')
                  : requiresOverwriteConfirmation
                    ? t('marketplace.install.actions.overwriteAndCopy')
                    : t('marketplace.install.actions.copy')}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
