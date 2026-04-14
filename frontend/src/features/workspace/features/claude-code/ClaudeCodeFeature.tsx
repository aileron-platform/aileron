/**
 * Claude Code 設定功能
 *
 * 提供 Claude Code 設定的第三欄主要內容組件
 */

import React from 'react';
import { Command } from 'lucide-react';
import {
  MCPSettingsPage,
  HooksSettingsPage,
  SettingsPage,
  SlashCommandsPage,
  OutputStylesPage,
  SubagentsPage,
  SkillsPage,
  ScriptsPage,
  MemoryPage,
} from './pages';
import AgentsMdPage from '../agent-settings/pages/AgentsMdPage';
import { getAgentToolConfig } from '../agent-settings/utils';
import type { SelectedFile } from './components/ClaudeCodeFileManager';

export interface ClaudeCodeFeatureProps {
  subView: 'claude-md' | 'mcp' | 'hooks' | 'settings' | 'slash-commands' | 'output-styles' | 'subagents' | 'skills' | 'scripts' | 'memory';
  skillSelectedFile?: SelectedFile | null;
  onSkillSelect?: (file: SelectedFile | null) => void;
  scriptSelectedFile?: SelectedFile | null;
  onScriptSelect?: (file: SelectedFile | null) => void;
}

const ClaudeCodeFeature: React.FC<Partial<ClaudeCodeFeatureProps>> = ({
  subView,
  skillSelectedFile,
  onSkillSelect,
  scriptSelectedFile,
  onScriptSelect
}) => {
  // 使用外部傳入的狀態，如果沒有則使用內部狀態
  const [internalSkillFile, setInternalSkillFile] = React.useState<SelectedFile | null>(null);
  const [internalScriptFile, setInternalScriptFile] = React.useState<SelectedFile | null>(null);

  const selectedSkillFileValue = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const setSelectedSkillFile = onSkillSelect || setInternalSkillFile;

  const selectedScriptFileValue = scriptSelectedFile !== undefined ? scriptSelectedFile : internalScriptFile;
  const setSelectedScriptFile = onScriptSelect || setInternalScriptFile;

  if (!subView) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <Command className="h-6 w-6" />
        <p>請透過 WorkspaceShell 使用 Claude Code 功能。</p>
      </div>
    );
  }

  switch (subView) {
    case 'claude-md':
      return <AgentsMdPage config={getAgentToolConfig('claude')} />;
    case 'mcp':
      return <MCPSettingsPage />;
    case 'hooks':
      return <HooksSettingsPage />;
    case 'settings':
      return <SettingsPage />;
    case 'slash-commands':
      return <SlashCommandsPage />;
    case 'output-styles':
      return <OutputStylesPage />;
    case 'subagents':
      return <SubagentsPage />;
    case 'skills':
      return <SkillsPage selectedFile={selectedSkillFileValue} onSelect={setSelectedSkillFile} />;
    case 'scripts':
      return <ScriptsPage selectedFile={selectedScriptFileValue} onSelect={setSelectedScriptFile} />;
    case 'memory':
      return <MemoryPage />;
    default:
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          未支援的視圖。
        </div>
      );
  }
};

export default ClaudeCodeFeature;
