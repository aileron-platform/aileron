import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingWidget } from './ThinkingWidget';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));
vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => ({
      'workspace.chat.widgets.agentTools.emptyThinking': 'No thinking content',
    })[key] ?? key,
  }),
}));

const baseProps = { status: 'completed' as const, isExpanded: false };

describe('ThinkingWidget', () => {
  it('renders a placeholder for empty thinking content', () => {
    render(<ThinkingWidget {...baseProps} input={{ thinking: '' }} />);
    expect(screen.getByText('No thinking content')).toBeInTheDocument();
  });

  it('renders a placeholder for whitespace thinking content', () => {
    render(<ThinkingWidget {...baseProps} input={{ thinking: '   ' }} />);
    expect(screen.getByText('No thinking content')).toBeInTheDocument();
  });

  it('renders a placeholder when input is missing', () => {
    render(<ThinkingWidget {...baseProps} />);
    expect(screen.getByText('No thinking content')).toBeInTheDocument();
  });

  it('渲染思考文字內容', () => {
    render(<ThinkingWidget {...baseProps} input={{ thinking: '這是思考內容' }} />);
    expect(screen.getByText('這是思考內容')).toBeInTheDocument();
  });

  it('透過 MarkdownContent 渲染 Markdown（prose class 存在）', () => {
    const { container } = render(
      <ThinkingWidget {...baseProps} input={{ thinking: '**粗體**' }} />,
    );
    expect(container.querySelector('.prose')).not.toBeNull();
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('渲染 GFM 表格', () => {
    const tableContent = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(
      <ThinkingWidget {...baseProps} input={{ thinking: tableContent }} />,
    );
    expect(container.querySelector('table')).not.toBeNull();
  });

  it('渲染 code block', () => {
    const codeContent = '```\nconst x = 1;\n```';
    const { container } = render(
      <ThinkingWidget {...baseProps} input={{ thinking: codeContent }} />,
    );
    expect(container.querySelector('pre')).not.toBeNull();
    expect(container.querySelector('code')).not.toBeNull();
  });
});
