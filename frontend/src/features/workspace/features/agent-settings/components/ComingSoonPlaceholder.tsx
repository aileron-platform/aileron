/**
 * ComingSoonPlaceholder - placeholder for unsupported agent capabilities.
 */

import React from 'react';
import { Construction } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { getAgentToolConfig } from '../utils';
import type { AgentToolType } from '../types';

export interface ComingSoonPlaceholderProps {
  feature: string;
  cliType: AgentToolType;
}

const subViewLabelKeys: Record<string, string> = {
  'claude-md': 'workspace.agentSettings.common.subViews.claudeMd',
  'gemini-md': 'workspace.agentSettings.common.subViews.geminiMd',
  'agents-md': 'workspace.agentSettings.common.subViews.agentsMd',
  rules: 'workspace.agentSettings.common.subViews.rules',
  mcp: 'workspace.agentSettings.common.subViews.mcp',
  hooks: 'workspace.agentSettings.common.subViews.hooks',
  plugins: 'workspace.agentSettings.common.subViews.plugins',
  extensions: 'workspace.agentSettings.common.subViews.extensions',
  'slash-commands': 'workspace.agentSettings.common.subViews.slashCommands',
  prompts: 'workspace.agentSettings.common.subViews.prompts',
  skills: 'workspace.agentSettings.common.subViews.skills',
  scripts: 'workspace.agentSettings.common.subViews.scripts',
  subagents: 'workspace.agentSettings.common.subViews.subagents',
  memory: 'workspace.agentSettings.common.subViews.memory',
  'output-styles': 'workspace.agentSettings.common.subViews.outputStyles',
  settings: 'workspace.agentSettings.common.subViews.settings',
};

const ComingSoonPlaceholder: React.FC<ComingSoonPlaceholderProps> = ({ feature, cliType }) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(cliType);
  const toolName = t(config.navigationLabelKey);
  const featureLabel = t(subViewLabelKeys[feature] ?? 'workspace.agentSettings.common.subViews.unknown');

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={featureLabel}
        icon={Construction}
      />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <Construction className="h-12 w-12 text-muted-foreground/50" />
        <div className="space-y-2">
          <h3 className="text-lg font-medium text-foreground">
            {t('workspace.agentSettings.common.comingSoon.title')}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            {t('workspace.agentSettings.common.comingSoon.description', {
              feature: featureLabel,
              toolName,
            })}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ComingSoonPlaceholder;
