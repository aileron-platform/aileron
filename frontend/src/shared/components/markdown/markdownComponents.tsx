import React from 'react';
import type { Components } from 'react-markdown';
import { cn } from '@/shared/utils/cn';
import { MarkdownSyntaxHighlighter } from './markdownSyntaxHighlighter';

const codeBlockClassName = 'not-prose text-foreground';
const preClassName = 'not-prose mb-4 max-h-[70vh] overflow-auto rounded bg-muted p-3 text-xs leading-relaxed text-foreground font-mono';

const getLanguageFromClassName = (className?: string): string | undefined => {
  const match = /(?:^|\s)language-([^\s]+)/.exec(className ?? '');
  return match?.[1];
};

const getPreCodeChild = (children: React.ReactNode): React.ReactElement | null => {
  if (!React.isValidElement(children)) {
    return null;
  }
  return children;
};

export const sharedComponents: Components = {
  table: ({ children, ...props }) => (
    <div className="markdown-table-shell my-2 overflow-x-auto rounded border border-border">
      <table className="my-0 w-full border-separate border-spacing-0 text-sm" {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-muted" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }) => (
    <th className="border-b border-r border-border/80 px-3 py-2 text-left font-semibold last:border-r-0" {...props}>{children}</th>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="[&_tr:last-child_td]:border-b-0" {...props}>{children}</tbody>
  ),
  td: ({ children, ...props }) => (
    <td className="border-b border-r border-border/60 px-3 py-2 last:border-r-0" {...props}>{children}</td>
  ),
  pre: ({ children, ...props }) => {
    const codeChild = getPreCodeChild(children);
    if (codeChild) {
      const codeProps = codeChild.props as {
        className?: string;
        children?: React.ReactNode;
      };
      const language = getLanguageFromClassName(codeProps.className);
      const code = String(codeProps.children ?? '').replace(/\n$/, '');

      return (
        <pre className={preClassName} {...props}>
          <MarkdownSyntaxHighlighter
            code={code}
            language={language}
            className={cn(codeBlockClassName, codeProps.className)}
            customStyle={{
              margin: 0,
              padding: 0,
              background: 'transparent',
              borderRadius: 0,
              fontSize: 'inherit',
              lineHeight: 'inherit',
            }}
          />
        </pre>
      );
    }

    return (
      <pre className={preClassName} {...props}>
        {children}
      </pre>
    );
  },
  code: ({ className, children, ...props }) => (
    <code
      className={cn('not-prose rounded bg-muted px-1 py-0.5 text-xs font-mono text-foreground', className)}
      {...props}
    >
      {children}
    </code>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote className="mb-4 border-l-2 border-border pl-3 text-sm italic text-muted-foreground" {...props}>{children}</blockquote>
  ),
  hr: ({ ...props }) => <hr className="my-6 border-border" {...props} />,
  a: ({ href, children, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline decoration-primary/40 hover:decoration-primary"
      {...props}
    >
      {children}
    </a>
  ),
};
