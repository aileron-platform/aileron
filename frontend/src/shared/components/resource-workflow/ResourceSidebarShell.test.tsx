import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';
import { ResourceSidebarShell } from './ResourceSidebarShell';

describe('ResourceSidebarShell', () => {
  it('renders toolbar-like scope content below the search slot', () => {
    render(
      <ResourceSidebarShell
        header={<span>header-slot</span>}
        scopeFilter={<span>scope-slot</span>}
        search={<span>search-slot</span>}
        body={<span>body-slot</span>}
        footer={<span>footer-slot</span>}
      />,
    );

    expect(screen.getByText('header-slot').compareDocumentPosition(screen.getByText('search-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText('search-slot').compareDocumentPosition(screen.getByText('scope-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText('scope-slot').compareDocumentPosition(screen.getByText('body-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText('body-slot').compareDocumentPosition(screen.getByText('footer-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('omits missing slots without rendering placeholders', () => {
    const { container } = render(
      <ResourceSidebarShell
        header={<span>header-slot</span>}
        body={<span>body-slot</span>}
      />,
    );

    expect(screen.getByText('header-slot')).toBeInTheDocument();
    expect(screen.getByText('body-slot')).toBeInTheDocument();
    expect(container.querySelectorAll(':scope > div > div')).toHaveLength(2);
  });
});
