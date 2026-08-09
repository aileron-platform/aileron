/**
 * AgentSettingsPage - generic AI agent settings route component.
 *
 * Renders the settings page for the selected agent type and subview.
 * Used by Claude, OpenCode, and Codex.
 */

import React, { useState } from 'react';
import { getAgentToolConfig } from './model/agentSettingsModel';
import type { AgentSelectedFile } from './model/documents';
import type { AgentSettingsToolId } from './model/capabilities';
import ComingSoonPlaceholder from './components/ComingSoonPlaceholder';
import { PAGE_REGISTRY } from './pageRegistryRuntime';
import { resolveAgentSettingsPageEntry } from './pageRegistryModel';
import { useI18n } from '@/shared/hooks/useI18n';
import { AgentSettingsAuthorizationProvider } from './AgentSettingsAuthorizationContext';

export interface AgentSettingsPageProps {
  toolId: AgentSettingsToolId;
  subView: string;
  skillSelectedFile?: AgentSelectedFile | null;
  onSkillSelect?: (file: AgentSelectedFile | null) => void;
  documentSelectedId?: string | null;
  onDocumentSelect?: (id: string | null) => void;
  onDocumentDirtyChange?: (dirty: boolean) => void;
  documentSelectionBlocked?: boolean;
  readOnly?: boolean;
}


const AgentSettingsPage: React.FC<AgentSettingsPageProps> = ({
  toolId,
  subView,
  skillSelectedFile,
  documentSelectedId,
  onDocumentSelect,
  onDocumentDirtyChange,
  documentSelectionBlocked,
  readOnly = false,
}) => {
  const { t } = useI18n();
  const config = getAgentToolConfig(toolId);
  const [internalSkillFile] = useState<AgentSelectedFile | null>(null);
  const selectedSkillFile = skillSelectedFile !== undefined ? skillSelectedFile : internalSkillFile;
  const loadingFallback = (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {t('workspace.agentSettings.common.loading')}
    </div>
  );

  const pageEntry = resolveAgentSettingsPageEntry(PAGE_REGISTRY, config, subView);
  if (!pageEntry) {
    return <ComingSoonPlaceholder feature={subView} toolId={toolId} />;
  }

  const content = pageEntry.render({
    toolId,
    config,
    subView,
    loadingFallback,
    selectedSkillFile,
    documentSelectedId: documentSelectedId ?? null,
    onDocumentSelect,
    onDocumentDirtyChange,
    documentSelectionBlocked,
  });

  return (
    <AgentSettingsAuthorizationProvider readOnly={readOnly}>
      {content}
    </AgentSettingsAuthorizationProvider>
  );
};

export default AgentSettingsPage;
