import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbench } from './FileViewerWorkbench';
import type { FileViewerWorkbenchAdapter, FileViewerWorkbenchTab } from './types';

const tMock = vi.hoisted(() => (key: string, values?: Record<string, unknown>) => (
  values?.count !== undefined ? `${key}:${values.count}` : key
));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
    state: {
      currentLanguage: 'en',
    },
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
  SharedMarkdownViewer: ({
    content,
    onOpenPath,
  }: {
    content: string;
    onOpenPath?: (path: string) => void;
  }) => (
    <div>
      markdown:{content}
      <button type="button" onClick={() => onOpenPath?.('/docs/linked.md')}>open-linked-markdown</button>
    </div>
  ),
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

  it('can hide tab and status chrome for embedded single-file previews', () => {
    renderWorkbench({ hideChrome: true });

    expect(screen.queryByText('a.md')).not.toBeInTheDocument();
    expect(screen.queryByText('shared.fileViewer.status.lineCount:1')).not.toBeInTheDocument();
    expect(screen.getByText('markdown:# A')).toBeInTheDocument();
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

  it('passes workspace Markdown link opens to the file workbench owner', () => {
    const onOpenPath = vi.fn();
    renderWorkbench({ onOpenPath });

    fireEvent.click(screen.getByRole('button', { name: 'open-linked-markdown' }));

    expect(onOpenPath).toHaveBeenCalledWith('/docs/linked.md');
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

  it('shows save and expand icon actions before the action menu', async () => {
    const onExpandedChange = vi.fn();
    const { adapter, onTabsChange } = renderWorkbench({
      activeTabId: '/docs/b.ts',
      isExpanded: false,
      onExpandedChange,
    });

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.save'));

    await waitFor(() => {
      expect(adapter.saveFile).toHaveBeenCalledWith('/docs/b.ts', 'const b = 2;');
    });
    expect(onTabsChange).toHaveBeenCalledWith([
      tabs[0],
      { ...tabs[1], originalContent: 'const b = 2;', isModified: false },
      tabs[2],
    ]);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.expand'));

    expect(onExpandedChange).toHaveBeenCalledWith(true);
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

  it('shows prominent tab scroll controls when opened files overflow the tab strip', async () => {
    const scrollBy = vi.fn();
    const scrollWidthDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollWidth');
    const clientWidthDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth');
    const scrollLeftDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollLeft');
    const scrollByDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollBy');

    Object.defineProperty(HTMLElement.prototype, 'scrollWidth', {
      configurable: true,
      get: () => 360,
    });
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      get: () => 120,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollLeft', {
      configurable: true,
      get: () => 0,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollBy', {
      configurable: true,
      value: scrollBy,
    });

    try {
      renderWorkbench();

      const scrollRight = await screen.findByLabelText('shared.fileViewer.tabs.scrollRight');
      expect(scrollRight).toHaveClass('right-0', 'w-7', 'bg-card/95', 'text-foreground');

      fireEvent.click(scrollRight);

      expect(scrollBy).toHaveBeenCalledWith({
        left: 200,
        behavior: 'smooth',
      });
    } finally {
      if (scrollWidthDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'scrollWidth', scrollWidthDescriptor);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).scrollWidth;
      }
      if (clientWidthDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientWidthDescriptor);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).clientWidth;
      }
      if (scrollLeftDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'scrollLeft', scrollLeftDescriptor);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).scrollLeft;
      }
      if (scrollByDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'scrollBy', scrollByDescriptor);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).scrollBy;
      }
    }
  });

  it('does not rerun tab scroll measurement when parent recreates the same tabs', () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    const Harness: React.FC = () => {
      const [renderCount, setRenderCount] = React.useState(0);
      const adapter: FileViewerWorkbenchAdapter = React.useMemo(() => ({
        readFile: vi.fn(),
        saveFile: vi.fn(),
      }), []);
      const unstableTabs = tabs.map((tab) => ({ ...tab }));

      return (
        <div>
          <button type="button" onClick={() => setRenderCount((current) => current + 1)}>
            rerender:{renderCount}
          </button>
          <FileViewerWorkbench
            tabs={unstableTabs}
            activeTabId="/docs/a.md"
            adapter={adapter}
            onTabsChange={vi.fn()}
            onActiveTabChange={vi.fn()}
          />
        </div>
      );
    };

    try {
      render(<Harness />);

      expect(addEventListenerSpy.mock.calls.filter(([eventName]) => eventName === 'resize')).toHaveLength(1);

      fireEvent.click(screen.getByRole('button', { name: 'rerender:0' }));

      expect(addEventListenerSpy.mock.calls.filter(([eventName]) => eventName === 'resize')).toHaveLength(1);
      expect(removeEventListenerSpy.mock.calls.filter(([eventName]) => eventName === 'resize')).toHaveLength(0);
    } finally {
      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    }
  });

  it('collapses automatically when the last tab is closed while expanded', async () => {
    const Harness: React.FC = () => {
      const [tabState, setTabState] = React.useState<FileViewerWorkbenchTab[]>([tabs[0]]);
      const [activeTabId, setActiveTabId] = React.useState<string | null>('/docs/a.md');
      const [expanded, setExpanded] = React.useState(true);
      const adapter: FileViewerWorkbenchAdapter = React.useMemo(() => ({
        readFile: vi.fn(),
        saveFile: vi.fn(),
      }), []);
      return (
        <div>
          <span data-testid="expanded-state">{expanded ? 'expanded' : 'collapsed'}</span>
          <FileViewerWorkbench
            tabs={tabState}
            activeTabId={activeTabId}
            adapter={adapter}
            isExpanded={expanded}
            onExpandedChange={setExpanded}
            capabilities={{ canCloseTabs: true }}
            onTabsChange={(next) => {
              setTabState(next);
              if (next.length === 0) setActiveTabId(null);
            }}
            onActiveTabChange={setActiveTabId}
          />
        </div>
      );
    };

    render(<Harness />);

    expect(screen.getByTestId('expanded-state')).toHaveTextContent('expanded');

    fireEvent.click(screen.getByLabelText('shared.fileViewer.tabs.close'));

    await waitFor(() => {
      expect(screen.getByTestId('expanded-state')).toHaveTextContent('collapsed');
    });
  });

  it('preserves tabs, toolbar, and status while expanded', () => {
    const onExpandedChange = vi.fn();

    renderWorkbench({
      activeTabId: '/docs/b.ts',
      isExpanded: true,
      onExpandedChange,
    });

    expect(screen.getByText('a.md')).toBeInTheDocument();
    expect(screen.getByText('b.ts')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.toolbar.more')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.fileViewer.toolbar.collapse')).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.status.modified')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.collapse'));

    expect(onExpandedChange).toHaveBeenCalledWith(false);
  });
});
