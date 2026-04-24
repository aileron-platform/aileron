import React, { useContext, useMemo } from 'react';
import { ClaudeDocumentPage } from '../components/ClaudeDocumentPage';
import { CommandDialog } from '@/shared/components/dialogs';
import { useI18n } from '@/shared/hooks/useI18n';
import { ClaudeCodeContext } from '../context/ClaudeCodeProvider';
import type { ClaudeDocument } from '../types';

const SlashCommandsPage: React.FC = () => {
  const { t } = useI18n();
  const context = useContext(ClaudeCodeContext);

  const DialogWrapper = useMemo(() => {
    const Wrapper: React.FC<{
      open: boolean;
      mode: 'create' | 'edit';
      initialValue?: ClaudeDocument | null;
      onClose: () => void;
      onSubmit: (document: ClaudeDocument) => Promise<void> | void;
    }> = (props) => (
      <CommandDialog
        {...props}
        availableScopes={['project', 'user']}
        format="markdown"
        i18nNamespace="workspace.claudeCode"
      />
    );
    Wrapper.displayName = 'ClaudeSlashCommandDialogWrapper';
    return Wrapper;
  }, []);

  if (!context) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <p>{t('workspace.claudeCode.documents.loading')}</p>
      </div>
    );
  }

  const { slashCommands } = context;

  return (
    <ClaudeDocumentPage
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
      config={{
        metaKey: 'slash-commands',
        contentFormat: 'markdown',
        createButtonLabel: t('workspace.claudeCode.slashCommands.actions.create'),
        emptyStateTitle: t('workspace.claudeCode.slashCommands.empty.title'),
        emptyStateDescription: t('workspace.claudeCode.slashCommands.empty.description'),
        dialogTitle: t('workspace.claudeCode.slashCommands.pageTitle'),
      }}
    />
  );
};

export { SlashCommandsPage };
export default SlashCommandsPage;
