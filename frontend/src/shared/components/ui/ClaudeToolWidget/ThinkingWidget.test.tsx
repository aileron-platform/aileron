import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingWidget } from './ThinkingWidget';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

const baseProps = { status: 'completed' as const, isExpanded: false };

describe('ThinkingWidget', () => {
  it('空思考內容顯示佔位提示', () => {
    render(<ThinkingWidget {...baseProps} input={{ thinking: '' }} />);
    expect(screen.getByText('無思考內容')).toBeInTheDocument();
  });

  it('空白思考內容（純空格）顯示佔位提示', () => {
    render(<ThinkingWidget {...baseProps} input={{ thinking: '   ' }} />);
    expect(screen.getByText('無思考內容')).toBeInTheDocument();
  });

  it('未傳 input 時顯示佔位提示', () => {
    render(<ThinkingWidget {...baseProps} />);
    expect(screen.getByText('無思考內容')).toBeInTheDocument();
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
