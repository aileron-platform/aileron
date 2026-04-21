import React from 'react';
import type { Components } from 'react-markdown';
import { cn } from '@/shared/utils/cn';

export const sharedComponents: Components = {
  table: ({ children, ...props }) => (
    <div className="my-2 overflow-x-auto rounded border border-border">
      <table className="w-full border-collapse text-sm" {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-muted" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }) => (
    <th className="border border-border/80 px-3 py-2 text-left font-semibold" {...props}>{children}</th>
  ),
  td: ({ children, ...props }) => (
    <td className="border border-border/60 px-3 py-2" {...props}>{children}</td>
  ),
  pre: ({ children, ...props }) => (
    <pre
      className="not-prose mb-4 max-h-[70vh] overflow-auto rounded bg-muted p-3 text-xs leading-relaxed text-foreground font-mono"
      {...props}
    >{children}</pre>
  ),
  code: ({ className, children, ...props }: any) => {
    const isBlock = className?.startsWith('language-');
    return isBlock ? (
      <code className={cn('not-prose text-foreground', className)} {...props}>{children}</code>
    ) : (
      <code className="not-prose rounded bg-muted px-1 py-0.5 text-xs font-mono text-foreground" {...props}>{children}</code>
    );
  },
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
