import React from 'react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return <MarkdownContent content={content} variant="chat" />;
};
