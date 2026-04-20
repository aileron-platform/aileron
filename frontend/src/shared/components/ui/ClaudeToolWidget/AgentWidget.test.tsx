import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentWidget } from './AgentWidget';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

const baseProps = {
  status: 'completed' as const,
  isExpanded: false,
  input: { description: '分析程式碼', subagent_type: 'general-purpose' },
};

describe('AgentWidget', () => {
  it('in_progress 狀態不渲染任何內容', () => {
    const { container } = render(
      <AgentWidget {...baseProps} status="in_progress" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('有 error 時顯示錯誤訊息', () => {
    render(<AgentWidget {...baseProps} error="Agent 執行失敗" />);
    expect(screen.getByText('Agent 執行失敗')).toBeInTheDocument();
  });

  it('顯示 subagent 類型標籤', () => {
    render(<AgentWidget {...baseProps} output="結果" />);
    expect(screen.getByText('general-purpose')).toBeInTheDocument();
  });

  it('顯示 description', () => {
    render(<AgentWidget {...baseProps} output="結果" />);
    expect(screen.getByText('分析程式碼')).toBeInTheDocument();
  });

  it('顯示 model 標籤（有 model 時）', () => {
    render(
      <AgentWidget
        {...baseProps}
        input={{ ...baseProps.input, model: 'claude-opus-4' }}
        output="結果"
      />,
    );
    expect(screen.getByText('claude-opus-4')).toBeInTheDocument();
  });

  it('透過 MarkdownContent 渲染 Markdown 輸出（prose class 存在）', () => {
    const { container } = render(
      <AgentWidget {...baseProps} output="**粗體結果**" />,
    );
    expect(container.querySelector('.prose')).not.toBeNull();
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('渲染 GFM 表格輸出', () => {
    const tableContent = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(
      <AgentWidget {...baseProps} output={tableContent} />,
    );
    expect(container.querySelector('table')).not.toBeNull();
  });

  it('內容超過 12 行時顯示展開按鈕', () => {
    const longContent = Array.from({ length: 15 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<AgentWidget {...baseProps} output={longContent} />);
    expect(screen.getByText(/查看完整內容/)).toBeInTheDocument();
  });

  it('內容不超過 12 行時不顯示展開按鈕', () => {
    const shortContent = Array.from({ length: 8 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<AgentWidget {...baseProps} output={shortContent} />);
    expect(screen.queryByText(/查看完整內容/)).toBeNull();
  });

  it('點擊展開按鈕後開啟 Dialog 顯示完整內容', async () => {
    const user = userEvent.setup();
    const longContent = Array.from({ length: 15 }, (_, i) => `Line ${i + 1}`).join('\n');
    render(<AgentWidget {...baseProps} output={longContent} />);

    await user.click(screen.getByText(/查看完整內容/));

    // Dialog 標題含 description
    const titles = screen.getAllByText('分析程式碼');
    expect(titles.length).toBeGreaterThan(1);
  });

  it('解析 usage metadata：total_tokens', () => {
    const output = JSON.stringify([
      { text: '分析結果內容' },
      { text: 'agentId: agent-123\ntotal_tokens: 5000\ntool_uses: 3\nduration_ms: 8500' },
    ]);
    render(<AgentWidget {...baseProps} output={output} />);
    expect(screen.getByText('5,000')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('8.5s')).toBeInTheDocument();
  });

  it('output 為 array 格式時正確渲染內容', () => {
    render(
      <AgentWidget
        {...baseProps}
        output={[{ text: '分析完成，程式碼品質良好' }]}
      />,
    );
    expect(screen.getByText('分析完成，程式碼品質良好')).toBeInTheDocument();
  });
});
