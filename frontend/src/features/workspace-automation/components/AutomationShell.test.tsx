import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AutomationShell } from './AutomationShell';

describe('AutomationShell', () => {
  it('keeps the required navigation slot in the original first-child position', () => {
    render(
      <AutomationShell navigationSlot={<div data-testid="navigation-slot" />}>
        <div data-testid="automation-content" />
      </AutomationShell>,
    );

    const navigationSlot = screen.getByTestId('navigation-slot');
    expect(navigationSlot.parentElement).toHaveClass(
      'h-screen',
      'w-screen',
      'flex',
      'flex-col',
    );
    expect(navigationSlot.parentElement?.firstElementChild).toBe(navigationSlot);
    expect(screen.getByTestId('automation-content')).toBeInTheDocument();
  });
});
