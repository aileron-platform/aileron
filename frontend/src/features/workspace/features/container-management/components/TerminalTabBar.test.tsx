import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import type { TerminalTab } from '@/features/workspace/realtime/terminalStore';
import { TerminalTabBar } from './TerminalTabBar';

const createTab = (tabId: string, workingDirectory: string): TerminalTab => ({
  tabId,
  sessionId: `session-${tabId}`,
  workingDirectory,
  lastActivityAt: null,
});

const renderTabBar = ({
  tabs = [createTab('tab-1', '/workspace')],
  activeTabId = 'tab-1',
  onCloseTab = vi.fn(),
}: {
  tabs?: ReturnType<typeof createTab>[];
  activeTabId?: string;
  onCloseTab?: ReturnType<typeof vi.fn>;
} = {}) => {
  render(
    <TerminalTabBar
      tabs={tabs}
      activeTabId={activeTabId}
      onSwitchTab={vi.fn()}
      onCloseTab={onCloseTab}
      onAddTab={vi.fn()}
      onContextMenu={vi.fn()}
      closeLabel="Close terminal"
      newTooltip="New terminal"
      scrollLeftLabel="Scroll tabs left"
      scrollRightLabel="Scroll tabs right"
    />,
  );
  return { onCloseTab };
};

describe('TerminalTabBar', () => {
  it('uses the session-level terminal icon and shows the working directory context', () => {
    renderTabBar({
      tabs: [
        createTab('tab-1', '/workspace/apps/frontend'),
        createTab('tab-2', '/'),
      ],
    });

    const frontendTab = screen.getByRole('tab', { name: 'frontend' });
    expect(frontendTab).toHaveAttribute('title', '/workspace/apps/frontend');
    expect(frontendTab.querySelector('.lucide-terminal')).not.toBeNull();
    expect(screen.getByRole('tab', { name: '/' })).toHaveAttribute('title', '/');
  });

  it('disables closing when there is only one terminal tab', () => {
    const { onCloseTab } = renderTabBar();

    const closeButton = screen.getByRole('button', { name: 'Close terminal' });
    expect(closeButton).toBeDisabled();

    fireEvent.click(closeButton);

    expect(onCloseTab).not.toHaveBeenCalled();
  });

  it('allows closing when more than one terminal tab exists', () => {
    const { onCloseTab } = renderTabBar({
      tabs: [
        createTab('tab-1', '/workspace/one'),
        createTab('tab-2', '/workspace/two'),
      ],
    });

    const closeButtons = screen.getAllByRole('button', { name: 'Close terminal' });
    expect(closeButtons[0]).not.toBeDisabled();

    fireEvent.click(closeButtons[0]);

    expect(onCloseTab).toHaveBeenCalledWith('tab-1');
  });
});
