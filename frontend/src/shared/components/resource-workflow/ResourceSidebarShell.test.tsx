import React from 'react';
import userEvent from '@testing-library/user-event';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';
import { ResourceSidebarShell } from './ResourceSidebarShell';
import { useResourceSidebarController } from './useResourceSidebarController';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('ResourceSidebarShell', () => {
  it('renders slots in the expected order', () => {
    render(
      <ResourceSidebarShell
        header={<span>header-slot</span>}
        scopeFilter={<span>scope-slot</span>}
        search={<span>search-slot</span>}
        body={<span>body-slot</span>}
        footer={<span>footer-slot</span>}
      />,
    );

    expect(screen.getByText('header-slot').compareDocumentPosition(screen.getByText('scope-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText('scope-slot').compareDocumentPosition(screen.getByText('search-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText('search-slot').compareDocumentPosition(screen.getByText('body-slot'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
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

  it('renders the default search control with an i18n placeholder', async () => {
    const user = userEvent.setup();
    const onSearchChange = vi.fn();

    render(
      <ResourceSidebarShell
        searchValue=""
        onSearchChange={onSearchChange}
        body={<span>body-slot</span>}
      />,
    );

    await user.type(screen.getByPlaceholderText('resource.sidebar.search.placeholder'), 'abc');

    expect(onSearchChange).toHaveBeenCalled();
  });
});

describe('useResourceSidebarController', () => {
  it('tracks query, collapsed state, and selected id without exposing scope state', () => {
    const { result } = renderHook(() => useResourceSidebarController());

    act(() => {
      result.current.setQuery('foo');
      result.current.setCollapsed(true);
      result.current.setSelectedId('abc');
    });

    expect(result.current.query).toBe('foo');
    expect(result.current.collapsed).toBe(true);
    expect(result.current.selectedId).toBe('abc');
    expect('scope' in result.current).toBe(false);
    expect('setScope' in result.current).toBe(false);
  });
});
