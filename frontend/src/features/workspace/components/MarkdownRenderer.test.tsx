import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { MarkdownRenderer } from './MarkdownRenderer';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

const openFileInTab = vi.fn();
const navigateMock = vi.fn();
let currentFeature: string = 'claude-code';

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('@/features/workspace/providers/WorkspaceContext', () => ({
  useWorkspaceOptional: () => ({
    openFileInTab,
    state: { currentFeature },
  }),
}));

describe('MarkdownRenderer', () => {
  beforeEach(() => {
    openFileInTab.mockReset();
    navigateMock.mockReset();
    currentFeature = 'claude-code';
  });

  it('AI CHAT 路徑使用 chat variant 的共用 markdown renderer', () => {
    const { container } = render(<MarkdownRenderer content="**chat**" />);

    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain('prose');
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('渲染表格時只產生單一外框容器', () => {
    const content = '| A | B |\n|---|---|\n| 1 | 2 |';
    const { container } = render(<MarkdownRenderer content={content} />);

    expect(container.querySelectorAll('.markdown-table-shell')).toHaveLength(1);
    expect(container.querySelectorAll('table')).toHaveLength(1);
    expect(container.querySelector('table')?.className).toContain('border-separate');
  });

  it('clicking /workspace file link opens the file and switches the workspace feature menu', () => {
    const { container } = render(
      <MarkdownRenderer content="[file](/workspace/dir/foo.md:42)" />,
    );

    const anchor = container.querySelector('a');
    expect(anchor).not.toBeNull();
    expect(anchor?.getAttribute('target')).not.toBe('_blank');

    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    fireEvent(anchor!, event);

    expect(openFileInTab).toHaveBeenCalledTimes(1);
    expect(openFileInTab).toHaveBeenCalledWith('/dir/foo.md', undefined, 'file-management');
    expect(navigateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith('/workspaces/file-management');
    expect(event.defaultPrevented).toBe(true);
  });

  it('skips navigation when already on the file-management feature', () => {
    currentFeature = 'file-management';
    const { container } = render(
      <MarkdownRenderer content="[file](/workspace/foo.md)" />,
    );

    fireEvent.click(container.querySelector('a')!);

    expect(openFileInTab).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('clicking external links does not trigger openFileInTab or navigate', () => {
    const { container } = render(
      <MarkdownRenderer content="[external](https://example.com/workspace/foo.md)" />,
    );

    const anchor = container.querySelector('a');
    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    fireEvent(anchor!, event);

    expect(openFileInTab).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it('respects modifier keys so users can still open in new tab', () => {
    const { container } = render(
      <MarkdownRenderer content="[file](/workspace/foo.md)" />,
    );

    const anchor = container.querySelector('a');
    fireEvent.click(anchor!, { metaKey: true });

    expect(openFileInTab).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
