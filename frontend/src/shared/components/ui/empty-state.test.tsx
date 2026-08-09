import { FileText } from 'lucide-react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EmptyState } from './empty-state';

describe('EmptyState', () => {
  it('owns the compact empty-state visual contract', () => {
    const { container } = render(
      <EmptyState
        icon={FileText}
        title="No selection"
        description="Choose an item to continue."
        action={<button type="button">Create item</button>}
      />,
    );

    expect(screen.getByText('No selection')).toHaveClass(
      'mb-1',
      'text-sm',
      'font-medium',
      'text-foreground',
    );
    expect(screen.getByText('Choose an item to continue.')).toHaveClass(
      'text-xs',
      'text-muted-foreground',
    );
    expect(screen.getByRole('button', { name: 'Create item' })).toBeInTheDocument();
    expect(container.querySelector('svg')).toHaveClass(
      'mb-3',
      'h-10',
      'w-10',
      'opacity-60',
    );
    expect(screen.getByText('No selection').parentElement).toHaveClass(
      'max-w-sm',
      'text-center',
    );
  });
});
