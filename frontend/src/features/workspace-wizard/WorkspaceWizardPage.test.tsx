import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import WorkspaceWizardPage from './WorkspaceWizardPage';

const { resetMock } = vi.hoisted(() => ({
  resetMock: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock('./hooks/useWorkspaceWizard', () => ({
  useWorkspaceWizard: () => ({
    state: {
      step: 'basicInfo',
      basicInfo: {
        name: '',
        description: '',
        agenticTools: ['claude-code'],
      },
      runtimeConfig: {
        runtime: 'universal',
        setupScript: '',
        envVars: [],
      },
      createdWorkspaceId: null,
      isSubmitting: false,
      isPolling: false,
      error: null,
    },
    setBasicInfo: vi.fn(),
    setRuntimeConfig: vi.fn(),
    submitBasicInfo: vi.fn(),
    submitRuntimeConfig: vi.fn(),
    retryWorkspaceCreation: vi.fn(),
    runtimeHelpers: {
      addEnvVar: vi.fn(),
      updateEnvVar: vi.fn(),
      removeEnvVar: vi.fn(),
    },
    goToStep: vi.fn(),
    reset: resetMock,
    completeWizard: vi.fn(),
  }),
}));

vi.mock('./components/steps/BasicInfoStep', () => ({
  default: () => <div>basic-info-step</div>,
}));

vi.mock('./components/steps/RuntimeConfigStep', () => ({
  default: () => <div>runtime-config-step</div>,
}));

vi.mock('./components/steps/WorkspaceCreationStep', () => ({
  default: () => <div>workspace-creation-step</div>,
}));

describe('WorkspaceWizardPage', () => {
  it('keeps navigation and content in the existing top-level DOM', () => {
    const { container } = render(
      <MemoryRouter>
        <WorkspaceWizardPage
          navigationSlot={<div data-testid="wizard-navigation">navigation</div>}
          userId="user-1"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('wizard-navigation')).toBeInTheDocument();
    expect(screen.getByText('basic-info-step')).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass('flex', 'h-screen', 'w-full', 'flex-col', 'bg-background');
    expect(container.querySelector('main')).toHaveClass(
      'flex-1',
      'overflow-auto',
      'px-10',
      'sm:px-24',
      'lg:px-40',
      'xl:px-56',
      '2xl:px-72',
      'py-10',
    );
  });
});
