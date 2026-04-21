import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { cn } from '@/shared/utils/cn';
import { sharedComponents } from './markdownComponents';
import { preprocessLatex } from './markdownPreprocess';
import 'katex/dist/katex.min.css';

export type MarkdownVariant = 'default' | 'compact' | 'chat';

export interface MarkdownContentProps {
  content: string;
  variant?: MarkdownVariant;
  className?: string;
}

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
  const processed = React.useMemo(() => preprocessLatex(content ?? ''), [content]);

  if (!processed) return null;

  return (
    <div className={cn(variantClass[variant], className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={sharedComponents}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownContent;
