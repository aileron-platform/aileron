import React from 'react';
import { createEvent, fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbenchSplitView } from './FileViewerWorkbenchSplitView';
import type { FileViewerWorkbenchAdapter, FileViewerWorkbenchTab } from './types';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: { value: string; onChange?: (value: string) => void }) => (
    <textarea
      aria-label="mock-code-editor"
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

const tabs: FileViewerWorkbenchTab[] = [
  { id: 'a.ts', path: '/a.ts', name: 'a.ts', content: 'A', originalContent: 'A', isModified: false },
  { id: 'b.ts', path: '/b.ts', name: 'b.ts', content: 'B', originalContent: 'B', isModified: false },
];

const adapter: FileViewerWorkbenchAdapter = { readFile: vi.fn() };

// jsdom reports zero-sized rects, so pointer-side detection needs a mocked
// rect on the tab element: clientX 10 lands on the left half, 90 on the right.
const getTabWithRect = (name: string): HTMLElement => {
  const element = screen.getByText(name).closest('[draggable="true"]');
  if (!(element instanceof HTMLElement)) throw new Error(`Tab element not found for ${name}`);
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({
    width: 100, height: 32, top: 0, left: 0, right: 100, bottom: 32, x: 0, y: 0,
    toJSON: () => ({}),
  } as DOMRect);
  return element;
};

const createWorkbenchTabDataTransfer = (tabId: string) => ({
  getData: (type: string) => (type === 'application/x-aileron-file-workbench-tab' ? tabId : ''),
  setData: vi.fn(),
  types: ['application/x-aileron-file-workbench-tab'],
  effectAllowed: '',
  dropEffect: '',
});

// jsdom lacks DragEvent, so createEvent falls back to a plain Event and
// silently drops MouseEvent fields; clientX must be attached manually.
const fireDragEvent = (
  element: Element,
  type: 'dragOver' | 'drop',
  { clientX, dataTransfer }: { clientX: number; dataTransfer: ReturnType<typeof createWorkbenchTabDataTransfer> },
) => {
  const event = createEvent[type](element, { dataTransfer });
  Object.defineProperty(event, 'clientX', { value: clientX });
  fireEvent(element, event);
};

describe('FileViewerWorkbenchSplitView', () => {
  it('renders a single pane with all tabs when uncontrolled and no split has happened', () => {
    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
      />,
    );

    expect(screen.getAllByLabelText('mock-code-editor')).toHaveLength(1);
    expect(screen.getByText('a.ts')).toBeInTheDocument();
    expect(screen.getByText('b.ts')).toBeInTheDocument();
  });

  it('forwards sizes and onSizesChange straight through to SplitPaneGroup', () => {
    const onSizesChange = vi.fn();
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={vi.fn()}
        sizes={[65, 35]}
        onSizesChange={onSizesChange}
      />,
    );

    expect(screen.getByTestId('split-pane-pane-a')).toHaveStyle({ width: '65%' });

    const divider = screen.getByRole('separator');
    vi.spyOn(divider.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      width: 1000, height: 500, top: 0, left: 0, right: 1000, bottom: 500, x: 0, y: 0, toJSON: () => ({}),
    });
    fireEvent.mouseDown(divider, { clientX: 650 });
    fireEvent.mouseMove(document, { clientX: 700 });
    fireEvent.mouseUp(document);

    expect(onSizesChange).toHaveBeenCalledWith([70, 30]);
  });

  it('adds a newly-opened tab (appearing in tabs after mount) to the pane holding the active tab, in uncontrolled mode', () => {
    const Harness: React.FC = () => {
      const [liveTabs, setLiveTabs] = React.useState(tabs);
      return (
        <>
          <button type="button" onClick={() => setLiveTabs([...tabs, {
            id: 'c.ts', path: '/c.ts', name: 'c.ts', content: 'C', originalContent: 'C', isModified: false,
          }])}>
            open-c
          </button>
          <FileViewerWorkbenchSplitView
            tabs={liveTabs}
            activeTabId="a.ts"
            adapter={adapter}
            onTabsChange={vi.fn()}
            onActiveTabChange={vi.fn()}
          />
        </>
      );
    };

    render(<Harness />);
    expect(screen.queryByText('c.ts')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('open-c'));

    expect(screen.getByText('c.ts')).toBeInTheDocument();
    expect(screen.getAllByLabelText('mock-code-editor')).toHaveLength(1);
  });

  it('adds a newly-opened tab to the pane holding the active tab, in controlled mode, and reports it via onPanesChange', () => {
    const controlledPanes = [{ id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' }];
    const onPanesChange = vi.fn();

    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={[tabs[0]]}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );
    expect(onPanesChange).not.toHaveBeenCalled();

    rerender(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-a', tabIds: ['a.ts', 'b.ts'], activeTabId: 'b.ts' },
    ]);
  });

  it('adds a newly-opened tab to the most recently active pane after the workspace active tab changes', () => {
    const controlledPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];
    const onPanesChange = vi.fn();
    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );

    fireEvent.click(screen.getByText('b.ts'));

    rerender(
      <FileViewerWorkbenchSplitView
        tabs={[...tabs, {
          id: 'c.ts', path: '/c.ts', name: 'c.ts', content: 'C', originalContent: 'C', isModified: false,
        }]}
        activeTabId="c.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(onPanesChange).toHaveBeenLastCalledWith([
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts', 'c.ts'], activeTabId: 'c.ts' },
    ]);
  });

  it('forwards pane content changes to the shared tab registry when tab ids stay the same', () => {
    const onTabsChange = vi.fn();

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={onTabsChange}
        onActiveTabChange={vi.fn()}
        panes={[{ id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' }]}
        onPanesChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('mock-code-editor'), { target: { value: 'const updated = true;' } });

    expect(onTabsChange).toHaveBeenCalledWith([
      { ...tabs[0], content: 'const updated = true;', isModified: true },
      tabs[1],
    ]);
  });

  it('prunes a tab id no longer present in tabs from every pane, instead of rendering a missing tab', () => {
    const controlledPanes = [
      { id: 'pane-a', tabIds: ['a.ts', 'b.ts'], activeTabId: 'a.ts' },
    ];
    const onPanesChange = vi.fn();

    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );
    expect(onPanesChange).not.toHaveBeenCalled();

    rerender(
      <FileViewerWorkbenchSplitView
        tabs={[tabs[0]]}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
    ]);
  });

  it('reconciles a freshly-restored controlled panes prop even when the tabs id set has not changed', () => {
    const onPanesChange = vi.fn();

    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={[tabs[0]]}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={undefined}
        onPanesChange={onPanesChange}
      />,
    );
    expect(onPanesChange).not.toHaveBeenCalled();

    const restoredPanes = [
      { id: 'restored-pane-0', tabIds: ['a.ts', 'stale.ts'], activeTabId: 'stale.ts' },
    ];
    rerender(
      <FileViewerWorkbenchSplitView
        tabs={[tabs[0]]}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={restoredPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'restored-pane-0', tabIds: ['a.ts'], activeTabId: 'a.ts' },
    ]);
  });

  it('syncs an external activeTabId change onto the pane that already holds that tab', () => {
    const controlledPanes = [{ id: 'pane-a', tabIds: ['a.ts', 'b.ts'], activeTabId: 'a.ts' }];
    const onPanesChange = vi.fn();

    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );
    expect(onPanesChange).not.toHaveBeenCalled();

    // Simulates clicking an already-open file in the sidebar: activeTabId changes
    // externally to a tab that is already a member of pane-a, with no tab added or removed.
    rerender(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="b.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={controlledPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-a', tabIds: ['a.ts', 'b.ts'], activeTabId: 'b.ts' },
    ]);
  });

  it('splits a tab into a new pane via the tab context menu, moving it out of the source pane', () => {
    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
      />,
    );

    fireEvent.contextMenu(screen.getByText('b.ts'));
    fireEvent.click(screen.getByText('shared.fileViewer.tabContextMenu.splitOpen'));

    expect(screen.getAllByLabelText('mock-code-editor')).toHaveLength(2);
    const paneElements = screen.getAllByTestId(/^split-pane-/);
    expect(paneElements).toHaveLength(2);
    expect(within(paneElements[0]).queryByText('b.ts')).not.toBeInTheDocument();
    expect(within(paneElements[1]).getByText('b.ts')).toBeInTheDocument();
  });

  it('disables Split Open once 4 panes already exist', () => {
    const manyTabs: FileViewerWorkbenchTab[] = Array.from({ length: 4 }, (_, index) => ({
      id: `t${index}.ts`, path: `/t${index}.ts`, name: `t${index}.ts`, content: '', originalContent: '', isModified: false,
    }));
    const fourPanes = manyTabs.map((tab, index) => ({ id: `pane-${index}`, tabIds: [tab.id], activeTabId: tab.id }));

    render(
      <FileViewerWorkbenchSplitView
        tabs={manyTabs}
        activeTabId="t0.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={fourPanes}
        onPanesChange={vi.fn()}
      />,
    );

    fireEvent.contextMenu(screen.getByText('t0.ts'));
    expect(screen.getByRole('menuitem', {
      name: 'shared.fileViewer.tabContextMenu.splitOpen',
    })).toHaveAttribute('aria-disabled', 'true');
  });

  it('disables Split Open for a pane that contains only the selected tab', () => {
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={vi.fn()}
      />,
    );

    fireEvent.contextMenu(screen.getByText('a.ts'));

    expect(screen.getByRole('menuitem', {
      name: 'shared.fileViewer.tabContextMenu.splitOpen',
    })).toHaveAttribute('aria-disabled', 'true');
  });

  it('moves a tab between two existing panes on foreign tab drop, dropping the now-empty source pane from the report', () => {
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];
    const onPanesChange = vi.fn();

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={onPanesChange}
      />,
    );

    const dataTransfer = createWorkbenchTabDataTransfer('a.ts');
    const target = getTabWithRect('b.ts');
    fireDragEvent(target, 'dragOver', { clientX: 10, dataTransfer });
    fireDragEvent(target, 'drop', { clientX: 10, dataTransfer });

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-b', tabIds: ['a.ts', 'b.ts'], activeTabId: 'a.ts' },
    ]);
  });

  it('inserts after the target tab when the drop lands on its right half', () => {
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];
    const onPanesChange = vi.fn();

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={onPanesChange}
      />,
    );

    const dataTransfer = createWorkbenchTabDataTransfer('a.ts');
    const target = getTabWithRect('b.ts');
    fireDragEvent(target, 'dragOver', { clientX: 90, dataTransfer });
    fireDragEvent(target, 'drop', { clientX: 90, dataTransfer });

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-b', tabIds: ['b.ts', 'a.ts'], activeTabId: 'a.ts' },
    ]);
  });

  it('appends to the target pane when the drop lands on its tab strip empty area', () => {
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];
    const onPanesChange = vi.fn();

    render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={onPanesChange}
      />,
    );

    const dataTransfer = createWorkbenchTabDataTransfer('a.ts');
    const strip = screen.getByText('b.ts').closest('[draggable="true"]')!.parentElement!;
    fireEvent.dragOver(strip, { dataTransfer });
    fireEvent.drop(strip, { dataTransfer });

    expect(onPanesChange).toHaveBeenCalledWith([
      { id: 'pane-b', tabIds: ['b.ts', 'a.ts'], activeTabId: 'a.ts' },
    ]);
  });

  it('collapses a pane whose last tab was moved away, keeping the remaining panes', () => {
    const twoPanes = [
      { id: 'pane-a', tabIds: ['a.ts'], activeTabId: 'a.ts' },
      { id: 'pane-b', tabIds: ['b.ts'], activeTabId: 'b.ts' },
    ];
    const onPanesChange = vi.fn();

    const { rerender } = render(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={twoPanes}
        onPanesChange={onPanesChange}
      />,
    );

    const dataTransfer = createWorkbenchTabDataTransfer('a.ts');
    const target = getTabWithRect('b.ts');
    fireDragEvent(target, 'dragOver', { clientX: 10, dataTransfer });
    fireDragEvent(target, 'drop', { clientX: 10, dataTransfer });

    const [nextPanes] = onPanesChange.mock.calls[0];
    expect(nextPanes).toEqual([{ id: 'pane-b', tabIds: ['a.ts', 'b.ts'], activeTabId: 'a.ts' }]);

    rerender(
      <FileViewerWorkbenchSplitView
        tabs={tabs}
        activeTabId="a.ts"
        adapter={adapter}
        onTabsChange={vi.fn()}
        onActiveTabChange={vi.fn()}
        panes={nextPanes}
        onPanesChange={onPanesChange}
      />,
    );

    expect(screen.queryAllByTestId(/split-pane-/)).toHaveLength(1);
  });
});
