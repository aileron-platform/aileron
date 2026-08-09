import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { ScopeSelector } from './ScopeSelector';

const options = [
  { value: 'all', label: 'All scopes' },
  { value: 'project', label: 'Project' },
];

describe('ScopeSelector', () => {
  it('uses the shared wider width by default', () => {
    render(
      <ScopeSelector
        value="all"
        onChange={vi.fn()}
        options={options}
      />,
    );

    expect(screen.getByRole('combobox')).toHaveStyle({ width: '160px' });
  });

  it('keeps explicit widths for selectors with distinct layout needs', () => {
    render(
      <ScopeSelector
        value="all"
        onChange={vi.fn()}
        options={options}
        width={220}
      />,
    );

    expect(screen.getByRole('combobox')).toHaveStyle({ width: '220px' });
  });
});
