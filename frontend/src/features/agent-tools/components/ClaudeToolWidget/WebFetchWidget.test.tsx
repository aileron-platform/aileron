import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WebFetchWidget } from './WebFetchWidget';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));
vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'workspace.chat.widgets.agentTools.error': 'Error',
        'workspace.chat.widgets.agentTools.emptyContent': 'No content',
        'workspace.chat.widgets.agentTools.viewFullContent': 'View full content ({{count}} lines)',
      };
      const template = translations[key] ?? key;
      return Object.entries(params ?? {}).reduce(
        (result, [paramKey, value]) => result.replace(`{{${paramKey}}}`, String(value)),
        template,
      );
    },
  }),
}));

const baseProps = {
  status: 'completed' as const,
  isExpanded: false,
  input: { url: 'https://example.com' },
};

describe('WebFetchWidget', () => {
  it('in_progress 狀態不渲染任何內容', () => {
    const { container } = render(
      <WebFetchWidget {...baseProps} status="in_progress" output="some content" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('有 error 時顯示錯誤訊息', () => {
    render(<WebFetchWidget {...baseProps} error="連線逾時" />);
    expect(screen.getByText('連線逾時')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('透過 MarkdownContent 渲染 Markdown（prose class 存在）', () => {
    const { container } = render(
      <WebFetchWidget {...baseProps} output="**粗體內容**" />,
    );
    expect(container.querySelector('.prose')).not.toBeNull();
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('渲染純文字內容', () => {
    render(<WebFetchWidget {...baseProps} output="Hello World" />);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('渲染 GFM 表格', () => {
    const tableContent = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(
      <WebFetchWidget {...baseProps} output={tableContent} />,
    );
    expect(container.querySelector('table')).not.toBeNull();
  });

  it('內容超過 15 行時顯示展開按鈕', () => {
    const longContent = Array.from({ length: 20 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<WebFetchWidget {...baseProps} output={longContent} />);
    expect(screen.getByText(/View full content/)).toBeInTheDocument();
  });

  it('內容不超過 15 行時不顯示展開按鈕', () => {
    const shortContent = Array.from({ length: 10 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<WebFetchWidget {...baseProps} output={shortContent} />);
    expect(screen.queryByText(/View full content/)).toBeNull();
  });

  it('點擊展開按鈕後開啟 Dialog 顯示完整內容', async () => {
    const user = userEvent.setup();
    const longContent = Array.from({ length: 20 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<WebFetchWidget {...baseProps} output={longContent} />);

    await user.click(screen.getByText(/View full content/));

    // Dialog 開啟後，URL 標題出現在 DialogTitle
    expect(screen.getByText('https://example.com')).toBeInTheDocument();
  });

  it('output 為 object 時序列化為 JSON 顯示', () => {
    const { container } = render(
      <WebFetchWidget {...baseProps} output={{ key: 'value' }} />,
    );
    expect(container.textContent).toContain('"key"');
    expect(container.textContent).toContain('"value"');
  });
});
