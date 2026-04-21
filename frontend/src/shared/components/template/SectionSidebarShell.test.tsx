import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SectionSidebarShell from './SectionSidebarShell';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('SectionSidebarShell', () => {
  it('renders unified header, search, and body regions', () => {
    render(
      <SectionSidebarShell
        title="Skills"
        actions={<button type="button">add</button>}
        searchValue="foo"
        onSearchChange={() => {}}
        onSearchClear={() => {}}
        searchPlaceholder="Search files"
        body={<div>body content</div>}
      />,
    );

    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'add' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search files')).toBeInTheDocument();
    expect(screen.getByText('body content')).toBeInTheDocument();
  });
});
