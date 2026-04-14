import React from 'react';
import { renderMarkdown } from '@/shared/utils/renderMarkdown';
import { cn } from '@/shared/utils/cn';

/**
 * Markdown 內容變體類型
 */
export type MarkdownVariant = 'default' | 'compact' | 'detailed' | 'editor';

/**
 * MarkdownContent 組件屬性
 */
export interface MarkdownContentProps {
  /** Markdown 內容字串 */
  content: string;
  /** 樣式變體 */
  variant?: MarkdownVariant;
  /** 額外的 CSS 類名 */
  className?: string;
}

/**
 * 變體對應的 CSS 類名映射
 */
const variantClassMap: Record<MarkdownVariant, string> = {
  default: 'markdown-content',
  compact: 'markdown-content-compact',
  detailed: 'markdown-content-detailed',
  editor: 'markdown-content-editor',
};

/**
 * MarkdownContent 組件
 * 
 * 統一的 Markdown 內容渲染組件，提供一致的樣式和行為。
 * 
 * @example
 * ```tsx
 * // 基本使用
 * <MarkdownContent content={markdownString} />
 * 
 * // 使用不同變體
 * <MarkdownContent content={markdownString} variant="detailed" />
 * 
 * // 添加自定義樣式
 * <MarkdownContent content={markdownString} className="px-4" />
 * ```
 */
export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  variant = 'default',
  className,
}) => {
  // 使用 useMemo 緩存渲染結果，避免不必要的重新渲染
  const html = React.useMemo(() => {
    if (!content) return '';
    return renderMarkdown(content);
  }, [content]);

  // 如果沒有內容，返回 null
  if (!html) {
    return null;
  }

  return (
    <div
      className={cn(variantClassMap[variant], className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

/**
 * 導出變體類型，方便其他組件使用
 */
export { variantClassMap };

