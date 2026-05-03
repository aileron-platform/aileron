/**
 * AgentSettingsFeature - generic AI agent settings route component.
 *
 * Renders the settings page for the selected agent type and subview.
 * Used by Gemini, OpenCode, and Codex. Claude keeps ClaudeCodeFeature.
 */

import React, { useState } from 'react';
import { getAgentToolConfig } from './utils';
import type { AgentSelectedFile, AgentToolType } from './types';
import AgentsMdPage from './pages/AgentsMdPage';
import ComingSoonPlaceholder from './components/ComingSoonPlaceholder';
import { useI18n } from '@/shared/hooks/useI18n';

// Shared page lazy imports.
const MCPSettingsPage = React.lazy(() => import('./pages/MCPSettingsPage'));
const HooksSettingsPage = React.lazy(() => import('./pages/HooksSettingsPage'));
const SlashCommandsPage = React.lazy(() => import('./pages/SlashCommandsPage'));
const SkillsPage = React.lazy(() => import('./pages/SkillsPage'));
const ScriptsPage = React.lazy(() => import('./pages/ScriptsPage'));
const CodexAgentsMdPage = React.lazy(() => import('./pages/CodexAgentsMdPage'));
const CodexRulesPage = React.lazy(() => import('./pages/CodexRulesPage'));
const CodexHooksPage = React.lazy(() => import('./pages/CodexHooksPage'));
const CodexPluginsPage = React.lazy(() => import('./pages/CodexPluginsPage'));
const CodexDocumentResourcePage = React.lazy(() => import('./pages/CodexDocumentResourcePage'));
const SubagentsPage = React.lazy(() => import('./pages/SubagentsPage'));

export interface AgentSettingsFeatureProps {
  cliType: AgentToolType;
  subView: string;
  skillSelectedFile?: AgentSelectedFile | null;
  onSkillSelect?: (file: AgentSelectedFile | null) => void;
  scriptSelectedFile?: AgentSelectedFile | null;
  onScriptSelect?: (file: AgentSelectedFile | null) => void;
  documentSelectedId?: string | null;
  onDocumentSelect?: (id: string | null) => void;
}


const AgentSettingsFeature: React.FC<AgentSettingsFeatureProps> = ({
  cliType,
  subView,
  skillSelectedFile,
  scriptSelectedFile,
  documentSelectedId,
  onDocumentSelect,
}) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(cliType);
  const [internalSkillFile] = useState<AgentSelectedFile | null>(null);
  const [internalScriptFile] = useState<AgentSelectedFile | null>(null);
  const selectedSkillFile = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const selectedScriptFile = scriptSelectedFile !== undefined ? scriptSelectedFile : internalScriptFile;
  const loadingFallback = (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {t('workspace.agentSettings.common.loading')}
    </div>
  );

  // Render the page for the active subview.
  switch (subView) {
    case config.agentsMd.subViewId:
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexAgentsMdPage />
          </React.Suspense>
        );
      }
      return <AgentsMdPage config={config} />;

    case 'mcp':
      if (config.capabilities.mcp?.supported === false || !config.capabilities.mcp) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={loadingFallback}>
          <MCPSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} supportsToggle={config.supportsToggle} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'rules':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexRulesPage
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
            />
          </React.Suspense>
        );
      }
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;

    case 'hooks':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexHooksPage />
          </React.Suspense>
        );
      }
      if (config.capabilities.hooks?.supported === false || !config.capabilities.hooks) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={loadingFallback}>
          <HooksSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} hookEvents={config.hookEvents} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'slash-commands':
      if (config.capabilities.slashCommands?.supported === false || !config.capabilities.slashCommands) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={loadingFallback}>
          <SlashCommandsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes.filter((s): s is 'project' | 'user' => s === 'project' || s === 'user')}
            format={config.slashCommandFormat}
            i18nNamespace={config.i18nNamespace}
            selectedId={documentSelectedId}
            onSelect={onDocumentSelect}
          />
        </React.Suspense>
      );

    case 'skills':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <SkillsPage selectedFile={selectedSkillFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
          </React.Suspense>
        );
      }
      if (config.capabilities.skills?.supported === false || !config.capabilities.skills) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={loadingFallback}>
          <SkillsPage selectedFile={selectedSkillFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'plugins':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexPluginsPage />
          </React.Suspense>
        );
      }
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;

    case 'subagents':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexDocumentResourcePage
              resource="subagents"
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
            />
          </React.Suspense>
        );
      }
      if (config.capabilities.agentDefinitions?.supported) {
        return (
          <React.Suspense fallback={loadingFallback}>
            <SubagentsPage
              apiPrefix={config.apiPathPrefix}
              availableScopes={config.capabilities.agentDefinitions.scopes}
              fields={config.capabilities.agentDefinitions.fields}
              i18nNamespace={config.i18nNamespace}
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
            />
          </React.Suspense>
        );
      }
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;

    case 'prompts':
      if (cliType === 'codex') {
        return (
          <React.Suspense fallback={loadingFallback}>
            <CodexDocumentResourcePage
              resource="prompts"
              selectedId={documentSelectedId}
              onSelect={onDocumentSelect}
            />
          </React.Suspense>
        );
      }
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;

    case 'scripts':
      if (config.capabilities.scripts?.supported === false) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={loadingFallback}>
          <ScriptsPage selectedFile={selectedScriptFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    default:
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
  }
};

export default AgentSettingsFeature;
