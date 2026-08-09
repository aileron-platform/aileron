import { fireEvent, render, screen } from '@testing-library/react';
import { FileText, Wand2 } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { FeatureNavSidebarContent, type FeatureNavItem } from './FeatureNavSidebar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const items: FeatureNavItem[] = [
  { id: 'basic', icon: FileText, labelKey: 'nav.basic' },
  { id: 'skills', icon: Wand2, labelKey: 'nav.skills', count: 3 },
];

const renderNav = (activeId: string, onSelect = vi.fn()) => {
    render(<FeatureNavSidebarContent items={items} activeId={activeId} onSelect={onSelect} />);
  return onSelect;
};

describe('FeatureNavSidebar', () => {
  it('renders item labels and count badges', () => {
    renderNav('basic');
    expect(screen.getByText('nav.basic')).toBeInTheDocument();
    expect(screen.getByText('nav.skills')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('marks the active item with aria-current', () => {
    renderNav('skills');
    expect(screen.getByRole('button', { name: 'nav.skills' })).toHaveAttribute('aria-current', 'page');
  });

  it('fires onSelect when a non-active item is clicked', () => {
    const onSelect = renderNav('basic');
    fireEvent.click(screen.getByRole('button', { name: 'nav.skills' }));
    expect(onSelect).toHaveBeenCalledWith('skills');
  });
});
