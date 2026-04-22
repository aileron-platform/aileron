import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { sharedComponents } from '@/shared/components/markdown/markdownComponents';
import { preprocessMarkdown } from '@/shared/components/markdown/markdownPreprocess';
import { remarkLineBreakTag } from '@/shared/components/markdown/remarkLineBreakTag';
import 'katex/dist/katex.min.css';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const processed = React.useMemo(() => preprocessMarkdown(content ?? ''), [content]);

  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs prose-code:before:content-none prose-code:after:content-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkLineBreakTag]}
        rehypePlugins={[rehypeKatex]}
        components={sharedComponents}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};
