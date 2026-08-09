import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkspaceAutomationRoute from './WorkspaceAutomationRoute';

const mocks = vi.hoisted(() => ({
  currentLanguage: 'zh-TW',
  workspaceRuntime: {
    workspaceId: 'ws-1' as string | null,
    runtimeBaseUrl: 'http://runtime.test' as string | null,
    isLoading: false,
  },
}));

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({ workspaceRuntime: mocks.workspaceRuntime }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ state: { currentLanguage: mocks.currentLanguage } }),
}));

vi.mock('@/features/workspace-automation/public', () => ({
  WorkspaceAutomationPage: ({
    workspaceId,
    runtimeBaseUrl,
    isRuntimeLoading,
    locale,
  }: {
    workspaceId: string | null;
    runtimeBaseUrl: string | null;
    isRuntimeLoading: boolean;
    locale: 'zh-TW' | 'en-US';
  }) => (
    <div
      data-testid="workspace-automation-page"
      data-workspace-id={workspaceId ?? 'null'}
      data-runtime-base-url={runtimeBaseUrl ?? 'null'}
      data-runtime-loading={String(isRuntimeLoading)}
      data-locale={locale}
    />
  ),
}));

describe('WorkspaceAutomationRoute', () => {
  beforeEach(() => {
    mocks.currentLanguage = 'zh-TW';
    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.workspaceRuntime.runtimeBaseUrl = 'http://runtime.test';
    mocks.workspaceRuntime.isLoading = false;
  });

  it('passes the workspace runtime boundary to the page without adding a wrapper', () => {
    const { container } = render(<WorkspaceAutomationRoute />);

    const page = screen.getByTestId('workspace-automation-page');
    expect(container.firstElementChild).toBe(page);
    expect(page).toHaveAttribute('data-workspace-id', 'ws-1');
    expect(page).toHaveAttribute('data-runtime-base-url', 'http://runtime.test');
    expect(page).toHaveAttribute('data-runtime-loading', 'false');
    expect(page).toHaveAttribute('data-locale', 'zh-TW');
  });

  it('normalizes unsupported UI languages and preserves a missing runtime', () => {
    mocks.currentLanguage = 'ja-JP';
    mocks.workspaceRuntime.workspaceId = null;
    mocks.workspaceRuntime.runtimeBaseUrl = null;
    mocks.workspaceRuntime.isLoading = true;

    render(<WorkspaceAutomationRoute />);

    const page = screen.getByTestId('workspace-automation-page');
    expect(page).toHaveAttribute('data-workspace-id', 'null');
    expect(page).toHaveAttribute('data-runtime-base-url', 'null');
    expect(page).toHaveAttribute('data-runtime-loading', 'true');
    expect(page).toHaveAttribute('data-locale', 'en-US');
  });
});
