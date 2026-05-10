import React, { useContext, useMemo } from 'react';
import { AgentDocumentPage } from '../../agent-settings/components/DocumentPage';
import { AgentCommandDialog } from '../../agent-settings/components/dialogs/AgentCommandDialog';
import type { AgentDocument, AgentScope } from '../../agent-settings/types';
import type { DocumentWorkflowDialogProps } from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';

const CLAUDE_SLASH_COMMAND_SCOPES: AgentScope[] = ['project', 'user'];
const I18N_NAMESPACE = 'workspace.agentSettings.common';

const SlashCommandsPage: React.FC = () => {
  const { t } = useI18n();
  const context = useContext(ClaudeCodeContext);

  if (!context) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <p>{t('workspace.claudeCode.documents.loading')}</p>
      </div>
    );
  }

  return <SlashCommandsPageContent />;
};

const SlashCommandsPageContent: React.FC = () => {
  const { t } = useI18n();
  const { slashCommands } = useClaudeCode();

  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<DocumentWorkflowDialogProps<AgentDocument>> = (props) => (
      <AgentCommandDialog
        {...props}
        format="markdown"
        availableScopes={CLAUDE_SLASH_COMMAND_SCOPES}
        i18nNamespace={I18N_NAMESPACE}
      />
    );
    Wrapper.displayName = 'ClaudeSlashCommandDialogWrapper';
    return Wrapper;
  }, []);

  return (
    <AgentDocumentPage
      documents={slashCommands.items}
      selectedId={slashCommands.selectedId}
      onSelect={slashCommands.select}
      onCreate={slashCommands.create}
      onUpdate={slashCommands.update}
      onDelete={slashCommands.remove}
      isLoading={slashCommands.loading}
      error={slashCommands.error}
      onRefresh={slashCommands.refresh}
      dialogComponent={DialogWrapper}
      i18nNamespace={I18N_NAMESPACE}
      showSidebar={false}
      config={{
        metaKey: 'slash-commands',
        contentFormat: 'markdown',
        createButtonLabel: t(`${I18N_NAMESPACE}.slashCommands.actions.create`),
        emptyStateTitle: t(`${I18N_NAMESPACE}.slashCommands.empty.title`),
        emptyStateDescription: t(`${I18N_NAMESPACE}.slashCommands.empty.description`),
        dialogTitle: t(`${I18N_NAMESPACE}.slashCommands.pageTitle`),
      }}
    />
  );
};

export default SlashCommandsPage;
