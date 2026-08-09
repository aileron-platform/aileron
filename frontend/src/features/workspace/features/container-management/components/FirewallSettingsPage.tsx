/**
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  CheckCircle2,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  Shield,
  TriangleAlert,
  X,
} from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { apiClient, ApiError } from '@/shared/api/apiClient';
import type {
  FirewallEgressMode,
  FirewallResourceResponse,
  FirewallRuleResponse,
} from '@/features/workspace/api/workspaceApiTypes';
import { getFirewallErrorI18nKey } from '../model/firewallErrorI18n';

interface FirewallRuleFormValues {
  egressMode: FirewallEgressMode;
  allowedDomains: string[];
}

interface FirewallFormValues {
  workspace: FirewallRuleFormValues;
  browser: FirewallRuleFormValues;
}

type FirewallGroup = keyof FirewallFormValues;

export const FIREWALL_POLL_INTERVAL_MS = 1_500;

const HOSTNAME_LABEL_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
const NUMERIC_ADDRESS_PATTERN = /^\d+(?:\.\d+){1,3}$/;

export const normalizeExactHostname = (value: string): string | null => {
  const normalized = value.trim().toLowerCase().replace(/\.$/, '');
  if (
    !normalized
    || normalized.length > 253
    || normalized.includes('://')
    || /[/*?#:@%]/.test(normalized)
    || NUMERIC_ADDRESS_PATTERN.test(normalized)
  ) {
    return null;
  }

  let asciiHostname: string;
  try {
    asciiHostname = new URL(`http://${normalized}`).hostname
      .toLowerCase()
      .replace(/\.$/, '');
  } catch {
    return null;
  }

  if (
    !asciiHostname
    || asciiHostname.length > 253
    || asciiHostname.split('.').some(label => !HOSTNAME_LABEL_PATTERN.test(label))
  ) {
    return null;
  }
  return asciiHostname;
};

const mapRuleResponseToFormValues = (
  firewall: FirewallRuleResponse
): FirewallRuleFormValues => ({
  egressMode: firewall.egressMode,
  allowedDomains: [...firewall.allowedDomains],
});

const mapResponseToFormValues = (
  firewall: FirewallResourceResponse
): FirewallFormValues => ({
  workspace: mapRuleResponseToFormValues(firewall.workspace),
  browser: mapRuleResponseToFormValues(firewall.browser),
});

const toComparableState = (state: FirewallFormValues | null) => {
  if (!state) {
    return null;
  }
  return JSON.stringify({
    workspace: {
      egressMode: state.workspace.egressMode,
      allowedDomains: [...state.workspace.allowedDomains].sort(),
    },
    browser: {
      egressMode: state.browser.egressMode,
      allowedDomains: [...state.browser.allowedDomains].sort(),
    },
  });
};

const isFirewallApplying = (
  status: FirewallResourceResponse['syncStatus'] | null,
  revision: number | null,
  observedRevision: number | null,
) =>
  status === 'pending'
  || status === 'applying'
  || (
    status === 'applied'
    && revision !== null
    && observedRevision !== revision
  );

const isFirewallApplied = (
  status: FirewallResourceResponse['syncStatus'] | null,
  revision: number | null,
  observedRevision: number | null,
) =>
  status === 'applied'
  && revision !== null
  && observedRevision === revision;

export const FirewallSettingsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, permissions } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;
  const canManageFirewall = permissions.canManageFirewall;

  const [settings, setSettings] = useState<FirewallFormValues | null>(null);
  const [revision, setRevision] = useState<number | null>(null);
  const [observedRevision, setObservedRevision] = useState<number | null>(null);
  const [syncStatus, setSyncStatus] =
    useState<FirewallResourceResponse['syncStatus'] | null>(null);
  const [syncErrorCode, setSyncErrorCode] = useState<string | null>(null);
  const [pendingAppliedRevision, setPendingAppliedRevision] = useState<number | null>(null);
  const [initialState, setInitialState] = useState<FirewallFormValues | null>(null);
  const [newDomains, setNewDomains] = useState<Record<FirewallGroup, string>>({
    workspace: '',
    browser: '',
  });
  const [domainErrors, setDomainErrors] = useState<Record<FirewallGroup, string | null>>({
    workspace: null,
    browser: null,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [firewallAvailable, setFirewallAvailable] = useState(false);
  const [firewallUnavailableReason, setFirewallUnavailableReason] = useState<string | null>(null);
  const lastAppliedToastRevisionRef = useRef<number | null>(null);
  const isApplying = isFirewallApplying(syncStatus, revision, observedRevision);
  const isApplied = isFirewallApplied(syncStatus, revision, observedRevision);

  const getErrorMessage = useCallback((err: unknown, fallbackKey: string) => {
    if (err instanceof ApiError) {
      const errorI18nKey = getFirewallErrorI18nKey(err.errorCode);
      if (errorI18nKey) {
        return t(errorI18nKey);
      }
    }
    return t(fallbackKey);
  }, [t]);

  const applyResource = useCallback((data: FirewallResourceResponse) => {
    const normalized = mapResponseToFormValues(data);
    setRevision(data.revision);
    setObservedRevision(data.observedRevision);
    setSyncStatus(data.syncStatus);
    setSyncErrorCode(data.errorCode ?? null);
    setFirewallAvailable(data.syncStatus !== 'unavailable');
    setFirewallUnavailableReason(
      data.syncStatus === 'unavailable' ? data.errorCode ?? null : null,
    );
    setSettings(normalized);
    setInitialState(normalized);
  }, []);

  useEffect(() => {
    let isActive = true;

    const loadFirewallSettings = async () => {
      if (!workspaceId) {
        setSettings(null);
        setInitialState(null);
        setError(null);
        setRevision(null);
        setObservedRevision(null);
        setSyncStatus(null);
        setSyncErrorCode(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const data = await apiClient.get<FirewallResourceResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/firewall`
        );
        if (!isActive) {
          return;
        }

        applyResource(data);
      } catch (err) {
        if (!isActive) {
          return;
        }
        setError(getErrorMessage(
          err,
          'workspace.containerManagement.firewall.notifications.loadFailed',
        ));
        setFirewallAvailable(false);
        setFirewallUnavailableReason(null);
        setSettings(null);
        setInitialState(null);
        setRevision(null);
        setObservedRevision(null);
        setSyncStatus(null);
        setSyncErrorCode(null);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadFirewallSettings();

    return () => {
      isActive = false;
    };
  }, [applyResource, getErrorMessage, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !isApplying) {
      return;
    }

    let isActive = true;
    let timerId: number | null = null;

    function scheduleNextPoll() {
      timerId = window.setTimeout(() => {
        void poll();
      }, FIREWALL_POLL_INTERVAL_MS);
    }

    async function poll() {
      try {
        const data = await apiClient.get<FirewallResourceResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/firewall`,
        );
        if (!isActive) {
          return;
        }
        applyResource(data);
        setError(null);
        if (
          isFirewallApplying(
            data.syncStatus,
            data.revision,
            data.observedRevision,
          )
        ) {
          scheduleNextPoll();
        }
      } catch (err) {
        if (!isActive) {
          return;
        }
        setError(getErrorMessage(
          err,
          'workspace.containerManagement.firewall.notifications.refreshFailed',
        ));
        const isStableClientError =
          err instanceof ApiError
          && err.status >= 400
          && err.status < 500
          && err.status !== 408
          && err.status !== 429;
        if (!isStableClientError) {
          scheduleNextPoll();
        }
      }
    }

    scheduleNextPoll();
    return () => {
      isActive = false;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
    };
  }, [applyResource, getErrorMessage, isApplying, workspaceId]);

  useEffect(() => {
    if (
      pendingAppliedRevision !== null
      && revision !== null
      && revision > pendingAppliedRevision
    ) {
      setPendingAppliedRevision(null);
      return;
    }
    if (
      pendingAppliedRevision === null
      || syncStatus !== 'applied'
      || revision !== pendingAppliedRevision
      || observedRevision !== pendingAppliedRevision
      || lastAppliedToastRevisionRef.current === pendingAppliedRevision
    ) {
      return;
    }

    lastAppliedToastRevisionRef.current = pendingAppliedRevision;
    toast({
      title: t('workspace.containerManagement.firewall.header.title'),
      description: t('workspace.containerManagement.firewall.notifications.applied'),
    });
    setPendingAppliedRevision(null);
  }, [observedRevision, pendingAppliedRevision, revision, syncStatus, t, toast]);

  const handleEgressModeChange = (
    group: FirewallGroup,
    egressMode: FirewallEgressMode
  ) => {
    if (!canManageFirewall) {
      return;
    }
    setSettings((current) =>
      current
        ? {
            ...current,
            [group]: {
              ...current[group],
              egressMode,
              allowedDomains:
                egressMode === 'allowlist'
                  ? current[group].allowedDomains
                  : [],
            },
          }
        : current
    );
  };

  const addDomain = (group: FirewallGroup) => {
    if (!canManageFirewall) {
      return;
    }
    const domain = normalizeExactHostname(newDomains[group]);
    if (!domain) {
      setDomainErrors(current => ({
        ...current,
        [group]: t('workspace.containerManagement.firewall.allowedDomains.invalid'),
      }));
      return;
    }
    if (settings?.[group].allowedDomains.includes(domain)) {
      setDomainErrors(current => ({
        ...current,
        [group]: t('workspace.containerManagement.firewall.allowedDomains.duplicate'),
      }));
      return;
    }
    setSettings((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [group]: {
          ...current[group],
          allowedDomains: [...current[group].allowedDomains, domain],
        },
      };
    });
    setNewDomains((current) => ({ ...current, [group]: '' }));
    setDomainErrors(current => ({ ...current, [group]: null }));
  };

  const removeDomain = (group: FirewallGroup, domain: string) => {
    if (!canManageFirewall) {
      return;
    }
    setSettings((current) =>
      current
        ? {
            ...current,
            [group]: {
              ...current[group],
              allowedDomains: current[group].allowedDomains.filter((item) => item !== domain),
            },
          }
        : current
    );
  };

  const isDirty = useMemo(() => toComparableState(settings) !== toComparableState(initialState), [settings, initialState]);
  const hasEmptyAllowlist = useMemo(
    () =>
      settings !== null
      && (
        (
          settings.workspace.egressMode === 'allowlist'
          && settings.workspace.allowedDomains.length === 0
        )
        || (
          settings.browser.egressMode === 'allowlist'
          && settings.browser.allowedDomains.length === 0
        )
      ),
    [settings],
  );
  const syncErrorI18nKey = getFirewallErrorI18nKey(syncErrorCode);

  const handleSave = async () => {
    if (
      !workspaceId
      || !canManageFirewall
      || !settings
      || revision === null
      || !firewallAvailable
      || hasEmptyAllowlist
    ) {
      return;
    }

    setIsSaving(true);
    setError(null);

    const payload = {
      revision,
      workspace: {
        egressMode: settings.workspace.egressMode,
        allowedDomains: settings.workspace.allowedDomains,
      },
      browser: {
        egressMode: settings.browser.egressMode,
        allowedDomains: settings.browser.allowedDomains,
      },
    };

    try {
      const data = await apiClient.put<FirewallResourceResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/firewall`,
        payload
      );
      applyResource(data);
      setPendingAppliedRevision(data.revision);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const latest = await apiClient.get<FirewallResourceResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}/firewall`
        );
        applyResource(latest);
        setError(t('workspace.containerManagement.firewall.notifications.revisionConflict'));
        toast({
          title: t('workspace.containerManagement.firewall.header.title'),
          description: t('workspace.containerManagement.firewall.notifications.revisionConflict'),
          variant: 'destructive',
        });
        return;
      }
      setError(getErrorMessage(
        err,
        'workspace.containerManagement.firewall.notifications.saveFailed',
      ));
      toast({
        title: t('workspace.containerManagement.firewall.header.title'),
        description: t('workspace.containerManagement.firewall.notifications.saveFailed'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRetry = async () => {
    if (!workspaceId || !canManageFirewall || syncStatus !== 'error') {
      return;
    }

    setIsRetrying(true);
    setError(null);
    try {
      const data = await apiClient.post<FirewallResourceResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}/firewall/retry`,
      );
      applyResource(data);
      setPendingAppliedRevision(data.revision);
    } catch (err) {
      setError(getErrorMessage(
        err,
        'workspace.containerManagement.firewall.notifications.retryFailed',
      ));
    } finally {
      setIsRetrying(false);
    }
  };

  const isSaveDisabled =
    isSaving ||
    isRetrying ||
    isApplying ||
    isLoading ||
    !canManageFirewall ||
    !workspaceId ||
    !settings ||
    revision === null ||
    !firewallAvailable ||
    hasEmptyAllowlist ||
    !isDirty;

  const renderFirewallGroup = (
    group: FirewallGroup,
    groupSettings: FirewallRuleFormValues
  ) => {
    const controlsDisabled =
      !canManageFirewall || !firewallAvailable || isSaving || isRetrying || isApplying;
    const allowlistRequiredError =
      canManageFirewall
      && groupSettings.egressMode === 'allowlist'
      && groupSettings.allowedDomains.length === 0
        ? t('workspace.containerManagement.firewall.allowedDomains.required')
        : null;
    const domainError = domainErrors[group] ?? allowlistRequiredError;

    return (
    <div className="space-y-5 rounded-lg border border-border/70 bg-card/60 p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">
          {t(`workspace.containerManagement.firewall.groups.${group}.title`)}
        </h3>
        <p className="text-xs text-muted-foreground">
          {t(`workspace.containerManagement.firewall.groups.${group}.description`)}
        </p>
      </div>

      <div className="space-y-2">
        <Label>{t('workspace.containerManagement.firewall.egressMode.label')}</Label>
        {canManageFirewall ? (
        <Select
          value={groupSettings.egressMode}
          onValueChange={(value) =>
            handleEgressModeChange(group, value as FirewallEgressMode)
          }
          disabled={controlsDisabled}
        >
          <SelectTrigger>
            <SelectValue>
              <div className="flex items-center gap-2">
                <Badge className={
                  groupSettings.egressMode === 'unrestricted'
                    ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                    : groupSettings.egressMode === 'allowlist'
                      ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800'
                      : 'bg-gray-100 dark:bg-gray-900/20 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800'
                }>
                  {t(
                    `workspace.containerManagement.firewall.egressMode.options.${groupSettings.egressMode}.label`,
                  )}
                </Badge>
              </div>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="blocked">
              <div className="flex items-center gap-2">
                <Badge className="bg-gray-100 dark:bg-gray-900/20 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800">
                  {t('workspace.containerManagement.firewall.egressMode.options.blocked.label')}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.firewall.egressMode.options.blocked.description')}
                </span>
              </div>
            </SelectItem>
            <SelectItem value="allowlist">
              <div className="flex items-center gap-2">
                <Badge className="bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800">
                  {t('workspace.containerManagement.firewall.egressMode.options.allowlist.label')}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.firewall.egressMode.options.allowlist.description')}
                </span>
              </div>
            </SelectItem>
            <SelectItem value="unrestricted">
              <div className="flex items-center gap-2">
                <Badge className="bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800">
                  {t('workspace.containerManagement.firewall.egressMode.options.unrestricted.label')}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.firewall.egressMode.options.unrestricted.description')}
                </span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
        ) : (
          <Badge className={
            groupSettings.egressMode === 'unrestricted'
              ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800'
              : groupSettings.egressMode === 'allowlist'
                ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800'
                : 'bg-gray-100 dark:bg-gray-900/20 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800'
          }>
            {t(
              `workspace.containerManagement.firewall.egressMode.options.${groupSettings.egressMode}.label`,
            )}
          </Badge>
        )}
      </div>

      {groupSettings.egressMode === 'allowlist' && (
            <div className="space-y-2">
              <Label>{t('workspace.containerManagement.firewall.allowedDomains.label')}</Label>
              {groupSettings.allowedDomains.map((domain) => (
                <div key={`${group}-${domain}`} className="flex items-center gap-2">
                  <Input value={domain} readOnly className="flex-1" />
                  {canManageFirewall ? (
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => removeDomain(group, domain)}
                    disabled={controlsDisabled}
                    aria-label={t(
                      'workspace.containerManagement.firewall.allowedDomains.remove',
                      { domain }
                    )}
                    title={t(
                      'workspace.containerManagement.firewall.allowedDomains.remove',
                      { domain }
                    )}
                    className="border-border text-foreground hover:bg-muted"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  ) : null}
                </div>
              ))}

              {canManageFirewall ? (
              <div className="flex gap-2">
                <Input
                  placeholder={t('workspace.containerManagement.firewall.allowedDomains.placeholder')}
                  value={newDomains[group]}
                  disabled={controlsDisabled}
                  aria-invalid={domainError ? true : undefined}
                  onChange={(e) => {
                    setNewDomains((current) => ({ ...current, [group]: e.target.value }));
                    setDomainErrors(current => ({ ...current, [group]: null }));
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addDomain(group);
                    }
                  }}
                  className="flex-1"
                />
                <Button
                  onClick={() => addDomain(group)}
                  variant="outline"
                  disabled={controlsDisabled}
                  className="border-border text-foreground hover:bg-muted"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.containerManagement.firewall.allowedDomains.add')}
                </Button>
              </div>
              ) : null}
              <p className="text-xs text-muted-foreground">
                {t('workspace.containerManagement.firewall.allowedDomains.exactHostnameHint')}
              </p>
              {domainError ? (
                <p role="alert" className="text-xs text-destructive">
                  {domainError}
                </p>
              ) : null}
            </div>
      )}

    </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-background">
      <FeatureHeader
        title={t('workspace.containerManagement.firewall.header.title')}
        icon={Shield}
        actions={canManageFirewall ? (
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleSave}
            disabled={isSaveDisabled}
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {isSaving
              ? t('workspace.containerManagement.firewall.header.actions.saving')
              : t('workspace.containerManagement.firewall.header.actions.save')}
          </Button>
        ) : undefined}
      />
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {error && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          {isApplying && (
            <Alert>
              <Loader2 className="h-4 w-4 animate-spin" />
              <AlertTitle>
                {t('workspace.containerManagement.firewall.sync.applying.title')}
              </AlertTitle>
              <AlertDescription>
                {t('workspace.containerManagement.firewall.sync.applying.description', {
                  observedRevision: observedRevision ?? 0,
                  desiredRevision: revision ?? 0,
                })}
              </AlertDescription>
            </Alert>
          )}

          {isApplied && revision !== null && (
            <div
              role="status"
              className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-foreground"
            >
              <CheckCircle2 className="h-4 w-4 text-primary" />
              {t('workspace.containerManagement.firewall.sync.applied', {
                revision,
              })}
            </div>
          )}

          {syncStatus === 'error' && (
            <Alert variant="destructive">
              <TriangleAlert className="h-4 w-4" />
              <AlertTitle>
                {t('workspace.containerManagement.firewall.sync.failed.title')}
              </AlertTitle>
              <AlertDescription className="space-y-3">
                <p>
                  {syncErrorI18nKey
                    ? t(syncErrorI18nKey)
                    : t('workspace.containerManagement.firewall.sync.failed.description')}
                </p>
                {syncErrorCode ? (
                  <code className="block break-all text-xs">{syncErrorCode}</code>
                ) : null}
                {canManageFirewall ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void handleRetry();
                  }}
                  disabled={isRetrying}
                >
                  <RotateCcw className={`mr-2 h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
                  {isRetrying
                    ? t('workspace.containerManagement.firewall.sync.failed.retrying')
                    : t('workspace.containerManagement.firewall.sync.failed.retry')}
                </Button>
                ) : null}
              </AlertDescription>
            </Alert>
          )}

          {!firewallAvailable && (
            <Alert>
              <Shield className="h-4 w-4" />
              <AlertTitle>{t('workspace.containerManagement.firewall.unavailable.title')}</AlertTitle>
              <AlertDescription>
                {firewallUnavailableReason
                  ? t(`workspace.containerManagement.firewall.unavailable.reasons.${firewallUnavailableReason}`, {
                      defaultValue: t('workspace.containerManagement.firewall.unavailable.description'),
                    })
                  : t('workspace.containerManagement.firewall.unavailable.description')}
              </AlertDescription>
            </Alert>
          )}

          {isLoading ? (
            <p className="text-sm text-muted-foreground">
              {t('workspace.containerManagement.firewall.status.loading')}
            </p>
          ) : settings ? (
            <>
              <div className="space-y-4">
                {renderFirewallGroup('workspace', settings.workspace)}
                {renderFirewallGroup('browser', settings.browser)}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('workspace.containerManagement.firewall.status.empty')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default FirewallSettingsPage;
