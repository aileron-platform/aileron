import React, { useContext } from 'react';
import { AgentDocumentPage } from '../../agent-settings/components/DocumentPage';
import { AgentDefinitionDialog } from '../../agent-settings/components/dialogs/AgentDefinitionDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';

const SubagentsPage: React.FC = () => {
  const { t } = useI18n();
  const context = useContext(ClaudeCodeContext);

  if (!context) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <p>{t('workspace.claudeCode.documents.loading')}</p>
      </div>
    );
  }

  return <SubagentsPageContent />;
};

const SubagentsPageContent: React.FC = () => {
  const { t } = useI18n();
  const { subagents } = useClaudeCode();

  return (
    <AgentDocumentPage
      documents={subagents.items}
      selectedId={subagents.selectedId}
      onSelect={subagents.select}
      onCreate={subagents.create}
      onUpdate={subagents.update}
      onDelete={subagents.remove}
      isLoading={subagents.loading}
      error={subagents.error}
      onRefresh={subagents.refresh}
      dialogComponent={AgentDefinitionDialog}
      config={{
        metaKey: 'subagents',
        createButtonLabel: t('workspace.agentSettings.common.subagents.actions.create'),
        emptyStateTitle: t('workspace.agentSettings.common.subagents.empty.title'),
        emptyStateDescription: t('workspace.agentSettings.common.subagents.empty.description'),
        dialogTitle: t('workspace.agentSettings.common.subagents.pageTitle'),
      }}
    />
  );
};

export default SubagentsPage;
