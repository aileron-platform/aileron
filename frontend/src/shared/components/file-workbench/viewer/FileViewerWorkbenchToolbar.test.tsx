import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileViewerWorkbenchToolbar } from './FileViewerWorkbenchToolbar';
import type { FileViewerWorkbenchTab } from './types';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const modifiedTab: FileViewerWorkbenchTab = {
  id: 'tab-1',
  path: '/docs/readme.md',
  name: 'readme.md',
  content: '# Updated',
  originalContent: '# Readme',
  isModified: true,
};

const renderToolbar = (overrides: Partial<React.ComponentProps<typeof FileViewerWorkbenchToolbar>> = {}) => {
  const props: React.ComponentProps<typeof FileViewerWorkbenchToolbar> = {
    headerActions: <button type="button">header-action</button>,
    formatActions: <button type="button">format-action</button>,
    canSave: true,
    activeTab: modifiedTab,
    isExpanded: false,
    onSave: vi.fn(),
    onToggleExpanded: vi.fn(),
    onOpenMoreMenu: vi.fn(),
    moreButtonRef: React.createRef<HTMLButtonElement>(),
    ...overrides,
  };

  render(<FileViewerWorkbenchToolbar {...props} />);
  return props;
};

describe('FileViewerWorkbenchToolbar', () => {
  it('renders host and format actions in the left group and workbench actions on the right', () => {
    renderToolbar();

    const leftGroup = screen.getByTestId('file-viewer-toolbar-left');
    const rightGroup = screen.getByTestId('file-viewer-toolbar-right');

    expect(within(leftGroup).getByText('header-action')).toBeInTheDocument();
    expect(within(leftGroup).getByText('format-action')).toBeInTheDocument();
    expect(within(rightGroup).getByLabelText('shared.fileViewer.toolbar.save')).toBeInTheDocument();
    expect(within(rightGroup).getByLabelText('shared.fileViewer.toolbar.expand')).toBeInTheDocument();
    expect(within(rightGroup).getByLabelText('shared.fileViewer.toolbar.more')).toBeInTheDocument();
  });

  it('keeps the left group valid when format actions are absent', () => {
    renderToolbar({ formatActions: null });

    const leftGroup = screen.getByTestId('file-viewer-toolbar-left');

    expect(within(leftGroup).getByText('header-action')).toBeInTheDocument();
    expect(within(leftGroup).queryByText('format-action')).not.toBeInTheDocument();
  });

  it('keeps save disabled for an unmodified generic text tab without format actions', () => {
    renderToolbar({ activeTab: { ...modifiedTab, isModified: false }, formatActions: null });

    expect(screen.getByLabelText('shared.fileViewer.toolbar.save')).toBeDisabled();
  });

  it('hides save for an unmodified specialized tab with format actions', () => {
    renderToolbar({ activeTab: { ...modifiedTab, isModified: false } });

    expect(screen.queryByLabelText('shared.fileViewer.toolbar.save')).not.toBeInTheDocument();
  });

  it('hides save when saving is unavailable', () => {
    renderToolbar({ canSave: false });

    expect(screen.queryByLabelText('shared.fileViewer.toolbar.save')).not.toBeInTheDocument();
  });

  it('dispatches save, expand, and more actions', () => {
    const props = renderToolbar();

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.save'));
    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.expand'));
    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));

    expect(props.onSave).toHaveBeenCalledTimes(1);
    expect(props.onToggleExpanded).toHaveBeenCalledTimes(1);
    expect(props.onOpenMoreMenu).toHaveBeenCalledTimes(1);
  });

  it('uses the collapse label when expanded', () => {
    renderToolbar({ isExpanded: true });

    expect(screen.getByLabelText('shared.fileViewer.toolbar.collapse')).toBeInTheDocument();
  });
});
