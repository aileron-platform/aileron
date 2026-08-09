import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceFeatureLoading } from './WorkspaceFeatureLoading';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('WorkspaceFeatureLoading', () => {
  it('keeps feature loading inside the workspace content region', () => {
    render(<WorkspaceFeatureLoading labelKey="workspace.layout.loading.fileTree" />);

    const loading = screen.getByTestId('workspace-feature-loading');
    expect(loading).toHaveAttribute('role', 'status');
    expect(loading).toHaveAttribute('aria-label', 'workspace.layout.loading.fileTree');
    expect(loading).toHaveAttribute('aria-busy', 'true');
    expect(loading).toHaveClass('min-h-0');
  });

  it('uses the workspace loading key by default', () => {
    render(<WorkspaceFeatureLoading />);

    expect(screen.getByRole('status')).toHaveAccessibleName('workspace.layout.loading.workspace');
  });
});
