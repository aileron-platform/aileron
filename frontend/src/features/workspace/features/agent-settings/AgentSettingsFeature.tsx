/**
 * AgentSettingsFeature - 通用 AI Agent 設定 Feature 路由元件
 *
 * 根據 agentType 和 subView 渲染對應的設定頁面。
 * 用於 gemini / opencode / codex 工具（Claude 使用既有的 ClaudeCodeFeature）。
 */

import React, { useState } from 'react';
import { getAgentToolConfig } from './utils';
import type { AgentToolType } from './types';
import AgentsMdPage from './pages/AgentsMdPage';
import ComingSoonPlaceholder from './components/ComingSoonPlaceholder';

// 共用頁面 lazy import
const MCPSettingsPage = React.lazy(() => import('./pages/MCPSettingsPage'));
const HooksSettingsPage = React.lazy(() => import('./pages/HooksSettingsPage'));
const SlashCommandsPage = React.lazy(() => import('./pages/SlashCommandsPage'));
const SkillsPage = React.lazy(() => import('./pages/SkillsPage'));

export interface AgentSettingsFeatureProps {
  cliType: AgentToolType;
  subView: string;
}


const AgentSettingsFeature: React.FC<AgentSettingsFeatureProps> = ({ cliType, subView }) => {
  const config = getAgentToolConfig(cliType);
  const [skillSelectedFile, setSkillSelectedFile] = useState<{ path: string; scope: 'project' | 'user' | 'plugin' } | null>(null);

  // 根據 subView 渲染對應頁面
  switch (subView) {
    case config.agentsMd.subViewId:
      return <AgentsMdPage config={config} />;

    case 'mcp':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">載入中...</div>}>
          <MCPSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} supportsToggle={config.supportsToggle} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'hooks':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">載入中...</div>}>
          <HooksSettingsPage apiPrefix={config.apiPathPrefix} availableScopes={config.availableScopes} hookEvents={config.hookEvents} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    case 'slash-commands':
      return (
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">載入中...</div>}>
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
        <React.Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">載入中...</div>}>
          <SkillsPage selectedFile={skillSelectedFile} apiPrefix={config.apiPathPrefix} i18nNamespace={config.i18nNamespace} />
        </React.Suspense>
      );

    default:
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
  }
};

export default AgentSettingsFeature;
