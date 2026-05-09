import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SettingsListWorkbench } from './SettingsListWorkbench';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('SettingsListWorkbench', () => {
  it('renders cards and dialog slot', () => {
    render(
      <SettingsListWorkbench
        items={[{ id: 'one', name: 'Server one' }]}
        getItemKey={(item) => item.id}
        card={(item) => <article>{item.name}</article>}
        dialog={<div>dialog slot</div>}
      />,
    );

    expect(screen.getByText('Server one')).toBeInTheDocument();
    expect(screen.getByText('dialog slot')).toBeInTheDocument();
  });

  it('renders the default empty state through i18n keys', () => {
    render(
      <SettingsListWorkbench
        items={[]}
        getItemKey={(_item, index) => index}
        card={() => null}
      />,
    );

    expect(screen.getByText('workspace.agentSettings.settings.list.empty.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.settings.list.empty.description')).toBeInTheDocument();
  });

  it('does not render a dialog container when the dialog slot is omitted', () => {
    render(
      <SettingsListWorkbench
        items={[{ id: 'one', name: 'Server one' }]}
        getItemKey={(item) => item.id}
        card={(item) => <article>{item.name}</article>}
      />,
    );

    expect(screen.getByText('Server one')).toBeInTheDocument();
    expect(screen.queryByText('dialog slot')).not.toBeInTheDocument();
  });

  it('renders the loading slot when isLoading is true', () => {
    render(
      <SettingsListWorkbench
        items={[]}
        getItemKey={(_item, index) => index}
        card={() => null}
        isLoading
        loading={<div>loading slot</div>}
      />,
    );

    expect(screen.getByText('loading slot')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.settings.list.empty.title')).not.toBeInTheDocument();
  });
});
