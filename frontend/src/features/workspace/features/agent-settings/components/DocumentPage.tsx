import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  DocumentWorkflowShell,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import type { AgentDocument } from '../types';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import { AgentSettingsSourceBadge, type AgentSettingsSourceType } from './SettingsSourcePrimitives';

const logger = createLogger('DocumentPage');

export type DocumentDialogProps = DocumentWorkflowDialogProps<AgentDocument>;

export interface DocumentPageConfig {
  metaKey: 'slash-commands' | 'output-styles' | 'subagents' | 'memory' | 'prompts';
  contentFormat?: 'markdown' | 'toml';
  createButtonLabel: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
  dialogTitle: string;
  hideScopeBadge?: boolean;
}

export interface DocumentPageProps {
  documents: AgentDocument[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (document: AgentDocument) => Promise<AgentDocument>;
  onUpdate: (document: AgentDocument) => Promise<AgentDocument>;
  onDelete: (id: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => Promise<void>;
  dialogComponent: React.ComponentType<DocumentDialogProps>;
  config: DocumentPageConfig;
  i18nNamespace?: string;
}

const documentSourceType = (document: AgentDocument): AgentSettingsSourceType => {
  const source = document.metadata?.source;
  if (source === 'built_in') return 'built-in';
  if (source === 'managed') return 'managed';
  if (source === 'inline-config') return 'inline-config';
  if (source === 'project' || source === 'user' || source === 'local' || source === 'plugin') return source;
  return document.scope;
};

const TomlContentView: React.FC<{ content: string; i18nNamespace: string }> = ({ content, i18nNamespace }) => {
  const { t } = useI18n();
  const [rawExpanded, setRawExpanded] = useState(false);

  const parsed = useMemo(() => {
    try {
      const descMatch = content.match(/^description\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMatch = content.match(/^prompt\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMultiMatch = content.match(/^prompt\s*=\s*"""([\s\S]*?)"""/m);
      const instructionsMatch = content.match(/^developer_instructions\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const instructionsMultiMatch = content.match(/^developer_instructions\s*=\s*"""([\s\S]*?)"""/m);

      const description = descMatch ? descMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null;
      const prompt = promptMultiMatch
        ? promptMultiMatch[1]
        : (promptMatch ? promptMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);
      const developerInstructions = instructionsMultiMatch
        ? instructionsMultiMatch[1]
        : (instructionsMatch ? instructionsMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);

      return { description, prompt, developerInstructions };
    } catch {
      return { description: null, prompt: null, developerInstructions: null };
    }
  }, [content]);

  return (
    <div className="space-y-4">
      {parsed.description ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {t(`${i18nNamespace}.documents.toml.description`)}
          </h4>
          <p className="text-sm text-foreground">{parsed.description}</p>
        </div>
      ) : null}

      {parsed.prompt ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {t(`${i18nNamespace}.documents.toml.prompt`)}
          </h4>
          <MarkdownContent content={parsed.prompt} />
        </div>
      ) : null}

      {parsed.developerInstructions ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {t(`${i18nNamespace}.documents.toml.developerInstructions`)}
          </h4>
          <MarkdownContent content={parsed.developerInstructions} />
        </div>
      ) : null}

      <div className="rounded-lg border border-border">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50"
          onClick={() => setRawExpanded(!rawExpanded)}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${rawExpanded ? 'rotate-0' : '-rotate-90'}`} />
          {t(`${i18nNamespace}.documents.toml.raw`)}
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
  i18nNamespace = 'workspace.agentSettings.common',
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
      case 'prompts':
        return CLAUDE_CODE_ICONS['slash-commands'];
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
    <DocumentWorkflowShell<AgentDocument>
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
          logger.error('copyToClipboardFailed', { error: err });
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
            <AgentSettingsSourceBadge
              source={{
                type: documentSourceType(document),
                label: t(`${i18nNamespace}.documents.scope.values.${document.metadata?.source ?? document.scope}`, { defaultValue: String(document.metadata?.source ?? document.scope) }),
                pluginName: document.pluginName,
                marketplaceName: document.marketplaceName,
              }}
            />
          ) : null}
          {document.metadata?.effective ? (
            <Badge variant="outline" className="text-[11px]">
              {t(`${i18nNamespace}.documents.status.effective`)}
            </Badge>
          ) : null}
          {document.metadata?.overridden ? (
            <Badge variant="outline" className="text-[11px]">
              {t(`${i18nNamespace}.documents.status.overridden`)}
            </Badge>
          ) : null}
          {document.size ? (
            <Badge variant="outline" className="text-[11px]">
              {t(`${i18nNamespace}.documents.size.badge`, { size: document.size })}
            </Badge>
          ) : null}
        </div>
      )}
      renderContent={(document) => (
        (config.contentFormat ?? (document.metadata?.format as string)) === 'toml'
          ? <TomlContentView content={document.content} i18nNamespace={i18nNamespace} />
          : <MarkdownContent content={document.content} />
      )}
    />
  );
};

DocumentPage.displayName = 'DocumentPage';

export { DocumentPage as AgentDocumentPage };

export default DocumentPage;
