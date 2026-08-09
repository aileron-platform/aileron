import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SettingsModelSelectionSection } from './SettingsModelSelectionSection';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const baseValue = {
  customModels: [],
  availableModels: ['gpt-5.6-sol', 'gpt-5.6-terra'],
  allowedModels: ['gpt-5.6-sol'],
  defaultModel: 'gpt-5.6-sol',
};

describe('SettingsModelSelectionSection', () => {
  it('renders model controls without a nested card container', () => {
    const { container } = render(
      <SettingsModelSelectionSection
        value={baseValue}
        onChange={vi.fn()}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    expect(screen.getByText('pages.settings.sections.codex.models.title')).toBeInTheDocument();
    expect(container.querySelector('.bg-card')).not.toBeInTheDocument();
  });

  it('adds a custom model as allowed and available', async () => {
    const onChange = vi.fn();
    render(
      <SettingsModelSelectionSection
        value={baseValue}
        onChange={onChange}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    await userEvent.type(screen.getByRole('textbox'), 'gpt-custom');
    await userEvent.click(screen.getByRole('button', { name: 'pages.settings.sections.codex.models.addButton' }));

    expect(onChange).toHaveBeenCalledWith({
      customModels: ['gpt-custom'],
      availableModels: ['gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-custom'],
      allowedModels: ['gpt-5.6-sol', 'gpt-custom'],
      defaultModel: 'gpt-5.6-sol',
    });
  });

  it('does not add an existing global model as custom', async () => {
    const onChange = vi.fn();
    render(
      <SettingsModelSelectionSection
        value={baseValue}
        onChange={onChange}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    await userEvent.type(screen.getByRole('textbox'), ' gpt-5.6-sol ');
    await userEvent.click(screen.getByRole('button', { name: 'pages.settings.sections.codex.models.addButton' }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'gpt-5.6-sol' })).not.toBeInTheDocument();
  });

  it('blocks removing the last allowed custom model', async () => {
    const onChange = vi.fn();
    render(
      <SettingsModelSelectionSection
        value={{
          customModels: ['gpt-custom'],
          availableModels: ['gpt-5.6-sol', 'gpt-custom'],
          allowedModels: ['gpt-custom'],
          defaultModel: 'gpt-custom',
        }}
        onChange={onChange}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'gpt-custom' }));

    expect(onChange).not.toHaveBeenCalledWith(expect.objectContaining({ allowedModels: [] }));
  });

  it('removes an allowed custom model and updates the default', async () => {
    const onChange = vi.fn();
    render(
      <SettingsModelSelectionSection
        value={{
          customModels: ['gpt-custom'],
          availableModels: ['gpt-5.6-sol', 'gpt-custom'],
          allowedModels: ['gpt-5.6-sol', 'gpt-custom'],
          defaultModel: 'gpt-custom',
        }}
        onChange={onChange}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'gpt-custom' }));

    expect(onChange).toHaveBeenCalledWith({
      customModels: [],
      availableModels: ['gpt-5.6-sol'],
      allowedModels: ['gpt-5.6-sol'],
      defaultModel: 'gpt-5.6-sol',
    });
  });

  it('moves default model when current default is disabled', async () => {
    const onChange = vi.fn();
    render(
      <SettingsModelSelectionSection
        value={{
          ...baseValue,
          allowedModels: ['gpt-5.6-sol', 'gpt-5.6-terra'],
          defaultModel: 'gpt-5.6-sol',
        }}
        onChange={onChange}
        i18nPrefix="pages.settings.sections.codex.models"
      />,
    );

    await userEvent.click(screen.getByRole('checkbox', { name: 'gpt-5.6-sol' }));

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      allowedModels: ['gpt-5.6-terra'],
      defaultModel: 'gpt-5.6-terra',
    }));
  });
});
