import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { BasicInfoStep } from './BasicInfoStep';
import type { BasicInfoForm } from '../../types';

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
  'workspace.wizard.steps.basicInfo.fields.gitUrl.label': 'Git repository URL',
  'workspace.wizard.steps.basicInfo.fields.gitUrl.placeholder': 'https://github.com/org/repo.git',
  'workspace.wizard.steps.basicInfo.fields.gitUrl.helper': 'Leave blank to start fresh.',
  'workspace.wizard.steps.basicInfo.fields.gitUrl.fetchBranches': 'Fetch branches',
  'workspace.wizard.steps.basicInfo.fields.gitUrl.errors.empty': 'Enter a Git repository URL first.',
  'workspace.wizard.steps.basicInfo.fields.gitUrl.errors.fetchFailed': 'We could not load branches.',
  'workspace.wizard.steps.basicInfo.fields.branch.label': 'Branch',
  'workspace.wizard.steps.basicInfo.fields.branch.placeholder': 'Select a branch',
  'workspace.wizard.steps.basicInfo.fields.branch.helper': 'Branches fetched from the repository.',
  'workspace.wizard.steps.basicInfo.fields.cliType.label': 'CLI type',
  'workspace.wizard.steps.basicInfo.fields.cliType.helper': 'This cannot be changed after creation.',
  'workspace.wizard.steps.basicInfo.fields.cliType.options.claudeCode': 'Claude Code',
  'workspace.wizard.steps.basicInfo.fields.cliType.options.codex': 'Codex',
  'workspace.wizard.steps.basicInfo.fields.cliType.options.gemini': 'Gemini',
  'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.claudeCode': 'Use Claude Code sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.codex': 'Use Codex sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.cliType.descriptions.gemini': 'Use Gemini sessions and compatible marketplace packages.',
  'workspace.wizard.steps.basicInfo.fields.cliType.selected': 'Selected',
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
    gitUrl: '',
    branch: '',
    cliType: 'claude-code',
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
  it('renders CLI choices as icon cards and updates the selected CLI', async () => {
    const user = userEvent.setup();
    const { data, onChange } = renderStep();

    const codexCard = screen.getByRole('button', { name: /Codex/ });

    expect(screen.getByRole('button', { name: /Claude Code/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/claude-code.png');
    expect(screen.getByRole('button', { name: /Codex/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/codex.png');
    expect(screen.getByRole('button', { name: /Gemini/ }).querySelector('img'))
      .toHaveAttribute('src', '/marketplace/providers/gemini.svg');
    expect(screen.queryByRole('combobox', { name: 'CLI type' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Claude Code/ })).toHaveAttribute('aria-pressed', 'true');

    await user.click(codexCard);

    expect(onChange).toHaveBeenCalledWith({ ...data, cliType: 'codex' });
  });
});
