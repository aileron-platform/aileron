import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

const authState = vi.hoisted(() => ({
  isLoading: false,
  allowedOperations: [] as string[],
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    isLoading: authState.isLoading,
    hasPlatformOperation: (operationId: string) => (
      authState.allowedOperations.includes(operationId)
    ),
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { RequirePlatformOperation } from './RequirePlatformOperation';

const renderGuard = () => render(
  <RequirePlatformOperation operationId={OPERATION_IDS.platformResourcesRead}>
    <div>protected-platform-resources</div>
  </RequirePlatformOperation>,
);

describe('RequirePlatformOperation', () => {
  beforeEach(() => {
    authState.isLoading = false;
    authState.allowedOperations = [];
  });

  it('shows loading while the authoritative snapshot is unresolved', () => {
    authState.isLoading = true;
    renderGuard();

    expect(screen.getByTestId('entry-frame')).toBeInTheDocument();
    expect(screen.queryByText('protected-platform-resources')).not.toBeInTheDocument();
  });

  it('renders only when the exact operation is allowed', () => {
    authState.allowedOperations = ['platform_resources.read'];
    renderGuard();

    expect(screen.getByText('protected-platform-resources')).toBeInTheDocument();
  });

  it('fails closed when the operation is absent', () => {
    renderGuard();

    expect(screen.getByRole('alert')).toHaveTextContent(
      'common.authorization.accessDeniedTitle',
    );
    expect(screen.queryByText('protected-platform-resources')).not.toBeInTheDocument();
  });
});
