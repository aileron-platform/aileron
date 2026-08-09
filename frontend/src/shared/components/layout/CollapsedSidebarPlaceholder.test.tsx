import { render, screen } from '@/__tests__/utils/render';
import { Folder } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { CollapsedSidebarPlaceholder } from './CollapsedSidebarPlaceholder';

describe('CollapsedSidebarPlaceholder', () => {
  it('renders the collapsed sidebar icon with the compact second-column hover block', () => {
    render(
      <CollapsedSidebarPlaceholder
        icon={Folder}
        testId="collapsed-sidebar-icon"
      />,
    );

    const iconTile = screen.getByTestId('collapsed-sidebar-icon');
    expect(iconTile).toHaveClass('p-0.5');
    expect(iconTile).toHaveClass('rounded');
    expect(iconTile).toHaveClass('text-sidebar-foreground');
    expect(iconTile).toHaveClass('hover:bg-sidebar-accent');
    expect(iconTile).not.toHaveClass('h-8');
    expect(iconTile).not.toHaveClass('w-8');
    expect(iconTile.querySelector('svg')).toBeInTheDocument();
  });
});
