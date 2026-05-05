/**
 * AgentSettingsFeature - generic AI agent settings route component.
 *
 * Renders the settings page for the selected agent type and subview.
 * Used by Gemini, OpenCode, and Codex. Claude keeps ClaudeCodeFeature.
 */

import React, { useState } from 'react';
import { getAgentToolConfig } from './utils';
import type { AgentSelectedFile, AgentToolType } from './types';
import ComingSoonPlaceholder from './components/ComingSoonPlaceholder';
import { PAGE_REGISTRY } from './pageRegistry';
import { useI18n } from '@/shared/hooks/useI18n';

export interface AgentSettingsFeatureProps {
  cliType: AgentToolType;
  subView: string;
  skillSelectedFile?: AgentSelectedFile | null;
  onSkillSelect?: (file: AgentSelectedFile | null) => void;
  documentSelectedId?: string | null;
  onDocumentSelect?: (id: string | null) => void;
}


const AgentSettingsFeature: React.FC<AgentSettingsFeatureProps> = ({
  cliType,
  subView,
  skillSelectedFile,
  documentSelectedId,
  onDocumentSelect,
}) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(cliType);
  const [internalSkillFile] = useState<AgentSelectedFile | null>(null);
  const selectedSkillFile = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const loadingFallback = (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {t('workspace.agentSettings.common.loading')}
    </div>
  );

  const pageEntry = PAGE_REGISTRY[cliType]?.[subView];
  if (!pageEntry) {
    return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
  }

  if (pageEntry.requiresCapability) {
    const capability = config.capabilities[pageEntry.requiresCapability];
    if (!capability || capability.supported === false) {
      return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
    }
  }

  if (pageEntry.isSupported && !pageEntry.isSupported(config)) {
    return <ComingSoonPlaceholder feature={subView} cliType={cliType} />;
  }

  return pageEntry.render({
    cliType,
    config,
    subView,
    loadingFallback,
    selectedSkillFile,
    documentSelectedId: documentSelectedId ?? null,
    onDocumentSelect,
  });
};

export default AgentSettingsFeature;
