import React, { useMemo, useCallback } from 'react';
import {
  Shield,
  Key,
  Plus,
  Trash2,
  AlertCircle,
  RefreshCw,
  Save,
  Loader2,
  Cpu,
  Building,
  User,
  HardDrive,
  Puzzle,
  ChevronDown,
  ChevronRight,
  Package,
  GitCommit,
  Globe2,
  ServerCog,
  ListChecks,
  Ban,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import type { ClaudeCodeSettingsScope } from '../services/claudeCodeApi';
import { useSettingsState } from '../hooks/useSettingsState';

const SettingsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;

  // 使用 settings state hook
  const settings = useSettingsState();

  // UI 配置
  const permissionModes = useMemo(
    () => [
      {
        value: 'default',
        label: t('workspace.claudeCode.permissions.modes.default.label'),
        description: t('workspace.claudeCode.permissions.modes.default.description'),
      },
      {
        value: 'acceptEdits',
        label: t('workspace.claudeCode.permissions.modes.acceptEdits.label'),
        description: t('workspace.claudeCode.permissions.modes.acceptEdits.description'),
      },
      {
        value: 'plan',
        label: t('workspace.claudeCode.permissions.modes.plan.label'),
        description: t('workspace.claudeCode.permissions.modes.plan.description'),
      },
      {
        value: 'bypassPermissions',
        label: t('workspace.claudeCode.permissions.modes.bypassPermissions.label'),
        description: t('workspace.claudeCode.permissions.modes.bypassPermissions.description'),
      },
    ],
    [t],
  );

  const selectedModeOption = useMemo(
    () => permissionModes.find((item) => item.value === settings.mode) ?? permissionModes[0],
    [settings.mode, permissionModes],
  );

  const scopeLabels = useMemo<Record<ClaudeCodeSettingsScope, string>>(
    () => ({
      project: t('workspace.claudeCode.permissions.scope.options.project'),
      user: t('workspace.claudeCode.permissions.scope.options.user'),
      local: t('workspace.claudeCode.permissions.scope.options.local'),
    }),
    [t],
  );

  const scopeOrder = useMemo<ClaudeCodeSettingsScope[]>(
    () => ['project', 'user', 'local'],
    [],
  );

  const scopeIconMap = useMemo<Record<ClaudeCodeSettingsScope, React.ComponentType<{ className?: string }>>>(
    () => ({
      project: Building,
      user: User,
      local: HardDrive,
    }),
    [],
  );

  // 事件處理
  const handleRefresh = useCallback(() => {
    if (!settings.isRuntimeReady) {
      const message = runtimeError
        ? t('workspace.claudeCode.permissions.status.runtimeUnavailable', { message: runtimeError })
        : t('workspace.claudeCode.permissions.status.runtimeMissing');
      toast({
        variant: 'destructive',
        title: message,
      });
      return;
    }
    void settings.fetchSettings();
  }, [settings, runtimeError, t, toast]);

  const getPluginKey = useCallback((marketplaceName: string, pluginName: string) => {
    return `${pluginName}@${marketplaceName}`;
  }, []);

  const runtimeLoadingMessage = runtimeLoading && !settings.isRuntimeReady
    ? t('workspace.claudeCode.permissions.status.runtimeLoading')
    : null;

  const runtimeUnavailableMessage = runtimeError
    ? t('workspace.claudeCode.permissions.status.runtimeUnavailable', { message: runtimeError })
    : null;

  const runtimeMissingMessage = !runtimeError && !settings.isRuntimeReady
    ? t('workspace.claudeCode.permissions.status.runtimeMissing')
    : null;

  const renderStatusCard = (
    icon: React.ReactNode,
    title: string,
    description?: string,
    showRetry?: boolean,
  ) => (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        {icon}
      </div>
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      </div>
      {showRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={handleRefresh} disabled={settings.refreshDisabled}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('workspace.claudeCode.permissions.actions.refresh')}
        </Button>
      ) : null}
    </div>
  );

  let mainContent: React.ReactNode;

  if (runtimeUnavailableMessage) {
    mainContent = renderStatusCard(
      <AlertCircle className="h-6 w-6 text-destructive" />,
      runtimeUnavailableMessage,
    );
  } else if (runtimeLoadingMessage) {
    mainContent = renderStatusCard(
      <Loader2 className="h-6 w-6 animate-spin text-primary" />,
      runtimeLoadingMessage,
    );
  } else if (runtimeMissingMessage) {
    mainContent = renderStatusCard(
      <AlertCircle className="h-6 w-6 text-muted-foreground" />,
      runtimeMissingMessage,
    );
  } else if (settings.isLoading) {
    mainContent = renderStatusCard(
      <Loader2 className="h-6 w-6 animate-spin text-primary" />,
      t('workspace.claudeCode.permissions.status.loading'),
    );
  } else if (settings.loadError) {
    mainContent = renderStatusCard(
      <AlertCircle className="h-6 w-6 text-destructive" />,
      t('workspace.claudeCode.permissions.status.loadFailed'),
      settings.loadError,
      true,
    );
  } else {
    mainContent = (
      <Tabs
        value={settings.activeTab}
        onValueChange={(value) => settings.setActiveTab(value as 'basic' | 'plugins' | 'rules' | 'mcp')}
        className="space-y-6"
      >
        <TabsList className="grid h-10 w-full grid-cols-1 gap-2 rounded-lg bg-muted/50 p-1 sm:grid-cols-4">
          <TabsTrigger
            value="basic"
            className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
          >
            <Shield className="h-4 w-4" />
            {t('workspace.claudeCode.permissions.tabs.basic')}
          </TabsTrigger>
          <TabsTrigger
            value="plugins"
            className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
          >
            <Puzzle className="h-4 w-4" />
            {t('workspace.claudeCode.permissions.tabs.plugins')}
          </TabsTrigger>
          <TabsTrigger
            value="rules"
            className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
          >
            <AlertCircle className="h-4 w-4" />
            {t('workspace.claudeCode.permissions.tabs.rules')}
          </TabsTrigger>
          <TabsTrigger
            value="mcp"
            className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
          >
            <ServerCog className="h-4 w-4" />
            {t('workspace.claudeCode.permissions.tabs.mcp')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="mt-0">
          <div className="space-y-4">
            {/* API Key Helper */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Key className="h-5 w-5 text-primary" />
                  <h3 className="text-base font-semibold text-foreground">
                    {t('workspace.claudeCode.permissions.basic.apiKeyHelper.title')}
                  </h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('workspace.claudeCode.permissions.basic.apiKeyHelper.description')}
                </p>
                <div className="space-y-2">
                  <Label htmlFor="claude-code-api-key-helper">
                    {t('workspace.claudeCode.permissions.basic.apiKeyHelper.label')}
                  </Label>
                  <Input
                    id="claude-code-api-key-helper"
                    placeholder={t('workspace.claudeCode.permissions.basic.apiKeyHelper.placeholder')}
                    value={settings.apiKeyHelper}
                    onChange={(event) => settings.setApiKeyHelper(event.target.value)}
                    disabled={settings.inputsDisabled}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.basic.apiKeyHelper.helper')}
                  </p>
                </div>
              </div>
            </div>

            {/* Cleanup Period */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <RefreshCw className="h-5 w-5 text-primary" />
                  <h3 className="text-base font-semibold text-foreground">
                    {t('workspace.claudeCode.permissions.basic.cleanup.label')}
                  </h3>
                </div>
                <div className="space-y-2">
                  <Input
                    id="claude-code-cleanup-period"
                    type="number"
                    min={0}
                    placeholder={t('workspace.claudeCode.permissions.basic.cleanup.placeholder')}
                    value={settings.cleanupPeriodDays}
                    onChange={(event) => settings.setCleanupPeriodDays(event.target.value)}
                    disabled={settings.inputsDisabled}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.basic.cleanup.helper')}
                  </p>
                </div>
              </div>
            </div>

            {/* Model */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-primary" />
                  <div className="flex-1">
                    <h3 className="text-base font-semibold text-foreground">
                      {t('workspace.claudeCode.permissions.model.title')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.claudeCode.permissions.basic.modelDescription')}
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="claude-code-model">
                    {t('workspace.claudeCode.permissions.model.label')}
                  </Label>
                  <Input
                    id="claude-code-model"
                    placeholder={t('workspace.claudeCode.permissions.model.placeholder')}
                    value={settings.model}
                    onChange={(event) => settings.setModel(event.target.value)}
                    disabled={settings.inputsDisabled}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.model.helper')}
                  </p>
                </div>
              </div>
            </div>

            {/* Output Style */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Package className="h-5 w-5 text-primary" />
                  <h3 className="text-base font-semibold text-foreground">
                    {t('workspace.claudeCode.permissions.outputStyle.label')}
                  </h3>
                </div>
                <div className="space-y-2">
                  <Select
                    value={settings.outputStyle || '__none__'}
                    onValueChange={(value) => settings.setOutputStyle(value === '__none__' ? '' : value)}
                    disabled={settings.inputsDisabled}
                  >
                    <SelectTrigger id="claude-code-output-style" className="w-full">
                      <SelectValue placeholder={t('workspace.claudeCode.permissions.outputStyle.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">{t('workspace.claudeCode.permissions.outputStyle.none')}</SelectItem>
                      {settings.outputStyleOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.outputStyle.helper')}
                  </p>
                </div>
              </div>
            </div>

            {/* Include Co-Authored-By */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <GitCommit className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
                  <div className="flex-1 space-y-1">
                    <h3 className="text-base font-semibold text-foreground">
                      {t('workspace.claudeCode.permissions.basic.includeCoAuthoredBy.label')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.claudeCode.permissions.basic.includeCoAuthoredBy.description')}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={settings.includeCoAuthoredBy}
                  onCheckedChange={(checked) => settings.setIncludeCoAuthoredBy(checked)}
                  disabled={settings.inputsDisabled}
                  className="flex-shrink-0"
                />
              </div>
            </div>

            {/* Disable All Hooks */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
                  <div className="flex-1 space-y-1">
                    <h3 className="text-base font-semibold text-foreground">
                      {t('workspace.claudeCode.permissions.basic.disableAllHooks.label')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.claudeCode.permissions.basic.disableAllHooks.description')}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={settings.disableAllHooks}
                  onCheckedChange={(checked) => settings.setDisableAllHooks(checked)}
                  disabled={settings.inputsDisabled}
                  className="flex-shrink-0"
                />
              </div>
            </div>

            {/* Environment Variables */}
            <div className="rounded-lg border border-border bg-background p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Globe2 className="h-5 w-5 text-primary" />
                  <div>
                    <h3 className="text-base font-semibold text-foreground">
                      {t('workspace.claudeCode.permissions.basic.env.title')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.claudeCode.permissions.basic.env.description')}
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  {settings.envVars.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {t('workspace.claudeCode.permissions.basic.env.empty')}
                    </p>
                  ) : (
                    settings.envVars.map((envVar, index) => (
                      <div
                        key={`env-${index}`}
                        className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                      >
                        <div className="space-y-1">
                          <Label htmlFor={`env-key-${index}`}>
                            {t('workspace.claudeCode.permissions.basic.env.keyLabel')}
                          </Label>
                          <Input
                            id={`env-key-${index}`}
                            value={envVar.key}
                            onChange={(event) => settings.updateEnvVar(index, 'key', event.target.value)}
                            placeholder={t('workspace.claudeCode.permissions.basic.env.keyPlaceholder')}
                            disabled={settings.inputsDisabled}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor={`env-value-${index}`}>
                            {t('workspace.claudeCode.permissions.basic.env.valueLabel')}
                          </Label>
                          <Input
                            id={`env-value-${index}`}
                            value={envVar.value}
                            onChange={(event) => settings.updateEnvVar(index, 'value', event.target.value)}
                            placeholder={t('workspace.claudeCode.permissions.basic.env.valuePlaceholder')}
                            disabled={settings.inputsDisabled}
                          />
                        </div>
                        <div className="flex items-end justify-end">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => settings.removeEnvVar(index)}
                            disabled={settings.inputsDisabled}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={settings.addEnvVar}
                    disabled={settings.inputsDisabled}
                    className="w-full sm:w-fit"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    {t('workspace.claudeCode.permissions.basic.env.add')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="plugins" className="mt-0 space-y-4">
          <div className="rounded-lg border border-border bg-background p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Puzzle className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">
                {t('workspace.claudeCode.permissions.plugins.title')}
              </h3>
            </div>

            <div className="space-y-4">
              {settings.marketplaces.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  <Package className="mx-auto mb-2 h-12 w-12 opacity-50" />
                  <p>{t('workspace.claudeCode.permissions.plugins.emptyTitle')}</p>
                  <p className="text-sm">{t('workspace.claudeCode.permissions.plugins.emptyDescription')}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {settings.marketplaces.map((marketplace) => {
                    const isExpanded = settings.expandedMarketplaces.has(marketplace.name);
                    return (
                      <div key={marketplace.name} className="overflow-hidden rounded-lg border border-border">
                        <button
                          type="button"
                          onClick={() => settings.toggleMarketplace(marketplace.name)}
                          disabled={settings.inputsDisabled}
                          className="flex w-full items-center justify-between gap-2 bg-muted/50 px-4 py-3 transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <div className="flex min-w-0 flex-1 items-center gap-3">
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                            )}
                            <Package className="h-5 w-5 flex-shrink-0 text-primary" />
                            <div className="min-w-0 flex-1 text-left">
                              <div className="truncate font-semibold text-foreground">{marketplace.name}</div>
                              <div className="truncate text-xs text-muted-foreground">
                                {marketplace.metadata.description} • v{marketplace.metadata.version}
                              </div>
                            </div>
                          </div>
                          <div className="flex-shrink-0 text-xs text-muted-foreground">
                            {t('workspace.claudeCode.permissions.plugins.count', {
                              count: marketplace.plugins.length,
                            })}
                          </div>
                        </button>

                        {isExpanded ? (
                          <div className="space-y-1 bg-background p-2">
                            {marketplace.plugins.map((plugin) => {
                              const pluginKey = getPluginKey(marketplace.name, plugin.name);
                              const isEnabled = settings.enabledPlugins[pluginKey] ?? false;
                              return (
                                <div
                                  key={plugin.name}
                                  className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 transition-colors hover:bg-muted/40"
                                >
                                  <div className="flex min-w-0 flex-1 items-center gap-3">
                                    <Switch
                                      checked={isEnabled}
                                      onCheckedChange={() => settings.togglePlugin(pluginKey)}
                                      disabled={settings.inputsDisabled}
                                    />
                                    <div className="min-w-0 flex-1">
                                      <div className="truncate text-sm font-medium text-foreground">{plugin.name}</div>
                                      <div className="truncate text-xs text-muted-foreground">
                                        {plugin.description} • v{plugin.version}
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}

              <p className="text-xs text-muted-foreground">
                {t('workspace.claudeCode.permissions.plugins.helper')}
              </p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="rules" className="mt-0 space-y-4">
          <div className="rounded-lg border border-border bg-background p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">
                {t('workspace.claudeCode.permissions.modes.title')}
              </h3>
            </div>

            <div className="space-y-2">
              <Label htmlFor="claude-code-mode-rules">
                {t('workspace.claudeCode.permissions.modes.fieldLabel')}
              </Label>
              <Select
                value={settings.mode}
                onValueChange={settings.setMode}
                disabled={settings.inputsDisabled}
              >
                <SelectTrigger id="claude-code-mode-rules" className="w-full">
                  <SelectValue>{selectedModeOption?.label ?? settings.mode}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {permissionModes.map((modeOption) => (
                    <SelectItem key={modeOption.value} value={modeOption.value}>
                      <div className="space-y-1">
                        <div className="font-medium">{modeOption.label}</div>
                        <div className="text-sm text-muted-foreground">{modeOption.description}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-6 space-y-6">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">
                {t('workspace.claudeCode.permissions.rules.title')}
              </h3>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-green-600 dark:text-green-400">
                    {t('workspace.claudeCode.permissions.allowRules.title')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('workspace.claudeCode.permissions.allowRules.placeholder')}
                    value={settings.newAllowRule}
                    onChange={(e) => settings.setNewAllowRule(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !settings.inputsDisabled) {
                        e.preventDefault();
                        settings.addRule(settings.newAllowRule, 'allow');
                      }
                    }}
                    disabled={settings.inputsDisabled}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    onClick={() => settings.addRule(settings.newAllowRule, 'allow')}
                    size="sm"
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.allowRules.length > 0 ? (
                  <div className="space-y-2">
                    {settings.allowRules.map((rule) => (
                      <div
                        key={rule}
                        className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-900/20"
                      >
                        <code className="font-mono text-sm text-green-700 dark:text-green-300">{rule}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeRule(rule, 'allow')}
                          className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-muted-foreground">
                    <AlertCircle className="mx-auto mb-2 h-8 w-8 opacity-50" />
                    <p>{t('workspace.claudeCode.permissions.allowRules.empty')}</p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-red-600 dark:text-red-400">
                    {t('workspace.claudeCode.permissions.denyRules.title')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('workspace.claudeCode.permissions.denyRules.placeholder')}
                    value={settings.newDenyRule}
                    onChange={(e) => settings.setNewDenyRule(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !settings.inputsDisabled) {
                        e.preventDefault();
                        settings.addRule(settings.newDenyRule, 'deny');
                      }
                    }}
                    disabled={settings.inputsDisabled}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    onClick={() => settings.addRule(settings.newDenyRule, 'deny')}
                    size="sm"
                    variant="destructive"
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.denyRules.length > 0 ? (
                  <div className="space-y-2">
                    {settings.denyRules.map((rule) => (
                      <div
                        key={rule}
                        className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20"
                      >
                        <code className="font-mono text-sm text-red-700 dark:text-red-300">{rule}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeRule(rule, 'deny')}
                          className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-muted-foreground">
                    <AlertCircle className="mx-auto mb-2 h-8 w-8 opacity-50" />
                    <p>{t('workspace.claudeCode.permissions.denyRules.empty')}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
                  {t('workspace.claudeCode.permissions.askRules.title')}
                </span>
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={t('workspace.claudeCode.permissions.askRules.placeholder')}
                  value={settings.newAskRule}
                  onChange={(event) => settings.setNewAskRule(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !settings.inputsDisabled) {
                      event.preventDefault();
                      settings.addRule(settings.newAskRule, 'ask');
                    }
                  }}
                  disabled={settings.inputsDisabled}
                  className="flex-1"
                />
                <Button
                  type="button"
                  onClick={() => settings.addRule(settings.newAskRule, 'ask')}
                  size="sm"
                  variant="outline"
                  className="border-amber-500 text-amber-600 hover:bg-amber-50 dark:border-amber-400 dark:text-amber-200 dark:hover:bg-amber-900/20"
                  disabled={settings.inputsDisabled}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {settings.askRules.length > 0 ? (
                <div className="space-y-2">
                  {settings.askRules.map((rule) => (
                    <div
                      key={rule}
                      className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20"
                    >
                      <code className="font-mono text-sm text-amber-700 dark:text-amber-200">{rule}</code>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => settings.removeRule(rule, 'ask')}
                        className="text-amber-600 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-900/20"
                        disabled={settings.inputsDisabled}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-muted-foreground">
                  <AlertCircle className="mx-auto mb-2 h-8 w-8 opacity-50" />
                  <p>{t('workspace.claudeCode.permissions.askRules.empty')}</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-blue-600 dark:text-blue-400">
                  {t('workspace.claudeCode.permissions.directoryRules.title')}
                </span>
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={t('workspace.claudeCode.permissions.directoryRules.placeholder')}
                  value={settings.newAdditionalDirectory}
                  onChange={(event) => settings.setNewAdditionalDirectory(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !settings.inputsDisabled) {
                      event.preventDefault();
                      settings.addDirectory(settings.newAdditionalDirectory);
                    }
                  }}
                  disabled={settings.inputsDisabled}
                  className="flex-1"
                />
                <Button
                  type="button"
                  onClick={() => settings.addDirectory(settings.newAdditionalDirectory)}
                  size="sm"
                  variant="outline"
                  className="border-blue-500 text-blue-600 hover:bg-blue-50 dark:border-blue-400 dark:text-blue-200 dark:hover:bg-blue-900/20"
                  disabled={settings.inputsDisabled}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {settings.additionalDirectories.length > 0 ? (
                <div className="space-y-2">
                  {settings.additionalDirectories.map((directory) => (
                    <div
                      key={directory}
                      className="flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-900/20"
                    >
                      <code className="font-mono text-sm text-blue-700 dark:text-blue-200">{directory}</code>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => settings.removeDirectory(directory)}
                        className="text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:hover:bg-blue-900/20"
                        disabled={settings.inputsDisabled}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-muted-foreground">
                  <AlertCircle className="mx-auto mb-2 h-8 w-8 opacity-50" />
                  <p>{t('workspace.claudeCode.permissions.directoryRules.empty')}</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="mcp" className="mt-0 space-y-4">
          <div className="rounded-lg border border-border bg-background p-6 space-y-4">
            <div className="flex items-start gap-3">
              <ServerCog className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-foreground">
                  {t('workspace.claudeCode.permissions.mcp.autoApprove.title')}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {t('workspace.claudeCode.permissions.mcp.autoApprove.description')}
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                {t('workspace.claudeCode.permissions.mcp.autoApprove.helper')}
              </p>
              <Switch
                checked={settings.enableAllProjectMcpServers}
                onCheckedChange={(checked) => settings.setEnableAllProjectMcpServers(checked)}
                disabled={settings.inputsDisabled}
              />
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-6 space-y-6">
            <div className="flex items-center gap-2">
              <ListChecks className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">
                {t('workspace.claudeCode.permissions.mcp.mcpjson.title')}
              </h3>
            </div>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label htmlFor="mcp-enabled-json">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.enabled.label')}
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.enabled.helper')}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Input
                    id="mcp-enabled-json"
                    placeholder={t('workspace.claudeCode.permissions.mcp.mcpjson.enabled.placeholder')}
                    value={settings.newEnabledMcpjsonServer}
                    onChange={(event) => settings.setNewEnabledMcpjsonServer(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !settings.inputsDisabled) {
                        event.preventDefault();
                        settings.addEnabledMcpjsonServer(settings.newEnabledMcpjsonServer);
                      }
                    }}
                    disabled={settings.inputsDisabled}
                  />
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => settings.addEnabledMcpjsonServer(settings.newEnabledMcpjsonServer)}
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.enabledMcpjsonServers.length > 0 ? (
                  <div className="space-y-2">
                    {settings.enabledMcpjsonServers.map((server) => (
                      <div
                        key={server}
                        className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-900/20"
                      >
                        <code className="font-mono text-sm text-emerald-700 dark:text-emerald-200">{server}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeEnabledMcpjsonServer(server)}
                          className="text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.enabled.empty')}
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <div className="space-y-1">
                  <Label htmlFor="mcp-disabled-json">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.disabled.label')}
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.disabled.helper')}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Input
                    id="mcp-disabled-json"
                    placeholder={t('workspace.claudeCode.permissions.mcp.mcpjson.disabled.placeholder')}
                    value={settings.newDisabledMcpjsonServer}
                    onChange={(event) => settings.setNewDisabledMcpjsonServer(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !settings.inputsDisabled) {
                        event.preventDefault();
                        settings.addDisabledMcpjsonServer(settings.newDisabledMcpjsonServer);
                      }
                    }}
                    disabled={settings.inputsDisabled}
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => settings.addDisabledMcpjsonServer(settings.newDisabledMcpjsonServer)}
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.disabledMcpjsonServers.length > 0 ? (
                  <div className="space-y-2">
                    {settings.disabledMcpjsonServers.map((server) => (
                      <div
                        key={server}
                        className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20"
                      >
                        <code className="font-mono text-sm text-red-700 dark:text-red-200">{server}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeDisabledMcpjsonServer(server)}
                          className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.mcpjson.disabled.empty')}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-6 space-y-6">
            <div className="flex items-center gap-2">
              <ServerCog className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-foreground">
                {t('workspace.claudeCode.permissions.mcp.policies.title')}
              </h3>
            </div>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <ListChecks className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-200">
                    {t('workspace.claudeCode.permissions.mcp.policies.allowed.title')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('workspace.claudeCode.permissions.mcp.policies.allowed.placeholder')}
                    value={settings.newAllowedMcpServer}
                    onChange={(event) => settings.setNewAllowedMcpServer(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !settings.inputsDisabled) {
                        event.preventDefault();
                        settings.addAllowedMcpServer(settings.newAllowedMcpServer);
                      }
                    }}
                    disabled={settings.inputsDisabled}
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                    onClick={() => settings.addAllowedMcpServer(settings.newAllowedMcpServer)}
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.allowedMcpServers.length > 0 ? (
                  <div className="space-y-2">
                    {settings.allowedMcpServers.map((policy) => (
                      <div
                        key={policy.serverName}
                        className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-900/20"
                      >
                        <code className="font-mono text-sm text-emerald-700 dark:text-emerald-200">{policy.serverName}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeAllowedMcpServer(policy.serverName)}
                          className="text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.policies.allowed.empty')}
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Ban className="h-5 w-5 text-red-600 dark:text-red-400" />
                  <span className="text-sm font-semibold text-red-700 dark:text-red-200">
                    {t('workspace.claudeCode.permissions.mcp.policies.denied.title')}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('workspace.claudeCode.permissions.mcp.policies.denied.placeholder')}
                    value={settings.newDeniedMcpServer}
                    onChange={(event) => settings.setNewDeniedMcpServer(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !settings.inputsDisabled) {
                        event.preventDefault();
                        settings.addDeniedMcpServer(settings.newDeniedMcpServer);
                      }
                    }}
                    disabled={settings.inputsDisabled}
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => settings.addDeniedMcpServer(settings.newDeniedMcpServer)}
                    disabled={settings.inputsDisabled}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {settings.deniedMcpServers.length > 0 ? (
                  <div className="space-y-2">
                    {settings.deniedMcpServers.map((policy) => (
                      <div
                        key={policy.serverName}
                        className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20"
                      >
                        <code className="font-mono text-sm text-red-700 dark:text-red-200">{policy.serverName}</code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => settings.removeDeniedMcpServer(policy.serverName)}
                          className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                          disabled={settings.inputsDisabled}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    {t('workspace.claudeCode.permissions.mcp.policies.denied.empty')}
                  </div>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('workspace.claudeCode.permissions.mcp.policies.helper')}
            </p>
          </div>
        </TabsContent>
      </Tabs>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={t('workspace.claudeCode.permissions.header.title')}
        icon={Shield}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">
                {t('workspace.claudeCode.permissions.scope.label')}
              </span>
              <Select
                value={settings.scope}
                onValueChange={(value) => settings.handleScopeChange(value as ClaudeCodeSettingsScope)}
                disabled={!settings.isRuntimeReady || settings.isLoading || settings.isSaving}
              >
                <SelectTrigger
                  className="h-7 w-32 text-xs"
                  aria-label={t('workspace.claudeCode.permissions.scope.label')}
                >
                  <SelectValue>{scopeLabels[settings.scope]}</SelectValue>
                </SelectTrigger>
                <SelectContent align="end">
                  {scopeOrder.map((option) => {
                    const Icon = scopeIconMap[option];
                    return (
                      <SelectItem key={option} value={option}>
                        <div className="flex items-center gap-2">
                          <Icon className="h-3 w-3" />
                          {scopeLabels[option]}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleRefresh}
              disabled={settings.refreshDisabled}
            >
              {settings.isLoading ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              )}
              {t('workspace.claudeCode.permissions.actions.refresh')}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={settings.handleSave}
              disabled={settings.saveDisabled}
            >
              {settings.isSaving ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5 mr-1.5" />
              )}
              {settings.isSaving
                ? t('workspace.claudeCode.permissions.actions.saving')
                : t('workspace.claudeCode.permissions.actions.save')}
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">{mainContent}</div>
      </div>
    </div>
  );
};

export default SettingsPage;
