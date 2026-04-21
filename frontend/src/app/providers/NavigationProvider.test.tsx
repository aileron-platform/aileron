import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { NavigationProvider, useNavigation } from './NavigationProvider';

const ModuleProbe = () => {
  const { state } = useNavigation();

  return <div data-testid="current-module">{state.currentModule}</div>;
};

describe('NavigationProvider', () => {
  it('treats templates root paths as the template module', async () => {
    render(
      <MemoryRouter initialEntries={['/templates/templates']}>
        <NavigationProvider>
          <ModuleProbe />
        </NavigationProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-module')).toHaveTextContent('template');
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
