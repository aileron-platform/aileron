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
  const i18nKeys = {
    emptyTitle: 'feature.settings.empty.title',
    emptyDescription: 'feature.settings.empty.description',
  };

  it('renders cards and dialog slot', () => {
    render(
      <SettingsListWorkbench
        items={[{ id: 'one', name: 'Server one' }]}
        getItemKey={(item) => item.id}
        card={(item) => <article>{item.name}</article>}
        dialog={<div>dialog slot</div>}
        i18nKeys={i18nKeys}
      />,
    );

    expect(screen.getByText('Server one')).toBeInTheDocument();
    expect(screen.getByText('dialog slot')).toBeInTheDocument();
  });

  it('does not render a dialog container when the dialog slot is omitted', () => {
    render(
      <SettingsListWorkbench
        items={[{ id: 'one', name: 'Server one' }]}
        getItemKey={(item) => item.id}
        card={(item) => <article>{item.name}</article>}
        i18nKeys={i18nKeys}
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
        i18nKeys={i18nKeys}
      />,
    );

    expect(screen.getByText('loading slot')).toBeInTheDocument();
    expect(screen.queryByText(i18nKeys.emptyTitle)).not.toBeInTheDocument();
  });
});
