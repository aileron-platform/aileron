import React, { useContext } from 'react';
import { ClaudeDocumentPage } from '../components/ClaudeDocumentPage';
import { OutputStyleDialog } from '@/shared/components/dialogs';
import { useI18n } from '@/shared/hooks/useI18n';
import { useClaudeCode, ClaudeCodeContext } from '../context/ClaudeCodeProvider';

const OutputStylesPage: React.FC = () => {
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

  return <OutputStylesPageContent />;
};

const OutputStylesPageContent: React.FC = () => {
  const { t } = useI18n();
  const { outputStyles } = useClaudeCode();

  return (
    <ClaudeDocumentPage
      documents={outputStyles.items}
      selectedId={outputStyles.selectedId}
      onSelect={outputStyles.select}
      onCreate={outputStyles.create}
      onUpdate={outputStyles.update}
      onDelete={outputStyles.remove}
      isLoading={outputStyles.loading}
      error={outputStyles.error}
      onRefresh={outputStyles.refresh}
      dialogComponent={OutputStyleDialog}
      config={{
        metaKey: 'output-styles',
        createButtonLabel: t('workspace.claudeCode.outputStyles.actions.create'),
        emptyStateTitle: t('workspace.claudeCode.outputStyles.empty.title'),
        emptyStateDescription: t('workspace.claudeCode.outputStyles.empty.description'),
        dialogTitle: t('workspace.claudeCode.outputStyles.pageTitle'),
      }}
    />
  );
};

export default OutputStylesPage;
