import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { cn } from '@/shared/utils/cn';
import { sharedComponents } from './markdownComponents';
import { parseFrontmatterSegments, preprocessMarkdown, type FrontmatterValue } from './markdownPreprocess';
import { remarkLineBreakTag } from './remarkLineBreakTag';

export type MarkdownVariant = 'default' | 'compact' | 'chat';

export interface MarkdownContentProps {
  content: string;
  variant?: MarkdownVariant;
  className?: string;
}

const isObjectValue = (value: FrontmatterValue): value is Record<string, FrontmatterValue> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const FrontmatterValueView: React.FC<{ value: FrontmatterValue }> = ({ value }) => {
  if (Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-2">
        {value.map((item, index) => (
          <div key={index} className="rounded-md border border-border/70 bg-background px-2.5 py-1.5 text-xs text-foreground">
            <FrontmatterValueView value={item} />
          </div>
        ))}
      </div>
    );
  }

  if (isObjectValue(value)) {
    return (
      <div className="space-y-2 rounded-lg border border-border/70 bg-background/80 p-3">
        {Object.entries(value).map(([nestedKey, nestedValue]) => (
          <div key={nestedKey} className="space-y-1">
            <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">{nestedKey}</div>
            <div className="text-sm text-foreground">
              <FrontmatterValueView value={nestedValue} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span className="break-words text-sm text-foreground">{String(value)}</span>;
};

const FrontmatterCard: React.FC<{ data: Record<string, FrontmatterValue> }> = ({ data }) => (
  <section className="not-prose my-4 overflow-hidden rounded-xl border border-border bg-muted/30">
    <div className="grid divide-y divide-border/70">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="grid gap-2 px-4 py-3 md:grid-cols-[minmax(140px,180px)_1fr] md:gap-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{key}</div>
          <div className="min-w-0">
            <FrontmatterValueView value={value} />
          </div>
        </div>
      ))}
    </div>
  </section>
);

const PROSE_BASE = 'prose prose-sm max-w-none dark:prose-invert prose-code:before:content-none prose-code:after:content-none';

const variantClass: Record<MarkdownVariant, string> = {
  default: `${PROSE_BASE} prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-pre:my-2 prose-code:text-xs`,
  compact: `${PROSE_BASE} prose-p:my-1 prose-headings:my-1.5 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-1 prose-code:text-xs`,
  chat:    `${PROSE_BASE} prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs`,
};

export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  variant = 'default',
  className,
}) => {
  const segments = React.useMemo(() => parseFrontmatterSegments(content ?? ''), [content]);

  React.useEffect(() => {
    if (content) {
      void import('katex/dist/katex.min.css');
    }
  }, [content]);

  if (!content) return null;

  return (
    <div className={cn(variantClass[variant], className)}>
      {segments.map((segment, index) => {
        if (segment.type === 'frontmatter') {
          return <FrontmatterCard key={`frontmatter-${index}`} data={segment.data} />;
        }

        const processed = preprocessMarkdown(segment.content);
        if (!processed.trim()) {
          return null;
        }

        return (
          <ReactMarkdown
            key={`markdown-${index}`}
            remarkPlugins={[remarkGfm, remarkMath, remarkLineBreakTag]}
            rehypePlugins={[rehypeKatex]}
            components={sharedComponents}
          >
            {processed}
          </ReactMarkdown>
        );
      })}
    </div>
  );
};

export default MarkdownContent;
