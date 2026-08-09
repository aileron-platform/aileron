import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useI18n } from '@/shared/hooks/useI18n';

interface TomlContentViewerProps {
  content: string;
  i18nNamespace: string;
  showRaw: boolean;
}

export const TomlContentViewer: React.FC<TomlContentViewerProps> = ({
  content,
  i18nNamespace,
  showRaw,
}) => {
  const { t } = useI18n();
  const [rawExpanded, setRawExpanded] = useState(false);
  const getTomlLabel = (key: 'description' | 'prompt' | 'developerInstructions' | 'raw') => {
    const namespaceKey = `${i18nNamespace}.documents.toml.${key}`;
    const translated = t(namespaceKey);
    return translated === namespaceKey
      ? t(`shared.documentResource.toml.${key}`)
      : translated;
  };

  const parsed = useMemo(() => {
    try {
      const descMatch = content.match(/^description\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMatch = content.match(/^prompt\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m);
      const promptMultiMatch = content.match(/^prompt\s*=\s*"""([\s\S]*?)"""/m);
      const instructionsMatch = content.match(
        /^developer_instructions\s*=\s*"([^"]*(?:\\.[^"]*)*)"/m,
      );
      const instructionsMultiMatch = content.match(
        /^developer_instructions\s*=\s*"""([\s\S]*?)"""/m,
      );

      const description = descMatch
        ? descMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')
        : null;
      const prompt = promptMultiMatch
        ? promptMultiMatch[1]
        : (promptMatch ? promptMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"') : null);
      const developerInstructions = instructionsMultiMatch
        ? instructionsMultiMatch[1]
        : (
          instructionsMatch
            ? instructionsMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')
            : null
        );

      return { description, prompt, developerInstructions };
    } catch {
      return { description: null, prompt: null, developerInstructions: null };
    }
  }, [content]);
  const hasParsedFields = Boolean(
    parsed.description || parsed.prompt || parsed.developerInstructions,
  );
  const showRawFallback = !showRaw && !hasParsedFields;

  return (
    <div className="space-y-4">
      {parsed.description ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('description')}
          </h4>
          <p className="text-sm text-foreground">{parsed.description}</p>
        </div>
      ) : null}

      {parsed.prompt ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('prompt')}
          </h4>
          <MarkdownContent content={parsed.prompt} />
        </div>
      ) : null}

      {parsed.developerInstructions ? (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
            {getTomlLabel('developerInstructions')}
          </h4>
          <MarkdownContent content={parsed.developerInstructions} />
        </div>
      ) : null}

      {showRaw ? (
        <div className="rounded-lg border border-border">
          <button
            type="button"
            className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50"
            onClick={() => setRawExpanded(!rawExpanded)}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${rawExpanded ? 'rotate-0' : '-rotate-90'}`}
            />
            {getTomlLabel('raw')}
          </button>
          {rawExpanded ? (
            <div className="border-t border-border p-4">
              <pre className="whitespace-pre-wrap text-xs font-mono text-foreground">
                {content}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
      {showRawFallback ? (
        <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/30 p-4 text-xs font-mono text-foreground">
          {content}
        </pre>
      ) : null}
    </div>
  );
};
