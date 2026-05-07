import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { NavigationProvider, useNavigation } from './NavigationProvider';

const ModuleProbe = () => {
  const { state } = useNavigation();

  return <div data-testid="current-module">{state.currentModule}</div>;
};

describe('NavigationProvider', () => {
  it('treats marketplace root paths as the marketplace module', async () => {
    render(
      <MemoryRouter initialEntries={['/marketplace/packages']}>
        <NavigationProvider>
          <ModuleProbe />
        </NavigationProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-module')).toHaveTextContent('marketplace');
    });
  });

  it('treats automation root paths as the automation module', async () => {
    render(
      <MemoryRouter initialEntries={['/automation/jobs']}>
        <NavigationProvider>
          <ModuleProbe />
        </NavigationProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-module')).toHaveTextContent('automation');
    });
  });

  it('treats knowledge base root paths as the knowledge-base module', async () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-bases/kb-1/files']}>
        <NavigationProvider>
          <ModuleProbe />
        </NavigationProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-module')).toHaveTextContent('knowledge-base');
    });
  });
});
