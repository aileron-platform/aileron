import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import BasicInfoStep from './BasicInfoStep';
import type { BasicInfoForm } from '../../model/workspaceWizardTypes';

const translations: Record<string, string> = {
  'workspace.wizard.steps.basicInfo.title': 'Create a new workspace',
  'workspace.wizard.steps.basicInfo.subtitle': 'Step {{current}}/{{total}}: Provide basic information',
  'workspace.wizard.steps.basicInfo.cardTitle': 'Project details',
  'workspace.wizard.steps.basicInfo.cardDescription': 'Project details description',
  'workspace.wizard.steps.basicInfo.fields.name.label': 'Project name',
  'workspace.wizard.steps.basicInfo.fields.name.placeholder': 'Enter a project name',
  'workspace.wizard.steps.basicInfo.fields.name.helper': 'Used as the workspace display name.',
  'workspace.wizard.steps.basicInfo.fields.description.label': 'Project description',
  'workspace.wizard.steps.basicInfo.fields.description.placeholder': 'Summarise the goal',
  'workspace.wizard.steps.basicInfo.fields.description.helper': 'Give teammates context.',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.label': 'Agent tool',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.helper': 'This cannot be changed after creation.',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.options.claudeCode': 'Claude Code',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.options.codex': 'Codex',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.options.opencode': 'OpenCode',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.claudeCode': 'Use Claude Code sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.codex': 'Use Codex sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.descriptions.opencode': 'Use OpenCode ACP sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.agenticTool.selected': 'Selected',
  'workspace.wizard.validation.basicInfo': 'Please complete all required fields before continuing.',
  'workspace.wizard.buttons.cancel': 'Cancel',
  'workspace.wizard.buttons.next': 'Next',
  'workspace.wizard.buttons.processing': 'Processing...',
};

const t = (key: string, params?: Record<string, string | number>) => {
  let value = translations[key] ?? key;
  Object.entries(params ?? {}).forEach(([param, replacement]) => {
    value = value.replace(`{{${param}}}`, String(replacement));
  });
  return value;
};

const renderStep = (overrides: Partial<BasicInfoForm> = {}) => {
  const data: BasicInfoForm = {
    name: 'Workspace',
    description: 'Workspace description',
    agenticTools: ['claude-code'],
    ...overrides,
  };
  const onChange = vi.fn();

  render(
    <BasicInfoStep
      data={data}
      onChange={onChange}
      onCancel={vi.fn()}
      onSubmit={vi.fn()}
      isSubmitting={false}
      t={t}
    />
  );

  return { data, onChange };
};

describe('BasicInfoStep', () => {
  it('creates a workspace without collecting Git repository settings', () => {
    renderStep();

    expect(screen.getByText('Step 1/3: Provide basic information')).toBeInTheDocument();
    expect(screen.queryByLabelText('Git repository URL')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Branch')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Fetch branches')).not.toBeInTheDocument();
  });

  it('renders agent tool choices as icon cards and updates the selected tool', async () => {
    const user = userEvent.setup();
    const { data, onChange } = renderStep();

    const codexCard = screen.getByRole('button', { name: /Codex/ });

    expect(screen.getByRole('button', { name: /Claude Code/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/claude-code.png');
    expect(screen.getByRole('button', { name: /Codex/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/codex.png');
    expect(screen.getByRole('button', { name: /OpenCode/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/opencode.png');
    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(2);
    expect(screen.queryByRole('combobox', { name: 'Agent tool' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Claude Code/ })).toHaveAttribute('aria-pressed', 'true');

    await user.click(codexCard);

    expect(onChange).toHaveBeenCalledWith({ ...data, agenticTools: ['claude-code', 'codex'] });
  });

  it('allows selecting OpenCode as an agent tool', async () => {
    const user = userEvent.setup();
    const { data, onChange } = renderStep();

    await user.click(screen.getByRole('button', { name: /OpenCode/ }));

    expect(onChange).toHaveBeenCalledWith({ ...data, agenticTools: ['claude-code', 'opencode'] });
  });

  it('does not allow removing the last selected agent tool', async () => {
    const user = userEvent.setup();
    const { onChange } = renderStep();

    await user.click(screen.getByRole('button', { name: /Claude Code/ }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
