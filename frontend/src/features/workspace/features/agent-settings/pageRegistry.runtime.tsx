import React from 'react';
import type {
  AgentSelectedFile,
  AgentToolCapabilities,
  AgentToolConfig,
  AgentToolType,
} from './types';

const AgentsMdPage = React.lazy(() => import('./pages/AgentsMdPage'));
const MCPSettingsPage = React.lazy(() => import('./pages/MCPSettingsPage'));
const HooksSettingsPage = React.lazy(() => import('./pages/HooksSettingsPage'));
const SlashCommandsPage = React.lazy(() => import('./pages/SlashCommandsPage'));
const SkillsPage = React.lazy(() => import('./pages/SkillsPage'));
const CodexAgentsMdPage = React.lazy(() => import('./pages/CodexAgentsMdPage'));
const CodexRulesPage = React.lazy(() => import('./pages/CodexRulesPage'));
const CodexHooksPage = React.lazy(() => import('./pages/CodexHooksPage'));
const CodexPluginsPage = React.lazy(() => import('./pages/CodexPluginsPage'));
const CodexDocumentResourcePage = React.lazy(() => import('./pages/CodexDocumentResourcePage'));
const SubagentsPage = React.lazy(() => import('./pages/SubagentsPage'));
const GeminiExtensionsPage = React.lazy(() => import('./pages/GeminiExtensionsPage'));

export type SubViewId = string;

export interface PageRenderContext {
  cliType: AgentToolType;
  config: AgentToolConfig;
  subView: string;
  loadingFallback: React.ReactNode;
  selectedSkillFile: AgentSelectedFile | null;
  documentSelectedId: string | null;
  onDocumentSelect?: (id: string | null) => void;
}

export interface PageEntry {
  render: (context: PageRenderContext) => React.ReactNode;
  requiresCapability?: keyof AgentToolCapabilities;
  isSupported?: (config: AgentToolConfig) => boolean;
}

const renderWithSuspense = (
  fallback: React.ReactNode,
  page: React.ReactNode,
): React.ReactNode => <React.Suspense fallback={fallback}>{page}</React.Suspense>;

export const PAGE_REGISTRY: Record<AgentToolType, Partial<Record<SubViewId, PageEntry>>> = {
  claude: {
    'claude-md': {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(loadingFallback, <AgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    hooks: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <HooksSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            hookEvents={config.hookEvents}
            i18nNamespace={config.i18nNamespace}
            supportsActionMetadata={config.capabilities.hooks?.supportsActionMetadata}
          />,
        ),
      requiresCapability: 'hooks',
    },
    'slash-commands': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <SlashCommandsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.capabilities.slashCommands?.scopes}
            format={config.slashCommandFormat}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      requiresCapability: 'slashCommands',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    subagents: {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <SubagentsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.capabilities.agentDefinitions?.scopes}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      requiresCapability: 'agentDefinitions',
    },
  },
  gemini: {
    'gemini-md': {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(loadingFallback, <AgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    hooks: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <HooksSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            hookEvents={config.hookEvents}
            i18nNamespace={config.i18nNamespace}
            supportsActionMetadata={config.capabilities.hooks?.supportsActionMetadata}
          />,
        ),
      requiresCapability: 'hooks',
    },
    'slash-commands': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <SlashCommandsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.capabilities.slashCommands?.scopes}
            format={config.slashCommandFormat}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      requiresCapability: 'slashCommands',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    subagents: {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <SubagentsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.capabilities.agentDefinitions?.scopes}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      requiresCapability: 'agentDefinitions',
    },
    extensions: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <GeminiExtensionsPage />),
      isSupported: (config) => config.id === 'gemini',
    },
  },
  opencode: {
    'agents-md': {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(loadingFallback, <AgentsMdPage config={config} />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    'slash-commands': {
      render: ({ loadingFallback, config, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <SlashCommandsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.capabilities.slashCommands?.scopes}
            format={config.slashCommandFormat}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      requiresCapability: 'slashCommands',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
  },
  codex: {
    'agents-md': {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <CodexAgentsMdPage />),
    },
    mcp: {
      render: ({ loadingFallback, config }) =>
        renderWithSuspense(
          loadingFallback,
          <MCPSettingsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes}
            supportsToggle={config.supportsToggle}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'mcp',
    },
    hooks: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <CodexHooksPage />),
      requiresCapability: 'hooks',
    },
    skills: {
      render: ({ loadingFallback, config, selectedSkillFile }) =>
        renderWithSuspense(
          loadingFallback,
          <SkillsPage
            selectedFile={selectedSkillFile}
            apiPrefix={config.apiPathPrefix}
            i18nNamespace={config.i18nNamespace}
          />,
        ),
      requiresCapability: 'skills',
    },
    prompts: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexDocumentResourcePage
            resource="prompts"
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    subagents: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexDocumentResourcePage
            resource="subagents"
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    rules: {
      render: ({ loadingFallback, documentSelectedId, onDocumentSelect }) =>
        renderWithSuspense(
          loadingFallback,
          <CodexRulesPage
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />,
        ),
      isSupported: (config) => config.id === 'codex',
    },
    plugins: {
      render: ({ loadingFallback }) => renderWithSuspense(loadingFallback, <CodexPluginsPage />),
      isSupported: (config) => config.id === 'codex',
    },
  },
};
