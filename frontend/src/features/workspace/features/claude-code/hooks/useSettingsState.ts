/**
 * Settings State Hook
 * 管理 SettingsPage 的所有狀態
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  claudeCodeApi,
  type ClaudeCodeSettingsScope,
  type Marketplace,
} from '../services/claudeCodeApi';
import {
  normalizeRules,
  normalizeEnvEntries,
  normalizeMcpPolicies,
  arraysEqual,
  envEntriesEqual,
  mcpPoliciesEqual,
  type McpServerPolicyState,
} from '../utils';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useSettingsState');

export interface SettingsState {
  // UI 狀態
  activeTab: 'basic' | 'plugins' | 'rules' | 'mcp';
  scope: ClaudeCodeSettingsScope;
  isLoading: boolean;
  isSaving: boolean;
  loadError: string | null;

  // 基本設定
  mode: string;
  model: string;
  outputStyle: string;
  outputStyleOptions: Array<{ value: string; label: string }>;
  apiKeyHelper: string;
  cleanupPeriodDays: string;
  includeCoAuthoredBy: boolean;
  disableAllHooks: boolean;
  enableAllProjectMcpServers: boolean;
  envVars: Array<{ key: string; value: string }>;

  // 規則設定
  allowRules: string[];
  denyRules: string[];
  askRules: string[];
  additionalDirectories: string[];

  // 輸入欄位
  newAllowRule: string;
  newDenyRule: string;
  newAskRule: string;
  newAdditionalDirectory: string;

  // MCP 設定
  enabledMcpjsonServers: string[];
  disabledMcpjsonServers: string[];
  allowedMcpServers: McpServerPolicyState[];
  deniedMcpServers: McpServerPolicyState[];
  newEnabledMcpjsonServer: string;
  newDisabledMcpjsonServer: string;
  newAllowedMcpServer: string;
  newDeniedMcpServer: string;

  // 插件設定
  enabledPlugins: Record<string, boolean>;
  marketplaces: Marketplace[];
  expandedMarketplaces: Set<string>;
}

export interface UseSettingsStateReturn extends SettingsState {
  // 計算屬性
  isRuntimeReady: boolean;
  hasChanges: boolean;
  inputsDisabled: boolean;
  refreshDisabled: boolean;
  saveDisabled: boolean;

  // Tab 操作
  setActiveTab: (tab: SettingsState['activeTab']) => void;

  // Scope 操作
  handleScopeChange: (scope: ClaudeCodeSettingsScope) => void;

  // 基本設定操作
  setMode: (value: string) => void;
  setModel: (value: string) => void;
  setOutputStyle: (value: string) => void;
  setApiKeyHelper: (value: string) => void;
  setCleanupPeriodDays: (value: string) => void;
  setIncludeCoAuthoredBy: (value: boolean) => void;
  setDisableAllHooks: (value: boolean) => void;
  setEnableAllProjectMcpServers: (value: boolean) => void;

  // 環境變數操作
  addEnvVar: () => void;
  updateEnvVar: (index: number, field: 'key' | 'value', value: string) => void;
  removeEnvVar: (index: number) => void;

  // 規則操作
  addRule: (rule: string, type: 'allow' | 'deny' | 'ask') => void;
  removeRule: (rule: string, type: 'allow' | 'deny' | 'ask') => void;
  setNewAllowRule: (value: string) => void;
  setNewDenyRule: (value: string) => void;
  setNewAskRule: (value: string) => void;

  // 目錄操作
  addDirectory: (directory: string) => void;
  removeDirectory: (directory: string) => void;
  setNewAdditionalDirectory: (value: string) => void;

  // MCP 操作
  addEnabledMcpjsonServer: (server: string) => void;
  removeEnabledMcpjsonServer: (server: string) => void;
  addDisabledMcpjsonServer: (server: string) => void;
  removeDisabledMcpjsonServer: (server: string) => void;
  addAllowedMcpServer: (server: string) => void;
  removeAllowedMcpServer: (server: string) => void;
  addDeniedMcpServer: (server: string) => void;
  removeDeniedMcpServer: (server: string) => void;
  setNewEnabledMcpjsonServer: (value: string) => void;
  setNewDisabledMcpjsonServer: (value: string) => void;
  setNewAllowedMcpServer: (value: string) => void;
  setNewDeniedMcpServer: (value: string) => void;

  // 插件操作
  togglePlugin: (pluginId: string) => void;
  toggleMarketplace: (marketplaceId: string) => void;

  // 資料操作
  fetchSettings: () => Promise<void>;
  handleSave: () => Promise<void>;
}

export function useSettingsState(): UseSettingsStateReturn {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { runtimeBaseUrl, workspaceId, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;

  // UI 狀態
  const [activeTab, setActiveTab] = useState<'basic' | 'plugins' | 'rules' | 'mcp'>('basic');
  const [scope, setScope] = useState<ClaudeCodeSettingsScope>('project');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 當前值與初始值（用於變更偵測）
  const [mode, setMode] = useState('default');
  const [initialMode, setInitialMode] = useState('default');
  const [model, setModel] = useState('');
  const [initialModel, setInitialModel] = useState('');
  const [outputStyle, setOutputStyle] = useState('');
  const [initialOutputStyle, setInitialOutputStyle] = useState('');
  const [outputStyleOptions, setOutputStyleOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [apiKeyHelper, setApiKeyHelper] = useState('');
  const [initialApiKeyHelper, setInitialApiKeyHelper] = useState('');
  const [cleanupPeriodDays, setCleanupPeriodDays] = useState('');
  const [initialCleanupPeriodDays, setInitialCleanupPeriodDays] = useState('');
  const [includeCoAuthoredBy, setIncludeCoAuthoredBy] = useState(true);
  const [initialIncludeCoAuthoredBy, setInitialIncludeCoAuthoredBy] = useState(true);
  const [disableAllHooks, setDisableAllHooks] = useState(false);
  const [initialDisableAllHooks, setInitialDisableAllHooks] = useState(false);
  const [enableAllProjectMcpServers, setEnableAllProjectMcpServers] = useState(false);
  const [initialEnableAllProjectMcpServers, setInitialEnableAllProjectMcpServers] = useState(false);
  const [envVars, setEnvVars] = useState<Array<{ key: string; value: string }>>([]);
  const [initialEnvVars, setInitialEnvVars] = useState<Array<{ key: string; value: string }>>([]);

  // 規則
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);
  const [askRules, setAskRules] = useState<string[]>([]);
  const [additionalDirectories, setAdditionalDirectories] = useState<string[]>([]);
  const [initialAllowRules, setInitialAllowRules] = useState<string[]>([]);
  const [initialDenyRules, setInitialDenyRules] = useState<string[]>([]);
  const [initialAskRules, setInitialAskRules] = useState<string[]>([]);
  const [initialAdditionalDirectories, setInitialAdditionalDirectories] = useState<string[]>([]);

  // 輸入欄位
  const [newAllowRule, setNewAllowRule] = useState('');
  const [newDenyRule, setNewDenyRule] = useState('');
  const [newAskRule, setNewAskRule] = useState('');
  const [newAdditionalDirectory, setNewAdditionalDirectory] = useState('');

  // MCP
  const [enabledMcpjsonServers, setEnabledMcpjsonServers] = useState<string[]>([]);
  const [initialEnabledMcpjsonServers, setInitialEnabledMcpjsonServers] = useState<string[]>([]);
  const [disabledMcpjsonServers, setDisabledMcpjsonServers] = useState<string[]>([]);
  const [initialDisabledMcpjsonServers, setInitialDisabledMcpjsonServers] = useState<string[]>([]);
  const [allowedMcpServers, setAllowedMcpServers] = useState<McpServerPolicyState[]>([]);
  const [initialAllowedMcpServers, setInitialAllowedMcpServers] = useState<McpServerPolicyState[]>([]);
  const [deniedMcpServers, setDeniedMcpServers] = useState<McpServerPolicyState[]>([]);
  const [initialDeniedMcpServers, setInitialDeniedMcpServers] = useState<McpServerPolicyState[]>([]);
  const [newEnabledMcpjsonServer, setNewEnabledMcpjsonServer] = useState('');
  const [newDisabledMcpjsonServer, setNewDisabledMcpjsonServer] = useState('');
  const [newAllowedMcpServer, setNewAllowedMcpServer] = useState('');
  const [newDeniedMcpServer, setNewDeniedMcpServer] = useState('');

  // 插件
  const [enabledPlugins, setEnabledPlugins] = useState<Record<string, boolean>>({});
  const [initialEnabledPlugins, setInitialEnabledPlugins] = useState<Record<string, boolean>>({});
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [expandedMarketplaces, setExpandedMarketplaces] = useState<Set<string>>(new Set());

  // 計算屬性
  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);

  const pluginsChanged = useMemo(() => {
    const currentKeys = Object.keys(enabledPlugins).sort();
    const initialKeys = Object.keys(initialEnabledPlugins).sort();
    if (currentKeys.length !== initialKeys.length) return true;
    if (!arraysEqual(currentKeys, initialKeys)) return true;
    return currentKeys.some((key) => enabledPlugins[key] !== initialEnabledPlugins[key]);
  }, [enabledPlugins, initialEnabledPlugins]);

  const hasChanges = useMemo(
    () =>
      mode !== initialMode ||
      model !== initialModel ||
      outputStyle !== initialOutputStyle ||
      apiKeyHelper !== initialApiKeyHelper ||
      cleanupPeriodDays !== initialCleanupPeriodDays ||
      includeCoAuthoredBy !== initialIncludeCoAuthoredBy ||
      disableAllHooks !== initialDisableAllHooks ||
      enableAllProjectMcpServers !== initialEnableAllProjectMcpServers ||
      !arraysEqual(allowRules, initialAllowRules) ||
      !arraysEqual(denyRules, initialDenyRules) ||
      !arraysEqual(askRules, initialAskRules) ||
      !arraysEqual(additionalDirectories, initialAdditionalDirectories) ||
      !arraysEqual(enabledMcpjsonServers, initialEnabledMcpjsonServers) ||
      !arraysEqual(disabledMcpjsonServers, initialDisabledMcpjsonServers) ||
      !mcpPoliciesEqual(allowedMcpServers, initialAllowedMcpServers) ||
      !mcpPoliciesEqual(deniedMcpServers, initialDeniedMcpServers) ||
      !envEntriesEqual(envVars, initialEnvVars) ||
      pluginsChanged,
    [
      mode, initialMode, model, initialModel, outputStyle, initialOutputStyle,
      apiKeyHelper, initialApiKeyHelper, cleanupPeriodDays, initialCleanupPeriodDays,
      includeCoAuthoredBy, initialIncludeCoAuthoredBy, disableAllHooks, initialDisableAllHooks,
      enableAllProjectMcpServers, initialEnableAllProjectMcpServers,
      allowRules, initialAllowRules, denyRules, initialDenyRules, askRules, initialAskRules,
      additionalDirectories, initialAdditionalDirectories,
      enabledMcpjsonServers, initialEnabledMcpjsonServers,
      disabledMcpjsonServers, initialDisabledMcpjsonServers,
      allowedMcpServers, initialAllowedMcpServers, deniedMcpServers, initialDeniedMcpServers,
      envVars, initialEnvVars, pluginsChanged,
    ]
  );

  const inputsDisabled = !isRuntimeReady || isLoading || isSaving;
  const refreshDisabled = !isRuntimeReady || isLoading;
  const saveDisabled = !isRuntimeReady || isLoading || isSaving || !hasChanges;

  // 重置狀態
  const resetState = useCallback(() => {
    setMode('default');
    setInitialMode('default');
    setModel('');
    setInitialModel('');
    setOutputStyle('');
    setInitialOutputStyle('');
    setApiKeyHelper('');
    setInitialApiKeyHelper('');
    setCleanupPeriodDays('');
    setInitialCleanupPeriodDays('');
    setIncludeCoAuthoredBy(true);
    setInitialIncludeCoAuthoredBy(true);
    setDisableAllHooks(false);
    setInitialDisableAllHooks(false);
    setEnableAllProjectMcpServers(false);
    setInitialEnableAllProjectMcpServers(false);
    setEnvVars([]);
    setInitialEnvVars([]);
    setAllowRules([]);
    setDenyRules([]);
    setAskRules([]);
    setAdditionalDirectories([]);
    setInitialAllowRules([]);
    setInitialDenyRules([]);
    setInitialAskRules([]);
    setInitialAdditionalDirectories([]);
    setEnabledMcpjsonServers([]);
    setInitialEnabledMcpjsonServers([]);
    setDisabledMcpjsonServers([]);
    setInitialDisabledMcpjsonServers([]);
    setAllowedMcpServers([]);
    setInitialAllowedMcpServers([]);
    setDeniedMcpServers([]);
    setInitialDeniedMcpServers([]);
    setEnabledPlugins({});
    setInitialEnabledPlugins({});
    setNewAllowRule('');
    setNewDenyRule('');
    setNewAskRule('');
    setNewAdditionalDirectory('');
    setNewEnabledMcpjsonServer('');
    setNewDisabledMcpjsonServer('');
    setNewAllowedMcpServer('');
    setNewDeniedMcpServer('');
    setLoadError(null);
  }, []);

  // 載入設定
  const fetchSettings = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }

    setIsLoading(true);
    setLoadError(null);

    try {
      const [settings, outputStyles] = await Promise.all([
        claudeCodeApi.getSettings(runtimeBaseUrl, workspaceId, scope),
        claudeCodeApi.listOutputStyles(runtimeBaseUrl, workspaceId, scope),
      ]);

      const resolvedMode = settings.defaultMode ?? settings.mode ?? 'default';
      const nextModel = (settings.model ?? '').trim();
      const nextOutputStyle = (settings.outputStyle ?? '').trim();
      const nextApiKeyHelper = (settings.apiKeyHelper ?? '').trim();
      const nextCleanupPeriod =
        typeof settings.cleanupPeriodDays === 'number' && Number.isFinite(settings.cleanupPeriodDays)
          ? String(settings.cleanupPeriodDays)
          : '';
      const nextIncludeCoAuthoredBy = settings.includeCoAuthoredBy ?? true;
      const nextDisableAllHooks = settings.disableAllHooks ?? false;
      const nextEnableAllProjectMcpServers = settings.enableAllProjectMcpServers ?? false;
      const nextAllowRules = normalizeRules(settings.permissions?.allow ?? []);
      const nextDenyRules = normalizeRules(settings.permissions?.deny ?? []);
      const nextAskRules = normalizeRules(settings.permissions?.ask ?? []);
      const nextAdditionalDirectories = normalizeRules(settings.permissions?.additionalDirectories ?? []);
      const nextEnabledPlugins = settings.enabledPlugins ?? {};
      const nextEnabledMcpjsonServers = normalizeRules(settings.enabledMcpjsonServers ?? []);
      const nextDisabledMcpjsonServers = normalizeRules(settings.disabledMcpjsonServers ?? []);
      const nextAllowedMcpServers = normalizeMcpPolicies(
        (settings.allowedMcpServers ?? [])
          .map((policy) => ({ serverName: (policy?.serverName ?? '').trim() }))
          .filter((policy) => policy.serverName.length > 0)
      );
      const nextDeniedMcpServers = normalizeMcpPolicies(
        (settings.deniedMcpServers ?? [])
          .map((policy) => ({ serverName: (policy?.serverName ?? '').trim() }))
          .filter((policy) => policy.serverName.length > 0)
      );
      const envEntries = Object.entries(settings.env ?? {}).map(([key, value]) => ({
        key,
        value: String(value ?? ''),
      }));
      const sortedEnvEntries = [...envEntries].sort((a, b) => a.key.localeCompare(b.key));

      // 建立 output style 選項
      const uniqueOptions = new Map<string, { value: string; label: string }>();
      outputStyles.forEach((doc) => {
        const value = (doc.metadata?.fileName as string) ?? doc.id;
        if (!uniqueOptions.has(value)) {
          uniqueOptions.set(value, { value, label: doc.title });
        }
      });
      setOutputStyleOptions(Array.from(uniqueOptions.values()));

      // 設定當前值和初始值
      setMode(resolvedMode);
      setInitialMode(resolvedMode);
      setModel(nextModel);
      setInitialModel(nextModel);
      setOutputStyle(nextOutputStyle);
      setInitialOutputStyle(nextOutputStyle);
      setApiKeyHelper(nextApiKeyHelper);
      setInitialApiKeyHelper(nextApiKeyHelper);
      setCleanupPeriodDays(nextCleanupPeriod);
      setInitialCleanupPeriodDays(nextCleanupPeriod);
      setIncludeCoAuthoredBy(nextIncludeCoAuthoredBy);
      setInitialIncludeCoAuthoredBy(nextIncludeCoAuthoredBy);
      setDisableAllHooks(nextDisableAllHooks);
      setInitialDisableAllHooks(nextDisableAllHooks);
      setEnableAllProjectMcpServers(nextEnableAllProjectMcpServers);
      setInitialEnableAllProjectMcpServers(nextEnableAllProjectMcpServers);
      setAllowRules(nextAllowRules);
      setInitialAllowRules([...nextAllowRules]);
      setDenyRules(nextDenyRules);
      setInitialDenyRules([...nextDenyRules]);
      setAskRules(nextAskRules);
      setInitialAskRules([...nextAskRules]);
      setAdditionalDirectories(nextAdditionalDirectories);
      setInitialAdditionalDirectories([...nextAdditionalDirectories]);
      setEnabledMcpjsonServers(nextEnabledMcpjsonServers);
      setInitialEnabledMcpjsonServers([...nextEnabledMcpjsonServers]);
      setDisabledMcpjsonServers(nextDisabledMcpjsonServers);
      setInitialDisabledMcpjsonServers([...nextDisabledMcpjsonServers]);
      setAllowedMcpServers(nextAllowedMcpServers);
      setInitialAllowedMcpServers(nextAllowedMcpServers.map((p) => ({ ...p })));
      setDeniedMcpServers(nextDeniedMcpServers);
      setInitialDeniedMcpServers(nextDeniedMcpServers.map((p) => ({ ...p })));
      setEnabledPlugins(nextEnabledPlugins);
      setInitialEnabledPlugins({ ...nextEnabledPlugins });
      setEnvVars(sortedEnvEntries);
      setInitialEnvVars(sortedEnvEntries.map((e) => ({ ...e })));

      // 清除輸入欄位
      setNewAllowRule('');
      setNewDenyRule('');
      setNewAskRule('');
      setNewAdditionalDirectory('');
      setNewEnabledMcpjsonServer('');
      setNewDisabledMcpjsonServer('');
      setNewAllowedMcpServer('');
      setNewDeniedMcpServer('');
    } catch (error) {
      logger.error('Failed to load Claude Code settings', { error });
      setLoadError(error instanceof Error ? error.message : null);
    } finally {
      setIsLoading(false);
    }
  }, [runtimeBaseUrl, runtimeError, scope, workspaceId]);

  // 載入 Marketplaces
  const fetchMarketplaces = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }

    try {
      const response = await claudeCodeApi.getMarketplaces(runtimeBaseUrl, workspaceId);
      setMarketplaces(response.marketplaces);
    } catch (error) {
      logger.error('Failed to load marketplaces', { error });
    }
  }, [runtimeBaseUrl, runtimeError, workspaceId]);

  // 初始化載入
  useEffect(() => {
    if (!isRuntimeReady) {
      resetState();
      setIsLoading(false);
      return;
    }
    void fetchSettings();
    void fetchMarketplaces();
  }, [fetchSettings, fetchMarketplaces, isRuntimeReady, resetState]);

  // Scope 變更
  const handleScopeChange = useCallback(
    (nextScope: ClaudeCodeSettingsScope) => {
      if (nextScope === scope) return;
      resetState();
      setScope(nextScope);
      setIsLoading(true);
    },
    [resetState, scope]
  );

  // 環境變數操作
  const addEnvVar = useCallback(() => {
    setEnvVars((prev) => [...prev, { key: '', value: '' }]);
  }, []);

  const updateEnvVar = useCallback((index: number, field: 'key' | 'value', value: string) => {
    setEnvVars((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, [field]: value } : entry))
    );
  }, []);

  const removeEnvVar = useCallback((index: number) => {
    setEnvVars((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // 規則操作
  const addRule = useCallback(
    (rule: string, type: 'allow' | 'deny' | 'ask') => {
      const trimmedRule = rule.trim();
      if (!trimmedRule) return;

      if (type === 'allow') {
        if (allowRules.includes(trimmedRule)) {
          toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.allowExists') });
          return;
        }
        setAllowRules((prev) => normalizeRules([...prev, trimmedRule]));
        setNewAllowRule('');
      } else if (type === 'deny') {
        if (denyRules.includes(trimmedRule)) {
          toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.denyExists') });
          return;
        }
        setDenyRules((prev) => normalizeRules([...prev, trimmedRule]));
        setNewDenyRule('');
      } else {
        if (askRules.includes(trimmedRule)) {
          toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.askExists') });
          return;
        }
        setAskRules((prev) => normalizeRules([...prev, trimmedRule]));
        setNewAskRule('');
      }
    },
    [allowRules, askRules, denyRules, t, toast]
  );

  const removeRule = useCallback((rule: string, type: 'allow' | 'deny' | 'ask') => {
    if (type === 'allow') {
      setAllowRules((prev) => prev.filter((item) => item !== rule));
    } else if (type === 'deny') {
      setDenyRules((prev) => prev.filter((item) => item !== rule));
    } else {
      setAskRules((prev) => prev.filter((item) => item !== rule));
    }
  }, []);

  // 目錄操作
  const addDirectory = useCallback(
    (directory: string) => {
      const trimmed = directory.trim();
      if (!trimmed) return;
      if (additionalDirectories.includes(trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.directoryExists') });
        return;
      }
      setAdditionalDirectories((prev) => normalizeRules([...prev, trimmed]));
      setNewAdditionalDirectory('');
    },
    [additionalDirectories, t, toast]
  );

  const removeDirectory = useCallback((directory: string) => {
    setAdditionalDirectories((prev) => prev.filter((item) => item !== directory));
  }, []);

  // MCP 伺服器操作
  const addEnabledMcpjsonServer = useCallback(
    (server: string) => {
      const trimmed = server.trim();
      if (!trimmed) return;
      if (enabledMcpjsonServers.includes(trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.mcp.messages.serverExists') });
        return;
      }
      setEnabledMcpjsonServers((prev) => normalizeRules([...prev, trimmed]));
      setNewEnabledMcpjsonServer('');
    },
    [enabledMcpjsonServers, t, toast]
  );

  const removeEnabledMcpjsonServer = useCallback((server: string) => {
    setEnabledMcpjsonServers((prev) => prev.filter((item) => item !== server));
  }, []);

  const addDisabledMcpjsonServer = useCallback(
    (server: string) => {
      const trimmed = server.trim();
      if (!trimmed) return;
      if (disabledMcpjsonServers.includes(trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.mcp.messages.serverExists') });
        return;
      }
      setDisabledMcpjsonServers((prev) => normalizeRules([...prev, trimmed]));
      setNewDisabledMcpjsonServer('');
    },
    [disabledMcpjsonServers, t, toast]
  );

  const removeDisabledMcpjsonServer = useCallback((server: string) => {
    setDisabledMcpjsonServers((prev) => prev.filter((item) => item !== server));
  }, []);

  const addAllowedMcpServer = useCallback(
    (server: string) => {
      const trimmed = server.trim();
      if (!trimmed) return;
      if (allowedMcpServers.some((p) => p.serverName === trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.mcp.messages.serverExists') });
        return;
      }
      setAllowedMcpServers((prev) => normalizeMcpPolicies([...prev, { serverName: trimmed }]));
      setNewAllowedMcpServer('');
    },
    [allowedMcpServers, t, toast]
  );

  const removeAllowedMcpServer = useCallback((server: string) => {
    setAllowedMcpServers((prev) => prev.filter((p) => p.serverName !== server));
  }, []);

  const addDeniedMcpServer = useCallback(
    (server: string) => {
      const trimmed = server.trim();
      if (!trimmed) return;
      if (deniedMcpServers.some((p) => p.serverName === trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.mcp.messages.serverExists') });
        return;
      }
      setDeniedMcpServers((prev) => normalizeMcpPolicies([...prev, { serverName: trimmed }]));
      setNewDeniedMcpServer('');
    },
    [deniedMcpServers, t, toast]
  );

  const removeDeniedMcpServer = useCallback((server: string) => {
    setDeniedMcpServers((prev) => prev.filter((p) => p.serverName !== server));
  }, []);

  // 插件操作
  const togglePlugin = useCallback((pluginId: string) => {
    setEnabledPlugins((prev) => ({
      ...prev,
      [pluginId]: !prev[pluginId],
    }));
  }, []);

  const toggleMarketplace = useCallback((marketplaceId: string) => {
    setExpandedMarketplaces((prev) => {
      const next = new Set(prev);
      if (next.has(marketplaceId)) {
        next.delete(marketplaceId);
      } else {
        next.add(marketplaceId);
      }
      return next;
    });
  }, []);

  // 儲存設定
  const handleSave = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }

    setIsSaving(true);

    try {
      const envRecord: Record<string, string> = {};
      normalizeEnvEntries(envVars).forEach(({ key, value }) => {
        envRecord[key] = value;
      });

      await claudeCodeApi.updateSettings(
        runtimeBaseUrl,
        workspaceId,
        {
          defaultMode: mode,
          model: model.trim() || undefined,
          outputStyle: outputStyle.trim() || undefined,
          apiKeyHelper: apiKeyHelper.trim() || undefined,
          cleanupPeriodDays: cleanupPeriodDays ? Number(cleanupPeriodDays) : undefined,
          includeCoAuthoredBy,
          disableAllHooks,
          enableAllProjectMcpServers,
          env: envRecord,
          permissions: {
            allow: normalizeRules(allowRules),
            deny: normalizeRules(denyRules),
            ask: normalizeRules(askRules),
            additionalDirectories: normalizeRules(additionalDirectories),
          },
          enabledMcpjsonServers: normalizeRules(enabledMcpjsonServers),
          disabledMcpjsonServers: normalizeRules(disabledMcpjsonServers),
          allowedMcpServers: normalizeMcpPolicies(allowedMcpServers),
          deniedMcpServers: normalizeMcpPolicies(deniedMcpServers),
          enabledPlugins,
        },
        scope
      );

      // 更新初始值
      setInitialMode(mode);
      setInitialModel(model);
      setInitialOutputStyle(outputStyle);
      setInitialApiKeyHelper(apiKeyHelper);
      setInitialCleanupPeriodDays(cleanupPeriodDays);
      setInitialIncludeCoAuthoredBy(includeCoAuthoredBy);
      setInitialDisableAllHooks(disableAllHooks);
      setInitialEnableAllProjectMcpServers(enableAllProjectMcpServers);
      setInitialAllowRules([...allowRules]);
      setInitialDenyRules([...denyRules]);
      setInitialAskRules([...askRules]);
      setInitialAdditionalDirectories([...additionalDirectories]);
      setInitialEnabledMcpjsonServers([...enabledMcpjsonServers]);
      setInitialDisabledMcpjsonServers([...disabledMcpjsonServers]);
      setInitialAllowedMcpServers(allowedMcpServers.map((p) => ({ ...p })));
      setInitialDeniedMcpServers(deniedMcpServers.map((p) => ({ ...p })));
      setInitialEnvVars(envVars.map((e) => ({ ...e })));
      setInitialEnabledPlugins({ ...enabledPlugins });

      toast({
        title: t('workspace.claudeCode.permissions.messages.saveSuccess'),
      });
    } catch (error) {
      logger.error('Failed to save settings', { error });
      toast({
        variant: 'destructive',
        title: t('workspace.claudeCode.permissions.messages.saveError'),
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSaving(false);
    }
  }, [
    runtimeBaseUrl, workspaceId, runtimeError, scope, mode, model, outputStyle,
    apiKeyHelper, cleanupPeriodDays, includeCoAuthoredBy, disableAllHooks,
    enableAllProjectMcpServers, envVars, allowRules, denyRules, askRules,
    additionalDirectories, enabledMcpjsonServers, disabledMcpjsonServers,
    allowedMcpServers, deniedMcpServers, enabledPlugins, t, toast,
  ]);

  return {
    // 狀態
    activeTab,
    scope,
    isLoading,
    isSaving,
    loadError,
    mode,
    model,
    outputStyle,
    outputStyleOptions,
    apiKeyHelper,
    cleanupPeriodDays,
    includeCoAuthoredBy,
    disableAllHooks,
    enableAllProjectMcpServers,
    envVars,
    allowRules,
    denyRules,
    askRules,
    additionalDirectories,
    newAllowRule,
    newDenyRule,
    newAskRule,
    newAdditionalDirectory,
    enabledMcpjsonServers,
    disabledMcpjsonServers,
    allowedMcpServers,
    deniedMcpServers,
    newEnabledMcpjsonServer,
    newDisabledMcpjsonServer,
    newAllowedMcpServer,
    newDeniedMcpServer,
    enabledPlugins,
    marketplaces,
    expandedMarketplaces,

    // 計算屬性
    isRuntimeReady,
    hasChanges,
    inputsDisabled,
    refreshDisabled,
    saveDisabled,

    // 操作
    setActiveTab,
    handleScopeChange,
    setMode,
    setModel,
    setOutputStyle,
    setApiKeyHelper,
    setCleanupPeriodDays,
    setIncludeCoAuthoredBy,
    setDisableAllHooks,
    setEnableAllProjectMcpServers,
    addEnvVar,
    updateEnvVar,
    removeEnvVar,
    addRule,
    removeRule,
    setNewAllowRule,
    setNewDenyRule,
    setNewAskRule,
    addDirectory,
    removeDirectory,
    setNewAdditionalDirectory,
    addEnabledMcpjsonServer,
    removeEnabledMcpjsonServer,
    addDisabledMcpjsonServer,
    removeDisabledMcpjsonServer,
    addAllowedMcpServer,
    removeAllowedMcpServer,
    addDeniedMcpServer,
    removeDeniedMcpServer,
    setNewEnabledMcpjsonServer,
    setNewDisabledMcpjsonServer,
    setNewAllowedMcpServer,
    setNewDeniedMcpServer,
    togglePlugin,
    toggleMarketplace,
    fetchSettings,
    handleSave,
  };
}
