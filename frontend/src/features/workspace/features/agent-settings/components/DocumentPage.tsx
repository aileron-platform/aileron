import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  DocumentWorkflowShell,
  PluginSourceBadge,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import type { ClaudeDocument } from '../../claude-code/types';
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';

const logger = createLogger('DocumentPage');

export interface DocumentDialogProps extends DocumentWorkflowDialogProps<ClaudeDocument> {}

export interface DocumentPageConfig {
  metaKey: 'slash-commands' | 'output-styles' | 'subagents' | 'memory';
  contentFormat?: 'markdown' | 'toml';
  createButtonLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  dialogTitle: string;
  hideScopeBadge?: boolean;
}

export interface DocumentPageProps {
  documents: ClaudeDocument[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  onUpdate: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent: React.ComponentType<DocumentDialogProps>;
  config: DocumentPageConfig;
  i18nNamespace?: string;
}

const TomlContentView: React.FC<{ content: string }> = ({ content }) => {
  const [rawExpanded, setRawExpanded] = useState(false);

  const parsed = useMemo(() => {
    try {
      const descMatch = content.match(/^description\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMatch = content.match(/^prompt\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMultiMatch = content.match(/^prompt\s*=\s*"""([\s\S]*?)"""/m);

      const description = descMatch ? descMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null;
      const prompt = promptMultiMatch
        ? promptMultiMatch[1]
        : (promptMatch ? promptMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);

      return { description, prompt };
    } catch {
      return { description: null, prompt: null };
    }
  }, [content]);

  return (
    <div className="space-y-4">
      {parsed.description ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">Description</h4>
          <p className="text-sm text-foreground">{parsed.description}</p>
        </div>
      ) : null}

      {parsed.prompt ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">Prompt</h4>
          <MarkdownContent content={parsed.prompt} />
        </div>
      ) : null}

      <div className="rounded-lg border border-border">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50"
          onClick={() => setRawExpanded(!rawExpanded)}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${rawExpanded ? 'rotate-0' : '-rotate-90'}`} />
          Raw TOML
        </button>
        {rawExpanded ? (
          <div className="border-t border-border p-4">
            <pre className="whitespace-pre-wrap text-xs font-mono text-foreground">{content}</pre>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const DocumentPage: React.FC<DocumentPageProps> = ({
  documents,
  selectedId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  isLoading = false,
  error = null,
  onRefresh,
  dialogComponent: DialogComponent,
  config,
  i18nNamespace = 'workspace.claudeCode',
}) => {
  const { t } = useI18n();

  const Icon = useMemo(() => {
    switch (config.metaKey) {
      case 'slash-commands':
        return CLAUDE_CODE_ICONS['slash-commands'];
      case 'output-styles':
        return CLAUDE_CODE_ICONS['output-styles'];
      case 'subagents':
        return CLAUDE_CODE_ICONS['subagents'];
      case 'memory':
        return CLAUDE_CODE_ICONS['memory'];
      default:
        return CLAUDE_CODE_ICONS['slash-commands'];
    }
  }, [config.metaKey]);

  const metaLabelKey = `${i18nNamespace}.documents.meta.${config.metaKey}.title`;
  const translatedMetaLabel = t(metaLabelKey);
  const title = translatedMetaLabel === metaLabelKey ? config.dialogTitle : translatedMetaLabel;

  return (
    <DocumentWorkflowShell<ClaudeDocument>
      documents={documents}
      selectedId={selectedId}
      onSelect={onSelect}
      onCreate={onCreate}
      onUpdate={onUpdate}
      onDelete={onDelete}
      isLoading={isLoading}
      error={error}
      onRefresh={onRefresh}
      dialogComponent={DialogComponent}
      title={title}
      icon={Icon}
      createButtonLabel={config.createButtonLabel}
      emptyStateTitle={config.emptyStateTitle}
      emptyStateDescription={config.emptyStateDescription}
      totalLabel={t(`${i18nNamespace}.documents.stats.total`, { count: documents.length })}
      refreshLabel={t(`${i18nNamespace}.documents.actions.refresh`)}
      editLabel={t(`${i18nNamespace}.documents.actions.edit`)}
      copyLabel={t(`${i18nNamespace}.documents.actions.copyContent`)}
      downloadLabel={t(`${i18nNamespace}.documents.actions.download`)}
      deleteLabel={t(`${i18nNamespace}.documents.actions.delete`)}
      loadingLabel={t(`${i18nNamespace}.documents.loading`)}
      canEdit={(document) => document?.scope !== 'plugin'}
      canDelete={(document) => document?.scope !== 'plugin'}
      confirmDelete={(document) => window.confirm(
        t(`${i18nNamespace}.documents.confirmDelete`, { title: document.title }),
      )}
      onCopyContent={async (document) => {
        try {
          await navigator.clipboard.writeText(document.content);
        } catch (err) {
          logger.error('無法複製到剪貼板', { error: err });
        }
      }}
      onDownload={(document) => {
        const blob = new Blob([document.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const anchor = window.document.createElement('a');
        anchor.href = url;
        anchor.download = `${document.title}.txt`;
        window.document.body.appendChild(anchor);
        anchor.click();
        window.document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
      }}
      renderMeta={(document) => (
        <div className="flex items-center gap-2">
          {!config.hideScopeBadge ? (
            <Badge variant="outline" className={`text-[11px] ${SCOPE_BADGE_CLASSES[document.scope]}`}>
              {t(`${i18nNamespace}.documents.scope.values.${document.scope}`, { defaultValue: document.scope })}
            </Badge>
          ) : null}
          {document.size ? (
            <Badge variant="outline" className="text-[11px]">
              {t(`${i18nNamespace}.documents.size.badge`, { size: document.size })}
            </Badge>
          ) : null}
          {document.scope === 'plugin' && document.pluginName ? (
            <PluginSourceBadge label={`${document.pluginName}@${document.marketplaceName}`} />
          ) : null}
        </div>
      )}
      renderContent={(document) => (
        (config.contentFormat ?? (document.metadata?.format as string)) === 'toml'
          ? <TomlContentView content={document.content} />
          : <MarkdownContent content={document.content} />
      )}
    />
  );
};

DocumentPage.displayName = 'DocumentPage';

export { DocumentPage as ClaudeDocumentPage };

export default DocumentPage;
