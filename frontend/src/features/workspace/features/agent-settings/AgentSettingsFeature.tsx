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

export interface AgentSettingsFeatureProps {
  cliType: AgentToolType;
  subView: string;
  skillSelectedFile?: AgentSelectedFile | null;
  onSkillSelect?: (file: AgentSelectedFile | null) => void;
  scriptSelectedFile?: AgentSelectedFile | null;
  onScriptSelect?: (file: AgentSelectedFile | null) => void;
}


const AgentSettingsFeature: React.FC<AgentSettingsFeatureProps> = ({
  cliType,
  subView,
  skillSelectedFile,
  scriptSelectedFile,
}) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(cliType);
  const [internalSkillFile] = useState<AgentSelectedFile | null>(null);
  const [internalScriptFile] = useState<AgentSelectedFile | null>(null);
  const selectedSkillFile = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const selectedScriptFile = scriptSelectedFile !== undefined ? scriptSelectedFile : internalScriptFile;

  // Render the page for the active subview.
  switch (subView) {
    case config.agentsMd.subViewId:
      return <AgentsMdPage config={config} />;

    case 'mcp':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('workspace.agentSettings.common.loading')}</div>}>
          <MCPSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} supportsToggle={config.supportsToggle} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'hooks':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('workspace.agentSettings.common.loading')}</div>}>
          <HooksSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} hookEvents={config.hookEvents} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'slash-commands':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('workspace.agentSettings.common.loading')}</div>}>
          <SlashCommandsPage
            apiPrefix={config.apiPathPrefix}
            availableScopes={config.availableScopes.filter((s): s is 'project' | 'user' => s === 'project' || s === 'user')}
            format={config.slashCommandFormat}
            i18nNamespace={config.i18nNamespace}
          />
        </React.Suspense>
      );

    case 'skills':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('workspace.agentSettings.common.loading')}</div>}>
          <SkillsPage selectedFile={selectedSkillFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'scripts':
      if (config.capabilities.scripts?.supported === false) {
        return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
      }
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('workspace.agentSettings.common.loading')}</div>}>
          <ScriptsPage selectedFile={selectedScriptFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    default:
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
  }
};

export default AgentSettingsFeature;
