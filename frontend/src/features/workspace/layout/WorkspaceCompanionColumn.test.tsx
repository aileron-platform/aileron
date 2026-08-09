import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  WorkspaceCompanionColumn,
  WorkspaceCompanionContent,
  WorkspaceCompanionHeader,
} from './WorkspaceCompanionColumn';

const mocks = vi.hoisted(() => ({
  terminalPanelMock: vi.fn(),
  companionChatPanelMock: vi.fn(),
}));

vi.mock('@/features/ai-chat/public', () => ({
  CompanionChatPanel: (props: unknown) => {
    mocks.companionChatPanelMock(props);
    return <div data-testid="companion-chat-panel" />;
  },
}));

vi.mock('@/features/workspace/features/container-management/components/TerminalPanel', () => ({
  TerminalPanel: (props: unknown) => {
    mocks.terminalPanelMock(props);
    return <div data-testid="terminal-panel" />;
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('WorkspaceCompanionColumn', () => {
  beforeEach(() => {
    mocks.terminalPanelMock.mockReset();
    mocks.companionChatPanelMock.mockReset();
  });

  it('centers tabs independently and keeps expand action at the end', () => {
    render(
      <WorkspaceCompanionHeader
        activeTab="terminal"
        canUseAgentChat
        canUseTerminal
        isExpanded={false}
        onActiveTabChange={vi.fn()}
        onToggleExpand={vi.fn()}
      />,
    );

    const header = screen.getByTestId('workspace-companion-header');
    expect(header).toHaveClass('relative', 'flex-1');
    expect(screen.getByRole('tablist')).toHaveClass('absolute', 'inset-x-0', 'justify-center');
    expect(screen.getByRole('button', { name: 'aiChat.companion.expand' }).parentElement)
      .toHaveClass('ml-auto');
  });

  it('keeps tab selection and expand action interactive', () => {
    const onActiveTabChange = vi.fn();
    const onToggleExpand = vi.fn();

    render(
      <WorkspaceCompanionHeader
        activeTab="ai-chat"
        canUseAgentChat
        canUseTerminal
        isExpanded={false}
        onActiveTabChange={onActiveTabChange}
        onToggleExpand={onToggleExpand}
      />,
    );

    fireEvent.click(screen.getByRole('tab', { name: 'aiChat.companion.tabs.terminal' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.companion.expand' }));

    expect(onActiveTabChange).toHaveBeenCalledWith('terminal');
    expect(onToggleExpand).toHaveBeenCalledTimes(1);
  });

  it('keeps the column content-only so bottom Terminal has no header DOM', () => {
    render(
      <WorkspaceCompanionColumn
        workspaceId="ws-1"
        userId="user-1"
        activeTab="terminal"
        canUseAgentChat
        canUseTerminal
        terminalPlacement="bottom"
        onActiveTabChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId('terminal-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('workspace-companion-header')).not.toBeInTheDocument();
    expect(mocks.terminalPanelMock).toHaveBeenCalledWith(expect.objectContaining({
      variant: 'compact',
      terminalPlacement: 'bottom',
    }));
  });

  it('preserves AI Chat content when the active tab resolves to chat', () => {
    render(
      <WorkspaceCompanionContent
        workspaceId="ws-1"
        userId="user-1"
        activeTab="ai-chat"
        canUseAgentChat
        canUseTerminal
        onActiveTabChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId('companion-chat-panel')).toBeInTheDocument();
    expect(mocks.companionChatPanelMock).toHaveBeenCalledWith({
      workspaceId: 'ws-1',
      userId: 'user-1',
    });
  });
});
