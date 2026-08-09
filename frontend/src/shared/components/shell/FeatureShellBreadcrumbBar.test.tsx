import { render, screen } from '@testing-library/react';
import { FileText } from 'lucide-react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { FeatureShellBreadcrumbBar } from './FeatureShellBreadcrumbBar';

describe('FeatureShellBreadcrumbBar', () => {
  it('renders linked and current breadcrumb items in a compact shell bar', () => {
    render(
      <MemoryRouter>
        <FeatureShellBreadcrumbBar
          items={[
            { label: 'Knowledge Base Center', to: '/knowledge-bases' },
            { label: 'Product Docs', to: '/knowledge-bases/kb-1/files' },
            { label: 'Files' },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('feature-shell-breadcrumb-bar')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Knowledge Base Center' })).toHaveAttribute('href', '/knowledge-bases');
    expect(screen.getByRole('link', { name: 'Product Docs' })).toHaveAttribute('href', '/knowledge-bases/kb-1/files');
    expect(screen.getByText('Files')).toHaveAttribute('aria-current', 'page');
    expect(screen.getAllByTestId('feature-shell-breadcrumb-separator')).toHaveLength(2);
  });

  it('combines breadcrumbs, title, info, and actions into the feature header row', () => {
    render(
      <MemoryRouter>
        <FeatureShellBreadcrumbBar
          items={[
            { label: 'Marketplace', to: '/marketplace' },
            { label: 'Package Center', to: '/marketplace/packages' },
          ]}
          title="Review Tools"
          icon={FileText}
          info={<span>Version 1.0.0</span>}
          actions={<button type="button">Back</button>}
        />
      </MemoryRouter>,
    );

    const header = screen.getByTestId('feature-shell-breadcrumb-bar');
    expect(header).toHaveClass('h-10');
    expect(header).toHaveTextContent('Marketplace');
    expect(header).toHaveTextContent('Package Center');
    expect(screen.getByRole('heading', { name: 'Review Tools' })).toBeInTheDocument();
    expect(screen.getByTestId('feature-shell-breadcrumb-icon')).toBeInTheDocument();
    expect(screen.getByText('Version 1.0.0')).toBeInTheDocument();
    const actions = screen.getByRole('button', { name: 'Back' }).parentElement;
    expect(actions).toHaveClass('ml-auto');
    expect(screen.getByTestId('feature-shell-breadcrumb-bar')).toHaveClass('w-full', 'min-w-0');
  });
});
