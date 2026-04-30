import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbench } from './FileViewerWorkbench';
import type { FileViewerWorkbenchAdapter, FileViewerWorkbenchTab } from './types';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values?.count !== undefined ? `${key}:${values.count}` : key
    ),
  }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      ui: {
        currentTheme: 'light',
      },
    },
  }),
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({
    value,
    onChange,
  }: {
    value: string;
    onChange?: (value: string) => void;
  }) => (
    <textarea
      aria-label="mock-code-editor"
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

vi.mock('./SharedMarkdownViewer', () => ({
  SharedMarkdownViewer: ({ content }: { content: string }) => <div>markdown:{content}</div>,
}));

vi.mock('./SharedMermaidViewer', () => ({
  SharedMermaidViewer: ({ content }: { content: string }) => <div>mermaid:{content}</div>,
}));

vi.mock('./SharedImageViewer', () => ({
  SharedImageViewer: ({ filePath }: { filePath: string }) => <div>image:{filePath}</div>,
}));

const tabs: FileViewerWorkbenchTab[] = [
  {
    id: '/docs/a.md',
    path: '/docs/a.md',
    name: 'a.md',
    content: '# A',
    originalContent: '# A',
    isModified: false,
  },
  {
    id: '/docs/b.ts',
    path: '/docs/b.ts',
    name: 'b.ts',
    content: 'const b = 2;',
    originalContent: 'const b = 1;',
    isModified: true,
  },
  {
    id: '/docs/c.mmd',
    path: '/docs/c.mmd',
    name: 'c.mmd',
    content: 'graph TD; A-->B;',
    originalContent: 'graph TD; A-->B;',
    isModified: false,
  },
];

const renderWorkbench = (
  overrides: Partial<React.ComponentProps<typeof FileViewerWorkbench>> = {},
) => {
  const adapter: FileViewerWorkbenchAdapter = {
    readFile: vi.fn(),
    saveFile: vi.fn().mockResolvedValue(undefined),
    copyPath: vi.fn().mockResolvedValue(undefined),
    revealInTree: vi.fn(),
    ...overrides.adapter,
  };
  const onTabsChange = vi.fn();
  const onActiveTabChange = vi.fn();

  render(
    <FileViewerWorkbench
      {...overrides}
      tabs={overrides.tabs ?? tabs}
      activeTabId={overrides.activeTabId ?? '/docs/a.md'}
      adapter={adapter}
      onTabsChange={onTabsChange}
      onActiveTabChange={onActiveTabChange}
    />,
  );

  return { adapter, onTabsChange, onActiveTabChange };
};

describe('FileViewerWorkbench', () => {
  it('renders workspace-style tabs and switches active tabs', () => {
    const { onActiveTabChange } = renderWorkbench();

    fireEvent.click(screen.getByText('b.ts'));

    expect(screen.getAllByText('a.md').length).toBeGreaterThan(0);
    expect(screen.getByText('b.ts')).toBeInTheDocument();
    expect(onActiveTabChange).toHaveBeenCalledWith('/docs/b.ts');
  });

  it('dispatches Markdown, Mermaid, image, Draw.io fallback, and code viewers', () => {
    renderWorkbench();
    expect(screen.getByText('markdown:# A')).toBeInTheDocument();

    cleanup();
    renderWorkbench({ activeTabId: '/docs/c.mmd' });
    expect(screen.getByText('mermaid:graph TD; A-->B;')).toBeInTheDocument();

    cleanup();
    renderWorkbench({
      tabs: [{ ...tabs[0], id: '/docs/logo.png', path: '/docs/logo.png', name: 'logo.png' }],
      activeTabId: '/docs/logo.png',
    });
    expect(screen.getByText('image:/docs/logo.png')).toBeInTheDocument();

    cleanup();
    renderWorkbench({
      tabs: [{ ...tabs[1], id: '/docs/diagram.drawio', path: '/docs/diagram.drawio', name: 'diagram.drawio' }],
      activeTabId: '/docs/diagram.drawio',
    });
    expect(screen.getByText('shared.fileViewer.drawio.fallback')).toBeInTheDocument();

    cleanup();
    renderWorkbench({ activeTabId: '/docs/b.ts' });
    expect(screen.getByLabelText('mock-code-editor')).toHaveValue('const b = 2;');
  });

  it('saves all modified tabs through the adapter', async () => {
    const { adapter, onTabsChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.saveAll'));

    await waitFor(() => {
      expect(adapter.saveFile).toHaveBeenCalledWith('/docs/b.ts', 'const b = 2;');
    });
    expect(onTabsChange).toHaveBeenCalledWith([
      tabs[0],
      { ...tabs[1], originalContent: 'const b = 2;', isModified: false },
      tabs[2],
    ]);
  });

  it('omits mutation toolbar actions in read-only mode', () => {
    renderWorkbench({ readOnly: true, activeTabId: '/docs/b.ts' });

    expect(screen.queryByLabelText('shared.fileViewer.toolbar.save')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    expect(screen.queryByText('shared.fileViewer.toolbar.save')).not.toBeInTheDocument();
    expect(screen.getByLabelText('mock-code-editor')).toHaveValue('const b = 2;');
  });

  it('opens a workspace-style tab context menu and closes saved tabs', () => {
    const { onTabsChange, onActiveTabChange } = renderWorkbench();

    fireEvent.contextMenu(screen.getAllByText('a.md')[0]);
    fireEvent.click(screen.getByText('shared.fileViewer.tabContextMenu.closeSaved'));

    expect(onTabsChange).toHaveBeenCalledWith([tabs[1]]);
    expect(onActiveTabChange).toHaveBeenCalledWith('/docs/b.ts');
  });

  it('opens the workspace-style action menu for copy path and reveal', () => {
    const { adapter } = renderWorkbench();

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.copyPath'));
    expect(adapter.copyPath).toHaveBeenCalledWith('/docs/a.md');

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.revealInTree'));
    expect(adapter.revealInTree).toHaveBeenCalledWith('/docs/a.md');
  });

  it('uses controlled focus expansion with the injected workspace focus toolbar', () => {
    const onExpandedChange = vi.fn();

    renderWorkbench({
      activeTabId: '/docs/b.ts',
      isExpanded: true,
      onExpandedChange,
      hideChromeWhenExpanded: true,
      renderFocusToolbar: ({ title, subtitle, metadata }) => (
        <header>
          <button type="button" onClick={() => onExpandedChange(false)}>
            exit-focus
          </button>
          <h1>{title}</h1>
          <span>{subtitle}</span>
          <div>{metadata}</div>
        </header>
      ),
    });

    expect(screen.getByRole('heading', { name: 'b.ts' })).toBeInTheDocument();
    expect(screen.getByText('/docs/b.ts')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.status.modified')).toBeInTheDocument();
    expect(screen.queryByLabelText('shared.fileViewer.toolbar.more')).not.toBeInTheDocument();
    expect(screen.queryByText('a.md')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('exit-focus'));

    expect(onExpandedChange).toHaveBeenCalledWith(false);
  });
});
