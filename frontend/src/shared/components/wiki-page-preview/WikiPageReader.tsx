import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/shared/components/ui/button';
import type { KnowledgeBaseWikiPageRef } from '@/shared/types/knowledgeBase';
import { cn } from '@/shared/utils/cn';

interface WikiPageReaderProps {
  body: string;
  related: KnowledgeBaseWikiPageRef[];
  compact?: boolean;
  onNavigate?: (path: string) => void;
}

const WIKILINK_RE = /\[\[([^\]]+)\]\]/g;

const normalizeWikilink = (value: string): string => {
  let target = value.split('|', 1)[0].split('#', 1)[0].trim().replace(/^\/+/, '');
  if (target.endsWith('.md')) target = target.slice(0, -3);
  if (target.startsWith('wiki/')) target = target.slice(5);
  return target;
};

export const WikiPageReader: React.FC<WikiPageReaderProps> = ({ body, related, compact, onNavigate }) => {
  const relatedBySlug = React.useMemo(() => new Map(related.map((item) => [item.slug ?? '', item])), [related]);

  const renderText = React.useCallback((value: string): React.ReactNode[] => {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    for (const match of value.matchAll(WIKILINK_RE)) {
      const index = match.index ?? 0;
      if (index > lastIndex) {
        parts.push(value.slice(lastIndex, index));
      }
      const raw = match[1] ?? '';
      const [target, label] = raw.split('|');
      const slug = normalizeWikilink(target ?? raw);
      const ref = relatedBySlug.get(slug);
      const text = label?.trim() || ref?.title || target?.trim() || raw;
      parts.push(
        <Button
          key={`${slug}-${index}`}
          type="button"
          variant="link"
          className="h-auto p-0 align-baseline text-current underline decoration-dotted underline-offset-4"
          disabled={!ref?.exists || !ref.path}
          onClick={() => ref?.path && onNavigate?.(ref.path)}
        >
          {text}
        </Button>,
      );
      lastIndex = index + match[0].length;
    }
    if (lastIndex < value.length) {
      parts.push(value.slice(lastIndex));
    }
    return parts;
  }, [onNavigate, relatedBySlug]);

  const renderChildren = React.useCallback((children: React.ReactNode): React.ReactNode => (
    React.Children.map(children, (child) => {
      if (typeof child === 'string') {
        return renderText(child);
      }
      return child;
    })
  ), [renderText]);

  return (
    <div className={cn('prose prose-sm max-w-none dark:prose-invert', compact ? 'prose-p:my-2' : 'p-5')}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p>{renderChildren(children)}</p>,
          li: ({ children }) => <li>{renderChildren(children)}</li>,
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
};
