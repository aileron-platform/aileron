import React, { useContext } from 'react';
import { ClaudeDocumentPage } from '../components/ClaudeDocumentPage';
import { AgentDialog } from '@/shared/components/dialogs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';

const SubagentsPage: React.FC = () => {
  const { t } = useI18n();
  // 安全地檢查 context 是否可用
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
    <ClaudeDocumentPage
      documents={subagents.items}
      selectedId={subagents.selectedId}
      onSelect={subagents.select}
      onCreate={subagents.create}
      onUpdate={subagents.update}
      onDelete={subagents.remove}
      isLoading={subagents.loading}
      error={subagents.error}
      onRefresh={subagents.refresh}
      dialogComponent={AgentDialog}
      config={{
        metaKey: 'subagents',
        createButtonLabel: t('workspace.claudeCode.subagents.actions.create'),
        emptyStateTitle: t('workspace.claudeCode.subagents.empty.title'),
        emptyStateDescription: t('workspace.claudeCode.subagents.empty.description'),
        dialogTitle: t('workspace.claudeCode.subagents.pageTitle'),
      }}
    />
  );
};

export default SubagentsPage;
