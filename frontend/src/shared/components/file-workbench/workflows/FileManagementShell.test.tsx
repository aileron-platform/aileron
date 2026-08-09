import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it } from 'vitest';
import { FileManagementShell } from './FileManagementShell';

describe('FileManagementShell', () => {
  it('renders sidebar, main content, and overlay regions', () => {
    render(
      <FileManagementShell
        sidebar={<div>sidebar</div>}
        mainContent={<div>main-content</div>}
        overlay={<div>overlay</div>}
      />,
    );

    expect(screen.getByText('sidebar')).toBeInTheDocument();
    expect(screen.getByText('main-content')).toBeInTheDocument();
    expect(screen.getByText('overlay')).toBeInTheDocument();
  });

  it('fills the available flex container width without forcing content overflow', () => {
    const { container } = render(
      <div className="flex min-w-0 flex-1 overflow-hidden">
        <FileManagementShell
          sidebar={<div>sidebar</div>}
          mainContent={<div>main-content</div>}
        />
      </div>,
    );

    const shell = container.querySelector('.relative.flex');

    expect(shell).toHaveClass('w-full');
    expect(shell).toHaveClass('min-w-0');
  });
});
