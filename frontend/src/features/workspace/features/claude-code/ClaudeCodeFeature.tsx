/**
 * Claude Code settings feature.
 *
 * Provides the main content component for Claude Code settings.
 */

import React from 'react';
import { Command } from 'lucide-react';
import { SettingsPage, OutputStylesPage, MemoryPage, SlashCommandsPage } from './pages';
import AgentsMdPage from '../agent-settings/pages/AgentsMdPage';
import MCPSettingsPage from '../agent-settings/pages/MCPSettingsPage';
import HooksSettingsPage from '../agent-settings/pages/HooksSettingsPage';
import SkillsPage from '../agent-settings/pages/SkillsPage';
import SubagentsPage from '../agent-settings/pages/SubagentsPage';
import { AGENT_TOOL_CONFIGS } from '../agent-settings/agentToolConfigs';
import { getAgentToolConfig } from '../agent-settings/utils';
import type { AgentSelectedFile } from '../agent-settings/types';
import { useI18n } from '@/shared/hooks/useI18n';

export interface ClaudeCodeFeatureProps {
  subView: 'claude-md' | 'mcp' | 'hooks' | 'settings' | 'slash-commands' | 'output-styles' | 'subagents' | 'skills' | 'memory';
  skillSelectedFile?: AgentSelectedFile | null;
  onSkillSelect?: (file: AgentSelectedFile | null) => void;
}

const ClaudeCodeFeature: React.FC<Partial<ClaudeCodeFeatureProps>> = ({
  subView,
  skillSelectedFile,
  onSkillSelect,
}) => {
  const { t } = useI18n();
  // Use external selection state when provided, otherwise keep local state.
  const [internalSkillFile, setInternalSkillFile] = React.useState<AgentSelectedFile | null>(null);

  const selectedSkillFileValue = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const setSelectedSkillFile = onSkillSelect || setInternalSkillFile;

  if (!subView) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <Command className="h-6 w-6" />
        <p>{t('workspace.claudeCode.shellRequired')}</p>
      </div>
    );
  }

  switch (subView) {
    case 'claude-md':
      return <AgentsMdPage config={getAgentToolConfig('claude')} />;
    case 'mcp':
      return <MCPSettingsPage />;
    case 'hooks':
      return (
        <HooksSettingsPage
          apiPrefix={AGENT_TOOL_CONFIGS.claude.apiPathPrefix}
          availableScopes={AGENT_TOOL_CONFIGS.claude.availableScopes}
          hookEvents={AGENT_TOOL_CONFIGS.claude.hookEvents}
          i18nNamespace={AGENT_TOOL_CONFIGS.claude.i18nNamespace}
          supportsActionMetadata={AGENT_TOOL_CONFIGS.claude.capabilities.hooks?.supportsActionMetadata}
        />
      );
    case 'settings':
      return <SettingsPage />;
    case 'slash-commands':
      return <SlashCommandsPage />;
    case 'output-styles':
      return <OutputStylesPage />;
    case 'subagents':
      return (
        <SubagentsPage
          apiPrefix="claude-code"
          availableScopes={AGENT_TOOL_CONFIGS.claude.capabilities.agentDefinitions?.scopes}
          i18nNamespace={AGENT_TOOL_CONFIGS.claude.i18nNamespace}
        />
      );
    case 'skills':
      return <SkillsPage selectedFile={selectedSkillFileValue} onSelect={setSelectedSkillFile} />;
    case 'memory':
      return <MemoryPage />;
    default:
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          {t('workspace.claudeCode.unsupportedView')}
        </div>
      );
  }
};

export default ClaudeCodeFeature;
