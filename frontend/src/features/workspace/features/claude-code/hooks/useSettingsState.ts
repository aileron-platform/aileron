/**
 * Settings State Hook
 * Manages SettingsPage state.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  claudeCodeApi,
  type ClaudeCodeSettingsScope,
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

interface MarketplacePlugin {
  name: string;
  description: string;
  version: string;
}

interface Marketplace {
  name: string;
  metadata: {
    description: string;
    version: string;
  };
  plugins: MarketplacePlugin[];
}

export interface SettingsState {
  // UI state
  activeTab: 'basic' | 'plugins' | 'rules' | 'mcp';
  scope: ClaudeCodeSettingsScope;
  isLoading: boolean;
  isSaving: boolean;
  loadError: string | null;

  // Basic settings
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

  // Rule settings
  allowRules: string[];
  denyRules: string[];
  askRules: string[];
  additionalDirectories: string[];

  // Input fields
  newAllowRule: string;
  newDenyRule: string;
  newAskRule: string;
  newAdditionalDirectory: string;

  // MCP settings
  enabledMcpjsonServers: string[];
  disabledMcpjsonServers: string[];
  allowedMcpServers: McpServerPolicyState[];
  deniedMcpServers: McpServerPolicyState[];
  newEnabledMcpjsonServer: string;
  newDisabledMcpjsonServer: string;
  newAllowedMcpServer: string;
  newDeniedMcpServer: string;

  // Plugin settings
  enabledPlugins: Record<string, boolean>;
  marketplaces: Marketplace[];
  expandedMarketplaces: Set<string>;
}

export interface UseSettingsStateReturn extends SettingsState {
  // Computed properties
  isRuntimeReady: boolean;
  hasChanges: boolean;
  inputsDisabled: boolean;
  refreshDisabled: boolean;
  saveDisabled: boolean;

  // Tab operations
  setActiveTab: (tab: SettingsState['activeTab']) => void;

  // Scope operations
  handleScopeChange: (scope: ClaudeCodeSettingsScope) => void;

  // Basic setting operations
  setMode: (value: string) => void;
  setModel: (value: string) => void;
  setOutputStyle: (value: string) => void;
  setApiKeyHelper: (value: string) => void;
  setCleanupPeriodDays: (value: string) => void;
  setIncludeCoAuthoredBy: (value: boolean) => void;
  setDisableAllHooks: (value: boolean) => void;
  setEnableAllProjectMcpServers: (value: boolean) => void;

  // Environment variable operations
  addEnvVar: () => void;
  updateEnvVar: (index: number, field: 'key' | 'value', value: string) => void;
  removeEnvVar: (index: number) => void;

  // Rule operations
  addRule: (rule: string, type: 'allow' | 'deny' | 'ask') => void;
  removeRule: (rule: string, type: 'allow' | 'deny' | 'ask') => void;
  setNewAllowRule: (value: string) => void;
  setNewDenyRule: (value: string) => void;
  setNewAskRule: (value: string) => void;

  // Directory operations
  addDirectory: (directory: string) => void;
  removeDirectory: (directory: string) => void;
  setNewAdditionalDirectory: (value: string) => void;

  // MCP operations
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

  // Plugin operations
  togglePlugin: (pluginId: string) => void;
  toggleMarketplace: (marketplaceId: string) => void;

  // Data operations
  fetchSettings: () => Promise<void>;
  handleSave: () => Promise<void>;
}

export function useSettingsState(): UseSettingsStateReturn {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const { runtimeBaseUrl, workspaceId, isLoading: runtimeLoading, error: runtimeError } = workspaceRuntime;

  // UI state
  const [activeTab, setActiveTab] = useState<'basic' | 'plugins' | 'rules' | 'mcp'>('basic');
  const [scope, setScope] = useState<ClaudeCodeSettingsScope>('project');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Current and initial values for change detection.
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

  // Rules
  const [allowRules, setAllowRules] = useState<string[]>([]);
  const [denyRules, setDenyRules] = useState<string[]>([]);
  const [askRules, setAskRules] = useState<string[]>([]);
  const [additionalDirectories, setAdditionalDirectories] = useState<string[]>([]);
  const [initialAllowRules, setInitialAllowRules] = useState<string[]>([]);
  const [initialDenyRules, setInitialDenyRules] = useState<string[]>([]);
  const [initialAskRules, setInitialAskRules] = useState<string[]>([]);
  const [initialAdditionalDirectories, setInitialAdditionalDirectories] = useState<string[]>([]);

  // Input fields
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

  // Plugins
  const [enabledPlugins, setEnabledPlugins] = useState<Record<string, boolean>>({});
  const [initialEnabledPlugins, setInitialEnabledPlugins] = useState<Record<string, boolean>>({});
  const [marketplaces, setMarketplaces] = useState<Marketplace[]>([]);
  const [expandedMarketplaces, setExpandedMarketplaces] = useState<Set<string>>(new Set());

  // Computed properties
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

  // Reset state
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

  // Load settings
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

      // Build output style options.
      const uniqueOptions = new Map<string, { value: string; label: string }>();
      outputStyles.forEach((doc) => {
        const value = (doc.metadata?.fileName as string) ?? doc.id;
        if (!uniqueOptions.has(value)) {
          uniqueOptions.set(value, { value, label: doc.title });
        }
      });
      setOutputStyleOptions(Array.from(uniqueOptions.values()));

      // Set current and initial values.
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

      // Clear input fields.
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

  // Initial load
  useEffect(() => {
    if (!isRuntimeReady) {
      resetState();
      setIsLoading(false);
      return;
    }
    void fetchSettings();
  }, [fetchSettings, isRuntimeReady, resetState]);

  // Scope change
  const handleScopeChange = useCallback(
    (nextScope: ClaudeCodeSettingsScope) => {
      if (nextScope === scope) return;
      resetState();
      setScope(nextScope);
      setIsLoading(true);
    },
    [resetState, scope]
  );

  // Environment variable operations
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

  // Rule operations
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

  // Directory operations
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

  // MCP server operations.
  const addEnabledMcpjsonServer = useCallback(
    (server: string) => {
      const trimmed = server.trim();
      if (!trimmed) return;
      if (enabledMcpjsonServers.includes(trimmed)) {
        toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.mcpJsonServerExists') });
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
        toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.mcpJsonServerExists') });
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
        toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.mcpJsonServerExists') });
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
        toast({ variant: 'destructive', title: t('workspace.claudeCode.permissions.messages.mcpJsonServerExists') });
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

  // Plugin operations
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

  // Save settings
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

      // Update initial values.
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
    // State
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

    // Computed properties
    isRuntimeReady,
    hasChanges,
    inputsDisabled,
    refreshDisabled,
    saveDisabled,

    // Operations
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
