import React, { useContext } from 'react';
import { ClaudeDocumentPage } from '../components/ClaudeDocumentPage';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import MemoryDialog from '../components/MemoryDialog';

const MemoryPage: React.FC = () => {
  const { t } = useI18n();
  const context = useContext(ClaudeCodeContext);

  if (!context) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <p>{t('workspace.claudeCode.documents.loading')}</p>
      </div>
    );
  }

  return <MemoryPageContent />;
};

const MemoryPageContent: React.FC = () => {
  const { t } = useI18n();
  const { memory } = useClaudeCode();

  return (
    <ClaudeDocumentPage
      documents={memory.items}
      selectedId={memory.selectedId}
      onSelect={memory.select}
      onCreate={memory.create}
      onUpdate={memory.update}
      onDelete={memory.remove}
      isLoading={memory.loading}
      error={memory.error}
      onRefresh={memory.refresh}
      dialogComponent={MemoryDialog}
      config={{
        metaKey: 'memory',
        createButtonLabel: t('workspace.claudeCode.memory.actions.create'),
        emptyStateTitle: t('workspace.claudeCode.memory.empty.title'),
        emptyStateDescription: t('workspace.claudeCode.memory.empty.description'),
        dialogTitle: t('workspace.claudeCode.memory.pageTitle'),
        hideScopeBadge: true,
      }}
    />
  );
};

export default MemoryPage;
