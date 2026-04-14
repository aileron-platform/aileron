/**
 * FirewallSettingsView - 基本防火牆設定組件
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Plus, X, Shield, Save } from 'lucide-react';
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
import { apiClient } from '@/shared/api/apiClient';

interface FirewallConfigResponse {
  workspace?: FirewallRuleResponse | null;
  browser?: FirewallRuleResponse | null;
}

interface FirewallRuleResponse {
  networkAccessEnabled?: boolean;
  domainAccessMode?: 'all' | 'specific';
  allowedDomains?: string[];
  effectiveAllowedDomains?: string[];
}

interface WorkspaceDetailResponse {
  firewallAvailable?: boolean;
  firewallUnavailableReason?: string | null;
  firewall?: FirewallConfigResponse | null;
}

interface FirewallRuleFormState {
  networkAccessEnabled: boolean;
  domainAccessMode: 'all' | 'specific';
  allowedDomains: string[];
  effectiveAllowedDomains: string[];
}

interface FirewallFormState {
  workspace: FirewallRuleFormState;
  browser: FirewallRuleFormState;
}

const mapRuleResponseToFormState = (
  firewall: FirewallRuleResponse | null | undefined
): FirewallRuleFormState => ({
  networkAccessEnabled: firewall?.networkAccessEnabled ?? true,
  domainAccessMode: firewall?.domainAccessMode ?? 'all',
  allowedDomains: [...(firewall?.allowedDomains ?? [])],
  effectiveAllowedDomains: [...(firewall?.effectiveAllowedDomains ?? firewall?.allowedDomains ?? [])],
});

const mapResponseToFormState = (
  firewall: FirewallConfigResponse | null | undefined
): FirewallFormState => ({
  workspace: mapRuleResponseToFormState(firewall?.workspace),
  browser: mapRuleResponseToFormState(firewall?.browser),
});

const toComparableState = (state: FirewallFormState | null) => {
  if (!state) {
    return null;
  }
  return JSON.stringify({
    workspace: {
      networkAccessEnabled: state.workspace.networkAccessEnabled,
      domainAccessMode: state.workspace.domainAccessMode,
      allowedDomains: [...state.workspace.allowedDomains].sort(),
    },
    browser: {
      networkAccessEnabled: state.browser.networkAccessEnabled,
      domainAccessMode: state.browser.domainAccessMode,
      allowedDomains: [...state.browser.allowedDomains].sort(),
    },
  });
};

export const FirewallSettingsView: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId;

  const [settings, setSettings] = useState<FirewallFormState | null>(null);
  const [initialState, setInitialState] = useState<FirewallFormState | null>(null);
  const [newDomains, setNewDomains] = useState<Record<'workspace' | 'browser', string>>({
    workspace: '',
    browser: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [firewallAvailable, setFirewallAvailable] = useState(
    import.meta.env.VITE_CILIUM_ENABLED === 'true'
  );
  const [firewallUnavailableReason, setFirewallUnavailableReason] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadFirewallSettings = async () => {
      if (!workspaceId) {
        setSettings(null);
        setInitialState(null);
        setError(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const data = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`
        );
        if (!isActive) {
          return;
        }

        const normalized = mapResponseToFormState(data.firewall);
        setFirewallAvailable(data.firewallAvailable ?? import.meta.env.VITE_CILIUM_ENABLED === 'true');
        setFirewallUnavailableReason(data.firewallUnavailableReason ?? null);
        setSettings(normalized);
        setInitialState(normalized);
      } catch (err) {
        if (!isActive) {
          return;
        }
        const message =
          err instanceof Error && err.message
            ? err.message
            : t('workspace.containerManagement.firewall.notifications.loadFailed');
        setError(message);
        setFirewallAvailable(import.meta.env.VITE_CILIUM_ENABLED === 'true');
        setFirewallUnavailableReason(null);
        setSettings(null);
        setInitialState(null);
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
  }, [workspaceId, t]);

  const handleNetworkAccessChange = (
    group: 'workspace' | 'browser',
    enabled: boolean
  ) => {
    setSettings((current) =>
      current
        ? {
            ...current,
            [group]: { ...current[group], networkAccessEnabled: enabled },
          }
        : current
    );
  };

  const handleDomainAccessModeChange = (
    group: 'workspace' | 'browser',
    mode: 'all' | 'specific'
  ) => {
    setSettings((current) =>
      current
        ? {
            ...current,
            [group]: { ...current[group], domainAccessMode: mode },
          }
        : current
    );
  };

  const addDomain = (group: 'workspace' | 'browser') => {
    const domain = newDomains[group].trim();
    if (!domain) {
      return;
    }
    setSettings((current) => {
      if (!current || current[group].allowedDomains.includes(domain)) {
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
  };

  const removeDomain = (group: 'workspace' | 'browser', domain: string) => {
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

  const handleSave = async () => {
    if (!workspaceId || !settings || !firewallAvailable) {
      return;
    }

    setIsSaving(true);
    setError(null);

    const payload = {
      firewall: {
        workspace: {
          networkAccessEnabled: settings.workspace.networkAccessEnabled,
          domainAccessMode: settings.workspace.domainAccessMode,
          allowedDomains: settings.workspace.allowedDomains,
        },
        browser: {
          networkAccessEnabled: settings.browser.networkAccessEnabled,
          domainAccessMode: settings.browser.domainAccessMode,
          allowedDomains: settings.browser.allowedDomains,
        },
      },
    };

    try {
      const data = await apiClient.put<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`,
        payload
      );
      const normalized = mapResponseToFormState(data.firewall);
      setFirewallAvailable(data.firewallAvailable ?? firewallAvailable);
      setFirewallUnavailableReason(data.firewallUnavailableReason ?? null);
      setSettings(normalized);
      setInitialState(normalized);

      toast({
        title: t('workspace.containerManagement.firewall.header.title'),
        description: t('workspace.containerManagement.firewall.notifications.saveSuccess'),
      });
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : t('workspace.containerManagement.firewall.notifications.saveFailed');
      setError(message);
      toast({
        title: t('workspace.containerManagement.firewall.header.title'),
        description: t('workspace.containerManagement.firewall.notifications.saveFailed'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const isSaveDisabled =
    isSaving ||
    isLoading ||
    !workspaceId ||
    !settings ||
    !firewallAvailable ||
    !isDirty;

  const renderFirewallGroup = (
    group: 'workspace' | 'browser',
    groupSettings: FirewallRuleFormState
  ) => (
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
        <Label>{t('workspace.containerManagement.firewall.networkAccess.label')}</Label>
        <Select
          value={groupSettings.networkAccessEnabled ? 'enabled' : 'disabled'}
          onValueChange={(value) => handleNetworkAccessChange(group, value === 'enabled')}
          disabled={!firewallAvailable}
        >
          <SelectTrigger>
            <SelectValue>
              <div className="flex items-center gap-2">
                <Badge className={groupSettings.networkAccessEnabled
                  ? 'bg-primary/10 dark:bg-primary/15 text-primary dark:text-primary-foreground border-primary/20 dark:border-primary/30'
                  : 'bg-gray-100 dark:bg-gray-900/20 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800'
                }>
                  {groupSettings.networkAccessEnabled
                    ? t('workspace.containerManagement.firewall.networkAccess.badge.enabled')
                    : t('workspace.containerManagement.firewall.networkAccess.badge.disabled')
                  }
                </Badge>
              </div>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="enabled">
              <div className="flex items-center gap-2">
                <Badge className="bg-primary/10 dark:bg-primary/15 text-primary dark:text-primary-foreground border-primary/20 dark:border-primary/30">
                  {t('workspace.containerManagement.firewall.networkAccess.badge.enabled')}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.firewall.networkAccess.options.enabled.description')}
                </span>
              </div>
            </SelectItem>
            <SelectItem value="disabled">
              <div className="flex items-center gap-2">
                <Badge className="bg-gray-100 dark:bg-gray-900/20 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800">
                  {t('workspace.containerManagement.firewall.networkAccess.badge.disabled')}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('workspace.containerManagement.firewall.networkAccess.options.disabled.description')}
                </span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {groupSettings.networkAccessEnabled && (
        <>
          <div className="space-y-2">
            <Label>{t('workspace.containerManagement.firewall.domainAccessMode.label')}</Label>
            <Select
              value={groupSettings.domainAccessMode}
              onValueChange={(value) =>
                handleDomainAccessModeChange(group, value as 'all' | 'specific')
              }
              disabled={!firewallAvailable}
            >
              <SelectTrigger>
                <SelectValue>
                  <div className="flex items-center gap-2">
                    <Badge className={groupSettings.domainAccessMode === 'all'
                      ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                      : 'bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800'
                    }>
                      {groupSettings.domainAccessMode === 'all'
                        ? t('workspace.containerManagement.firewall.domainAccessMode.badge.all')
                        : t('workspace.containerManagement.firewall.domainAccessMode.badge.specific')
                      }
                    </Badge>
                  </div>
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800">
                      {t('workspace.containerManagement.firewall.domainAccessMode.badge.all')}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {t('workspace.containerManagement.firewall.domainAccessMode.options.all.description')}
                    </span>
                  </div>
                </SelectItem>
                <SelectItem value="specific">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800">
                      {t('workspace.containerManagement.firewall.domainAccessMode.badge.specific')}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {t('workspace.containerManagement.firewall.domainAccessMode.options.specific.description')}
                    </span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {groupSettings.domainAccessMode === 'specific' && (
            <div className="space-y-2">
              <Label>{t('workspace.containerManagement.firewall.allowedDomains.label')}</Label>
              {groupSettings.allowedDomains.map((domain) => (
                <div key={`${group}-${domain}`} className="flex items-center gap-2">
                  <Input value={domain} readOnly className="flex-1" />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => removeDomain(group, domain)}
                    disabled={!firewallAvailable}
                    className="border-border text-foreground hover:bg-muted"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}

              <div className="flex gap-2">
                <Input
                  placeholder={t('workspace.containerManagement.firewall.allowedDomains.placeholder')}
                  value={newDomains[group]}
                  disabled={!firewallAvailable}
                  onChange={(e) =>
                    setNewDomains((current) => ({ ...current, [group]: e.target.value }))
                  }
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
                  disabled={!firewallAvailable}
                  className="border-border text-foreground hover:bg-muted"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('workspace.containerManagement.firewall.allowedDomains.add')}
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <div className="space-y-2">
        <Label>{t('workspace.containerManagement.firewall.effectiveAllowedDomains.label')}</Label>
        {groupSettings.effectiveAllowedDomains.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {groupSettings.effectiveAllowedDomains.map((domain) => (
              <Badge key={`${group}-effective-${domain}`} variant="secondary">
                {domain}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {t('workspace.containerManagement.firewall.effectiveAllowedDomains.empty')}
          </p>
        )}
      </div>
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-background">
      <FeatureHeader
        title={t('workspace.containerManagement.firewall.header.title')}
        icon={Shield}
        actions={
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
        }
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

export default FirewallSettingsView;
