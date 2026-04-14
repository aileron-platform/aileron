/**
 * MarkdownRenderer 組件
 * 用於渲染 Markdown 內容
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

const previewMarkdownComponents: Components = {
  p: ({ node, ...props }) => {
    // 檢查父節點是否為列表項
    const parent = node?.position ? (node as any).parent : null;
    const isInListItem = parent?.type === 'listItem';

    return (
      <p
        className={
          isInListItem
            ? 'm-0 inline break-words text-sm leading-relaxed'
            : 'mb-4 break-words text-sm leading-relaxed'
        }
        {...props}
      />
    );
  },
  ul: ({ node: _node, ...props }) => (
    <ul className="mb-4 ml-6 list-disc break-words text-sm leading-relaxed space-y-2" {...props} />
  ),
  ol: ({ node: _node, ...props }) => (
    <ol className="mb-4 ml-6 list-decimal break-words text-sm leading-relaxed space-y-2" {...props} />
  ),
  li: ({ node: _node, ...props }) => (
    <li className="break-words text-sm leading-relaxed" {...props} />
  ),
  pre: ({ node: _node, ...props }) => (
    <pre className="m-0 mb-4 max-h-[70vh] overflow-auto rounded bg-muted p-3 text-xs leading-relaxed" {...props} />
  ),
  code: ({ node, className, inline, ...props }: any) => {
    // 使用 inline prop 來判斷是否為 inline code
    // inline code: true, block code: false 或 undefined
    const isInline = inline === true;

    return isInline ? (
      <code className="rounded bg-muted px-1 py-0.5 text-xs font-mono whitespace-nowrap" {...props} />
    ) : (
      <code className={className} {...props} />
    );
  },
  h1: ({ node: _node, ...props }) => (
    <h1 className="mb-4 mt-6 text-lg font-semibold first:mt-0" {...props} />
  ),
  h2: ({ node: _node, ...props }) => (
    <h2 className="mb-3 mt-5 text-base font-semibold first:mt-0" {...props} />
  ),
  h3: ({ node: _node, ...props }) => (
    <h3 className="mb-2 mt-4 text-sm font-semibold first:mt-0" {...props} />
  ),
  hr: ({ node: _node, ...props }) => <hr className="my-6 border-border" {...props} />,
  blockquote: ({ node: _node, ...props }) => (
    <blockquote className="mb-4 border-l-2 border-border pl-3 text-sm italic" {...props} />
  ),
};

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={previewMarkdownComponents}>
      {content}
    </ReactMarkdown>
  );
};

