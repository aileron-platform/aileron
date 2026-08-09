import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it } from 'vitest';
import { WorkspaceStatusBar } from './WorkspaceStatusBar';

describe('WorkspaceStatusBar', () => {
  it('renders left and right slot content with the shared base styling', () => {
    render(
      <WorkspaceStatusBar
        data-testid="workspace-status-bar"
        left={<span>current/path</span>}
        right={<button type="button">Clear</button>}
      />,
    );

    const bar = screen.getByTestId('workspace-status-bar');
    expect(bar).toHaveClass('h-8');
    expect(bar).toHaveClass('border-t');
    expect(bar).toHaveClass('border-border');
    expect(bar).toHaveClass('bg-muted/30');
    expect(bar).toHaveClass('text-muted-foreground');
    expect(screen.getByText('current/path')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument();
  });

  it('renders with no slots without throwing', () => {
    render(<WorkspaceStatusBar data-testid="empty-status-bar" />);

    expect(screen.getByTestId('empty-status-bar')).toBeInTheDocument();
  });
});
