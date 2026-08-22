import React from 'react';
import { cleanup, createEvent, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbench } from './FileViewerWorkbench';
import { FILE_WORKBENCH_TAB_DND_MIME } from './model/fileViewerWorkbenchModel';
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

vi.mock('@monaco-editor/react', () => ({
  default: ({
    value,
    onChange,
    options,
  }: {
    value: string;
    onChange?: (value: string) => void;
    options?: { readOnly?: boolean };
  }) => (
    <textarea
      aria-label="mock-code-editor"
      data-readonly={String(Boolean(options?.readOnly))}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

vi.mock('./MarkdownViewer', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');
  const { useFileViewerWorkbench } = await vi.importActual<typeof import('./FileViewerWorkbenchContext')>('./FileViewerWorkbenchContext');

  return {
    MarkdownViewer: ({
      content,
      filePath,
      fileName,
      onOpenPath,
      onSave,
      toolbarOwnerKey,
    }: {
      content: string;
      filePath?: string;
      fileName: string;
      onOpenPath?: (path: string) => void;
      onSave?: (content: string) => Promise<void> | void;
      toolbarOwnerKey?: string;
    }) => {
      const { registerFormatActions } = useFileViewerWorkbench();
      const ownerKey = toolbarOwnerKey ?? `markdown:${filePath ?? fileName}`;
      const registrationKey = `markdown:${filePath ?? fileName}:${content}`;

      ReactModule.useEffect(() => {
        registerFormatActions(
          <button type="button" aria-label="mock-markdown-edit">edit</button>,
          registrationKey,
          ownerKey,
        );
        return () => registerFormatActions(null, registrationKey, ownerKey);
      }, [ownerKey, registerFormatActions, registrationKey]);

      return (
        <div>
          markdown:{content}
          <button type="button" onClick={() => onOpenPath?.('/docs/linked.md')}>open-linked-markdown</button>
          <button type="button" onClick={() => void onSave?.('# Persisted')}>mock-markdown-save</button>
        </div>
      );
    },
  };
});

vi.mock('./MermaidViewer', () => ({
  MermaidViewer: ({ content }: { content: string }) => <div>mermaid:{content}</div>,
}));

vi.mock('./ImageViewer', () => ({
  ImageViewer: ({ filePath }: { filePath: string }) => <div>image:{filePath}</div>,
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

// jsdom reports zero-sized rects, so pointer-side detection needs a mocked
// rect on the tab element: clientX 10 lands on the left half, 90 on the right.
const TAB_RECT = {
  width: 100, height: 32, top: 0, left: 0, right: 100, bottom: 32, x: 0, y: 0,
  toJSON: () => ({}),
} as DOMRect;

const getTabWithRect = (name: string): HTMLElement => {
  const element = screen.getByText(name).closest('[draggable="true"]');
  if (!(element instanceof HTMLElement)) throw new Error(`Tab element not found for ${name}`);
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(TAB_RECT);
  return element;
};

const createForeignDataTransfer = (tabId = 'foreign-tab-id') => ({
  getData: (type: string) => (type === FILE_WORKBENCH_TAB_DND_MIME ? tabId : ''),
  setData: vi.fn(),
  types: [FILE_WORKBENCH_TAB_DND_MIME],
  effectAllowed: '',
  dropEffect: '',
});

// jsdom lacks DragEvent, so createEvent falls back to a plain Event and
// silently drops MouseEvent fields; clientX must be attached manually.
const fireDragEvent = (
  element: Element,
  type: 'dragOver' | 'drop',
  { clientX, dataTransfer }: { clientX: number; dataTransfer?: ReturnType<typeof createForeignDataTransfer> },
) => {
  const event = createEvent[type](element, { dataTransfer });
  Object.defineProperty(event, 'clientX', { value: clientX });
  fireEvent(element, event);
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

  it('dispatches Markdown, Mermaid, image, and code viewers', () => {
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
    renderWorkbench({ activeTabId: '/docs/b.ts' });
    expect(screen.getByLabelText('mock-code-editor')).toHaveValue('const b = 2;');
  });

  it('passes workspace Markdown link opens to the file workbench owner', () => {
    const onOpenPath = vi.fn();
    renderWorkbench({ onOpenPath });

    fireEvent.click(screen.getByRole('button', { name: 'open-linked-markdown' }));

    expect(onOpenPath).toHaveBeenCalledWith('/docs/linked.md');
  });

  it('clears Markdown format actions while the active Markdown tab is loading', async () => {
    const adapter: FileViewerWorkbenchAdapter = {
      readFile: vi.fn(),
      saveFile: vi.fn().mockResolvedValue(undefined),
    };
    const onTabsChange = vi.fn();
    const onActiveTabChange = vi.fn();
    const { rerender } = render(
      <FileViewerWorkbench
        tabs={[tabs[0]]}
        activeTabId="/docs/a.md"
        adapter={adapter}
        onTabsChange={onTabsChange}
        onActiveTabChange={onActiveTabChange}
      />,
    );

    expect(await screen.findByLabelText('mock-markdown-edit')).toBeInTheDocument();

    rerender(
      <FileViewerWorkbench
        tabs={[{ ...tabs[0], isLoading: true }]}
        activeTabId="/docs/a.md"
        adapter={adapter}
        onTabsChange={onTabsChange}
        onActiveTabChange={onActiveTabChange}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByLabelText('mock-markdown-edit')).not.toBeInTheDocument();
    });
  });

  it('saves all modified tabs through the adapter', async () => {
    const { adapter, onTabsChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });

    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
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

  it('persists Markdown viewer saves through the adapter', async () => {
    const { adapter, onTabsChange } = renderWorkbench();

    fireEvent.click(screen.getByRole('button', { name: 'mock-markdown-save' }));

    await waitFor(() => {
      expect(adapter.saveFile).toHaveBeenCalledWith('/docs/a.md', '# Persisted');
    });
    expect(onTabsChange).toHaveBeenCalledWith([
      { ...tabs[0], content: '# Persisted', originalContent: '# Persisted', isModified: false },
      tabs[1],
      tabs[2],
    ]);
  });

  it('shows save in the editor toolbar and expand/actions at the right of the tab bar', async () => {
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

    const tabBarActions = screen.getByTestId('file-viewer-tabbar-actions');

    expect(within(tabBarActions).getByLabelText('shared.fileViewer.toolbar.expand')).toBeInTheDocument();
    expect(within(tabBarActions).getByLabelText('shared.fileViewer.toolbar.more')).toBeInTheDocument();

    fireEvent.click(within(tabBarActions).getByLabelText('shared.fileViewer.toolbar.expand'));

    expect(onExpandedChange).toHaveBeenCalledWith(true);
  });

  it('omits mutation toolbar actions in read-only mode', () => {
    renderWorkbench({ readOnly: true, activeTabId: '/docs/b.ts' });

    expect(screen.queryByLabelText('shared.fileViewer.toolbar.save')).not.toBeInTheDocument();
    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
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

  it('shows a Split Open item in the tab context menu only when onSplitTab is provided', () => {
    renderWorkbench();

    fireEvent.contextMenu(screen.getAllByText('a.md')[0]);
    expect(screen.queryByText('shared.fileViewer.tabContextMenu.splitOpen')).not.toBeInTheDocument();
  });

  it('calls onSplitTab with the right-clicked tab id when Split Open is chosen', () => {
    const onSplitTab = vi.fn();
    renderWorkbench({ onSplitTab });

    fireEvent.contextMenu(screen.getAllByText('a.md')[0]);
    fireEvent.click(screen.getByText('shared.fileViewer.tabContextMenu.splitOpen'));

    expect(onSplitTab).toHaveBeenCalledWith('/docs/a.md');
  });

  it('disables Split Open when canSplitTab returns false for the right-clicked tab', () => {
    const onSplitTab = vi.fn();
    renderWorkbench({ onSplitTab, canSplitTab: () => false });

    fireEvent.contextMenu(screen.getAllByText('a.md')[0]);
    fireEvent.click(screen.getByText('shared.fileViewer.tabContextMenu.splitOpen'));

    expect(onSplitTab).not.toHaveBeenCalled();
  });

  it('uses the dedicated MIME type when a tab drag starts', () => {
    renderWorkbench();
    const setData = vi.fn();

    fireEvent.dragStart(screen.getByText('a.md'), {
      dataTransfer: { setData, effectAllowed: '' },
    });

    expect(setData).toHaveBeenCalledWith(FILE_WORKBENCH_TAB_DND_MIME, '/docs/a.md');
  });

  it('calls onForeignTabDrop instead of onTabsChange when the dropped tab id is not in this instance\'s own tabs', () => {
    const onForeignTabDrop = vi.fn();
    const { onTabsChange } = renderWorkbench({ onForeignTabDrop });

    const dataTransfer = createForeignDataTransfer();
    const target = getTabWithRect('a.md');
    fireDragEvent(target, 'dragOver', { clientX: 10, dataTransfer });
    fireDragEvent(target, 'drop', { clientX: 10, dataTransfer });

    expect(onForeignTabDrop).toHaveBeenCalledWith('foreign-tab-id', '/docs/a.md', 'before');
    expect(onTabsChange).not.toHaveBeenCalled();
  });

  it('shows the pointer-side indicator during a foreign drag and reports an after drop on the right half', () => {
    const onForeignTabDrop = vi.fn();
    renderWorkbench({ onForeignTabDrop });

    const dataTransfer = createForeignDataTransfer();
    const target = getTabWithRect('a.md');

    fireDragEvent(target, 'dragOver', { clientX: 90, dataTransfer });
    expect(target).toHaveAttribute('data-drop-position', 'after');

    fireDragEvent(target, 'dragOver', { clientX: 10, dataTransfer });
    expect(target).toHaveAttribute('data-drop-position', 'before');

    fireDragEvent(target, 'drop', { clientX: 90, dataTransfer });
    expect(onForeignTabDrop).toHaveBeenCalledWith('foreign-tab-id', '/docs/a.md', 'after');
    expect(target).not.toHaveAttribute('data-drop-position');
  });

  it('appends a foreign tab when it is dropped on the tab strip empty area', () => {
    const onForeignTabDrop = vi.fn();
    renderWorkbench({ onForeignTabDrop });

    const dataTransfer = createForeignDataTransfer();
    const strip = getTabWithRect('a.md').parentElement!;

    fireEvent.dragOver(strip, { dataTransfer });
    expect(screen.getByText('c.mmd').closest('[draggable="true"]')).toHaveAttribute('data-drop-position', 'after');

    fireEvent.drop(strip, { dataTransfer });
    expect(onForeignTabDrop).toHaveBeenCalledWith('foreign-tab-id', null, 'after');
  });

  it('does nothing when a foreign tab is dropped and onForeignTabDrop is not provided', () => {
    const { onTabsChange } = renderWorkbench();

    const dataTransfer = createForeignDataTransfer();
    fireEvent.dragOver(screen.getByText('a.md'), { dataTransfer });
    fireEvent.drop(screen.getByText('a.md'), { dataTransfer });

    expect(onTabsChange).not.toHaveBeenCalled();
  });

  it('calls preventDefault on dragover for a foreign drag so the browser allows the eventual drop', () => {
    // Real HTML5 drag-and-drop only fires "drop" on an element if some dragover
    // over that element called preventDefault(); dataTransfer's actual value
    // (the dragged tab id) is not readable until drop, only its `types` list
    // is readable during dragover - this test locks in that a foreign drag
    // (this instance's own draggedTabIdRef is empty) still gets preventDefault()
    // called during dragover whenever onForeignTabDrop is provided, since
    // without it a real cross-pane drag would never reach handleTabDrop at all.
    const onForeignTabDrop = vi.fn();
    renderWorkbench({ onForeignTabDrop });

    const dataTransfer = createForeignDataTransfer();
    const dragOverEvent = createEvent.dragOver(screen.getByText('a.md'), { dataTransfer });
    const preventDefaultSpy = vi.spyOn(dragOverEvent, 'preventDefault');
    fireEvent(screen.getByText('a.md'), dragOverEvent);

    expect(preventDefaultSpy).toHaveBeenCalled();
  });

  it('does not call preventDefault on dragover for a foreign drag when onForeignTabDrop is not provided', () => {
    renderWorkbench();

    const dataTransfer = createForeignDataTransfer();
    const dragOverEvent = createEvent.dragOver(screen.getByText('a.md'), { dataTransfer });
    const preventDefaultSpy = vi.spyOn(dragOverEvent, 'preventDefault');
    fireEvent(screen.getByText('a.md'), dragOverEvent);

    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  it('ignores file-tree text/plain drags without enabling a foreign tab drop', () => {
    const onForeignTabDrop = vi.fn();
    renderWorkbench({ onForeignTabDrop });

    const dataTransfer = {
      getData: (type: string) => type === 'text/plain' ? '/workspace/from-file-tree.ts' : '',
      setData: vi.fn(),
      types: ['text/plain'],
      effectAllowed: '',
      dropEffect: '',
    };
    const target = screen.getByText('a.md');
    const dragOverEvent = createEvent.dragOver(target, { dataTransfer });
    const preventDefaultSpy = vi.spyOn(dragOverEvent, 'preventDefault');

    fireEvent(target, dragOverEvent);
    fireEvent.drop(target, { dataTransfer });

    expect(preventDefaultSpy).not.toHaveBeenCalled();
    expect(onForeignTabDrop).not.toHaveBeenCalled();
  });

  it('emits reordered tabs when a tab is dropped on the left half of another tab', () => {
    const { onTabsChange, onActiveTabChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });

    const target = getTabWithRect('a.md');
    fireEvent.dragStart(screen.getByText('c.mmd'));
    fireDragEvent(target, 'dragOver', { clientX: 10 });
    fireDragEvent(target, 'drop', { clientX: 10 });

    expect(onTabsChange).toHaveBeenCalledWith([tabs[2], tabs[0], tabs[1]]);
    expect(onActiveTabChange).not.toHaveBeenCalled();
  });

  it('emits reordered tabs when a tab is dropped on the right half of another tab', () => {
    const { onTabsChange } = renderWorkbench();

    const target = getTabWithRect('c.mmd');
    fireEvent.dragStart(screen.getByText('a.md'));
    fireDragEvent(target, 'dragOver', { clientX: 90 });
    fireDragEvent(target, 'drop', { clientX: 90 });

    expect(onTabsChange).toHaveBeenCalledWith([tabs[1], tabs[2], tabs[0]]);
  });

  it('moves a tab to the end when it is dropped on the tab strip empty area', () => {
    const { onTabsChange } = renderWorkbench();

    const lastTab = screen.getByText('c.mmd').closest('[draggable="true"]');
    const strip = lastTab!.parentElement!;

    fireEvent.dragStart(screen.getByText('a.md'));
    fireEvent.dragOver(strip);

    expect(lastTab).toHaveAttribute('data-drop-position', 'after');

    fireEvent.drop(strip);

    expect(onTabsChange).toHaveBeenCalledWith([tabs[1], tabs[2], tabs[0]]);
    expect(lastTab).not.toHaveAttribute('data-drop-position');
  });

  it('shows the drop position while dragging over tabs and clears it after drop', () => {
    renderWorkbench();

    const targetBeforeTab = getTabWithRect('a.md');
    const targetAfterTab = getTabWithRect('b.ts');

    fireEvent.dragStart(screen.getByText('c.mmd'));
    fireDragEvent(targetBeforeTab, 'dragOver', { clientX: 10 });

    expect(targetBeforeTab).toHaveAttribute('data-drop-position', 'before');

    fireDragEvent(targetAfterTab, 'dragOver', { clientX: 90 });

    expect(targetBeforeTab).not.toHaveAttribute('data-drop-position');
    expect(targetAfterTab).toHaveAttribute('data-drop-position', 'after');

    fireDragEvent(targetAfterTab, 'drop', { clientX: 90 });

    expect(targetAfterTab).not.toHaveAttribute('data-drop-position');
  });

  it('flips the drop side as the pointer crosses the target tab midpoint and clears it on drag end', () => {
    renderWorkbench();

    const sourceTab = screen.getByText('a.md').closest('[draggable="true"]');
    const targetTab = getTabWithRect('c.mmd');

    fireEvent.dragStart(sourceTab!);
    fireDragEvent(targetTab, 'dragOver', { clientX: 90 });

    expect(targetTab).toHaveAttribute('data-drop-position', 'after');

    fireDragEvent(targetTab, 'dragOver', { clientX: 10 });

    expect(targetTab).toHaveAttribute('data-drop-position', 'before');

    fireEvent.dragEnd(sourceTab!);

    expect(targetTab).not.toHaveAttribute('data-drop-position');
  });

  it('clears the drop indicator when the drag leaves the tab strip', () => {
    renderWorkbench();

    const targetTab = getTabWithRect('b.ts');
    const strip = targetTab.parentElement!;

    fireEvent.dragStart(screen.getByText('a.md'));
    fireDragEvent(targetTab, 'dragOver', { clientX: 90 });

    expect(targetTab).toHaveAttribute('data-drop-position', 'after');

    fireEvent.dragLeave(strip);

    expect(targetTab).not.toHaveAttribute('data-drop-position');
  });

  it('clears drag state when the dragged tab leaves this pane before dragend can fire', () => {
    const adapter: FileViewerWorkbenchAdapter = { readFile: vi.fn() };
    const sharedProps = {
      activeTabId: '/docs/b.ts',
      adapter,
      onTabsChange: vi.fn(),
      onActiveTabChange: vi.fn(),
    };
    const { rerender } = render(<FileViewerWorkbench {...sharedProps} tabs={tabs} />);

    const targetTab = getTabWithRect('b.ts');
    fireEvent.dragStart(screen.getByText('a.md'));
    fireDragEvent(targetTab, 'dragOver', { clientX: 90 });

    expect(targetTab).toHaveAttribute('data-drop-position', 'after');

    // Simulates a successful cross-pane drop: the dragged tab is removed from
    // this pane's tabs, unmounting it before dragend fires.
    rerender(<FileViewerWorkbench {...sharedProps} tabs={[tabs[1], tabs[2]]} />);

    expect(screen.getByText('b.ts').closest('[draggable="true"]')).not.toHaveAttribute('data-drop-position');
  });

  it('keeps tab order unchanged when a dragged tab is dropped onto itself', () => {
    const { onTabsChange } = renderWorkbench();

    fireEvent.dragStart(screen.getByText('b.ts'));
    fireEvent.dragOver(screen.getByText('b.ts'));
    fireEvent.drop(screen.getByText('b.ts'));

    expect(onTabsChange).not.toHaveBeenCalled();
  });

  it('keeps close buttons and context menus targeting the intended tab after reorder', () => {
    const Harness: React.FC = () => {
      const [tabState, setTabState] = React.useState<FileViewerWorkbenchTab[]>(tabs);
      const [activeTabId, setActiveTabId] = React.useState<string | null>('/docs/a.md');
      const adapter: FileViewerWorkbenchAdapter = React.useMemo(() => ({
        readFile: vi.fn(),
        saveFile: vi.fn().mockResolvedValue(undefined),
      }), []);

      return (
        <FileViewerWorkbench
          tabs={tabState}
          activeTabId={activeTabId}
          adapter={adapter}
          onTabsChange={setTabState}
          onActiveTabChange={setActiveTabId}
        />
      );
    };

    render(<Harness />);

    const target = getTabWithRect('a.md');
    fireEvent.dragStart(screen.getByText('c.mmd'));
    fireDragEvent(target, 'dragOver', { clientX: 10 });
    fireDragEvent(target, 'drop', { clientX: 10 });

    fireEvent.contextMenu(screen.getByText('c.mmd'));
    fireEvent.click(screen.getByText('shared.fileViewer.tabContextMenu.closeToTheRight'));

    expect(screen.getByText('c.mmd')).toBeInTheDocument();
    expect(screen.queryByText('a.md')).not.toBeInTheDocument();
    expect(screen.queryByText('b.ts')).not.toBeInTheDocument();
  });

  it('opens the workspace-style action menu for copy path and reveal', () => {
    const { adapter } = renderWorkbench();

    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.copyPath'));
    expect(adapter.copyPath).toHaveBeenCalledWith('/docs/a.md');

    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
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
        Reflect.deleteProperty(HTMLElement.prototype, 'scrollWidth');
      }
      if (clientWidthDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientWidthDescriptor);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, 'clientWidth');
      }
      if (scrollLeftDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'scrollLeft', scrollLeftDescriptor);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, 'scrollLeft');
      }
      if (scrollByDescriptor) {
        Object.defineProperty(HTMLElement.prototype, 'scrollBy', scrollByDescriptor);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, 'scrollBy');
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

  it.each([
    {
      name: 'loading',
      overrides: {
        tabs: [{ ...tabs[1], isLoading: true }],
        activeTabId: '/docs/b.ts',
      },
      text: 'shared.fileViewer.loading',
      className: 'text-muted-foreground',
    },
    {
      name: 'error',
      overrides: {
        tabs: [{ ...tabs[1], error: 'Unable to load file' }],
        activeTabId: '/docs/b.ts',
      },
      text: 'Unable to load file',
      className: 'text-destructive',
    },
  ])('renders the $name active-content state with its existing presentation class', ({
    overrides,
    text,
    className,
  }) => {
    renderWorkbench(overrides);

    expect(screen.getByText(text)).toHaveClass(
      'flex',
      'h-full',
      'items-center',
      'justify-center',
      'text-sm',
      className,
    );
  });

  it('renders the shared empty state when no file is active', () => {
    renderWorkbench({ tabs: [], activeTabId: null });
    const title = screen.getByText('shared.fileViewer.emptyState.title');

    expect(title).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
  });

  it('renders a localized unavailable state instead of the code editor for binary files', () => {
    renderWorkbench({
      tabs: [{
        id: '/archive.zip',
        path: '/archive.zip',
        name: 'archive.zip',
        content: '',
        originalContent: '',
        isModified: false,
        readable: false,
        unreadableReason: 'binary',
      }],
      activeTabId: '/archive.zip',
    });

    expect(screen.getByText('shared.fileViewer.unavailable.binary.title')).toBeInTheDocument();
    expect(screen.getByText('shared.fileViewer.unavailable.binary.description')).toBeInTheDocument();
    expect(screen.queryByLabelText('mock-code-editor')).not.toBeInTheDocument();
  });

  it('updates only the active code tab and forwards read-only state to the editor', () => {
    renderWorkbench({
      activeTabId: '/docs/b.ts',
      readOnly: true,
    });

    expect(screen.getByLabelText('mock-code-editor')).toHaveAttribute('data-readonly', 'true');

    cleanup();
    const { onTabsChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });
    fireEvent.change(screen.getByLabelText('mock-code-editor'), {
      target: { value: 'const b = 3;' },
    });

    expect(onTabsChange).toHaveBeenCalledTimes(1);
    const nextTabs = onTabsChange.mock.calls[0][0] as FileViewerWorkbenchTab[];
    expect(nextTabs[0]).toBe(tabs[0]);
    expect(nextTabs[1]).toEqual({
      ...tabs[1],
      content: 'const b = 3;',
      isModified: true,
    });
    expect(nextTabs[2]).toBe(tabs[2]);
  });

  it('uses collision-aware primitive portals and restores focus when menus close', async () => {
    const innerWidthDescriptor = Object.getOwnPropertyDescriptor(window, 'innerWidth');
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 320,
    });

    try {
      renderWorkbench({ activeTabId: '/docs/b.ts' });

      const contextTrigger = screen.getByText('b.ts').closest<HTMLElement>('[role="tab"]');
      expect(contextTrigger).not.toBeNull();
      contextTrigger!.focus();
      fireEvent.contextMenu(contextTrigger!, {
        clientX: 500,
        clientY: 40,
      });

      const contextMenu = await screen.findByRole('menu');
      expect(document.body).toContainElement(contextMenu);
      expect(contextMenu).toHaveClass('w-56');
      expect(contextMenu).not.toHaveStyle({ top: '40px', left: '120px' });
      expect(contextMenu.parentElement).toHaveAttribute('data-radix-popper-content-wrapper');
      fireEvent.keyDown(contextMenu, { key: 'Escape' });
      await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
      expect(contextTrigger).toHaveFocus();

      cleanup();
      renderWorkbench({ activeTabId: '/docs/b.ts' });
      const moreButton = screen.getByLabelText('shared.fileViewer.toolbar.more');

      fireEvent.keyDown(moreButton, { key: 'Enter' });

      const moreMenu = await screen.findByRole('menu');
      expect(document.body).toContainElement(moreMenu);
      expect(moreMenu).toHaveClass('w-56');
      expect(moreMenu.parentElement).toHaveAttribute('data-radix-popper-content-wrapper');
      await waitFor(() => {
        expect(screen.getByText('shared.fileViewer.toolbar.save')).toHaveFocus();
      });

      fireEvent.keyDown(moreMenu, { key: 'Escape' });
      await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
      expect(moreButton).toHaveFocus();
    } finally {
      if (innerWidthDescriptor) {
        Object.defineProperty(window, 'innerWidth', innerWidthDescriptor);
      }
    }
  });

  it('keeps tab bar, editor toolbar, content, and status as ordered shell children', () => {
    renderWorkbench({
      activeTabId: '/docs/b.ts',
      headerActions: <button type="button">header action</button>,
    });

    const tabBarActions = screen.getByTestId('file-viewer-tabbar-actions');
    const tabBar = tabBarActions.parentElement;
    const root = tabBar?.parentElement;

    expect(root).toHaveClass('flex', 'h-full', 'min-h-0', 'flex-col', 'bg-background');
    expect(root?.children).toHaveLength(4);
    expect(root?.children[0]).toBe(tabBar);
    expect(root?.children[0]).toHaveClass('relative', 'flex', 'h-10', 'border-b', 'bg-card');
    expect(root?.children[1]).toHaveClass('flex', 'h-10', 'border-b', 'bg-card');
    expect(root?.children[2]).toHaveClass('min-h-0', 'flex-1', 'overflow-hidden');
    expect(root?.children[3]).toHaveClass('flex', 'h-8', 'border-t', 'bg-muted/30');
  });

  it('lets primitives close menus on Escape and collapses the workbench only while expanded', () => {
    const onCollapsedExpandedChange = vi.fn();
    renderWorkbench({
      activeTabId: '/docs/b.ts',
      isExpanded: false,
      onExpandedChange: onCollapsedExpandedChange,
    });

    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
    expect(screen.getByText('shared.fileViewer.toolbar.copyPath')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onCollapsedExpandedChange).not.toHaveBeenCalled();
    expect(screen.queryByText('shared.fileViewer.toolbar.copyPath')).not.toBeInTheDocument();

    cleanup();
    const onExpandedChange = vi.fn();
    renderWorkbench({
      activeTabId: '/docs/b.ts',
      isExpanded: true,
      onExpandedChange,
    });

    fireEvent.contextMenu(screen.getByText('b.ts'));
    expect(screen.getByText('shared.fileViewer.tabContextMenu.closeSaved')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onExpandedChange).toHaveBeenCalledWith(false);
    expect(screen.queryByText('shared.fileViewer.tabContextMenu.closeSaved')).not.toBeInTheDocument();
  });

  it('reverts the active tab to its original content and clears its dirty state', () => {
    const { onTabsChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });

    fireEvent.keyDown(screen.getByLabelText('shared.fileViewer.toolbar.more'), { key: 'Enter' });
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.revert'));

    expect(onTabsChange).toHaveBeenCalledWith([
      tabs[0],
      {
        ...tabs[1],
        content: 'const b = 1;',
        isModified: false,
      },
      tabs[2],
    ]);
  });

  it('selects the tab at the same position after closing the active middle tab', () => {
    const { onTabsChange, onActiveTabChange } = renderWorkbench({ activeTabId: '/docs/b.ts' });
    const middleTab = screen.getByText('b.ts').closest<HTMLElement>('[draggable="true"]');

    expect(middleTab).not.toBeNull();
    fireEvent.click(within(middleTab!).getByLabelText('shared.fileViewer.tabs.close'));

    expect(onTabsChange).toHaveBeenCalledWith([tabs[0], tabs[2]]);
    expect(onActiveTabChange).toHaveBeenCalledWith('/docs/c.mmd');
  });
});
