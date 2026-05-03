import React from 'react';
import type { DocumentWorkflowDialogProps } from '@/shared/components/document-workflow';
import type { AgentDocument } from '../../types';
import AgentDefinitionDialog from './AgentDefinitionDialog';

export const CodexSubagentDialog: React.FC<DocumentWorkflowDialogProps<AgentDocument>> = (props) => (
  <AgentDefinitionDialog
    {...props}
    format="toml"
    i18nNamespace="workspace.agentSettings.codex"
  />
);

export default CodexSubagentDialog;
