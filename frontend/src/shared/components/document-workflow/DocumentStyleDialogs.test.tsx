import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AgentDefinitionDialog } from '@/features/workspace/features/agent-settings/components/dialogs/AgentDefinitionDialog';
import { AgentCommandDialog } from '@/features/workspace/features/agent-settings/components/dialogs/AgentCommandDialog';
import { WorkspaceOutputStyleDialog } from '@/features/workspace/features/claude-code/components/dialogs/WorkspaceOutputStyleDialog';

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({
    value,
    onChange,
    footerExtras,
  }: {
    value: string;
    onChange: (value: string) => void;
    footerExtras?: React.ReactNode;
  }) => (
    <div>
      <textarea
        aria-label="Markdown content"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {footerExtras}
    </div>
  ),
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea
      aria-label="TOML content"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const map: Record<string, string> = {
        'common.cancel': 'Cancel',
        'workspace.agentSettings.common.documents.scope.values.project': 'Project',
        'workspace.agentSettings.common.documents.scope.values.user': 'User',
        'workspace.agentSettings.common.subagents.dialog.title.create': 'Create agent',
        'workspace.agentSettings.common.subagents.dialog.title.edit': 'Edit agent',
        'workspace.agentSettings.common.subagents.dialog.description.create': 'Create agent description',
        'workspace.agentSettings.common.subagents.dialog.description.edit': 'Edit agent description',
        'workspace.agentSettings.common.subagents.dialog.fields.scope.label': 'Scope',
        'workspace.agentSettings.common.subagents.dialog.fields.fileName.label': 'File name',
        'workspace.agentSettings.common.subagents.dialog.fields.fileName.placeholder': 'agent.md',
        'workspace.agentSettings.common.subagents.dialog.fields.fileName.placeholders.markdown': 'agent.md',
        'workspace.agentSettings.common.subagents.dialog.fields.fileName.placeholders.toml': 'agent.toml',
        'workspace.agentSettings.common.subagents.dialog.fields.name.label': 'Name',
        'workspace.agentSettings.common.subagents.dialog.fields.name.placeholder': 'reviewer',
        'workspace.agentSettings.common.subagents.dialog.fields.tools.label': 'Tools',
        'workspace.agentSettings.common.subagents.dialog.fields.tools.placeholder': 'Read, Grep',
        'workspace.agentSettings.common.subagents.dialog.fields.content.label': 'Content',
        'workspace.agentSettings.common.subagents.dialog.fields.content.labels.markdown': 'Markdown document',
        'workspace.agentSettings.common.subagents.dialog.fields.content.labels.toml': 'TOML document',
        'workspace.agentSettings.common.subagents.dialog.fields.content.helpers.markdown': 'Agent helper',
        'workspace.agentSettings.common.subagents.dialog.fields.content.helpers.toml': 'TOML helper',
        'workspace.agentSettings.common.subagents.dialog.fields.content.placeholders.markdown': 'Markdown placeholder',
        'workspace.agentSettings.common.subagents.dialog.fields.content.placeholders.toml': 'TOML placeholder',
        'workspace.agentSettings.common.subagents.dialog.fields.content.helper': 'Agent helper',
        'workspace.agentSettings.common.subagents.dialog.actions.cancel': 'Cancel',
        'workspace.agentSettings.common.subagents.dialog.actions.create': 'Create',
        'workspace.agentSettings.common.subagents.dialog.actions.save': 'Save',
        'workspace.agentSettings.common.subagents.dialog.validation.fileName': 'File name is required',
        'workspace.agentSettings.common.subagents.dialog.validation.content': 'Content is required',
        'workspace.claudeCode.outputStyles.dialog.title.create': 'Create output style',
        'workspace.claudeCode.outputStyles.dialog.title.edit': 'Edit output style',
        'workspace.claudeCode.outputStyles.dialog.description.create': 'Create output style description',
        'workspace.claudeCode.outputStyles.dialog.description.edit': 'Edit output style description',
        'workspace.claudeCode.outputStyles.dialog.fields.scope.label': 'Scope',
        'workspace.claudeCode.outputStyles.dialog.fields.fileName.label': 'File name',
        'workspace.claudeCode.outputStyles.dialog.fields.fileName.placeholder': 'style.md',
        'workspace.claudeCode.outputStyles.dialog.fields.fileName.helper': 'Workspace style helper',
        'workspace.claudeCode.outputStyles.dialog.fields.content.label': 'Content',
        'workspace.claudeCode.outputStyles.dialog.actions.cancel': 'Cancel',
        'workspace.claudeCode.outputStyles.dialog.actions.create': 'Create',
        'workspace.claudeCode.outputStyles.dialog.actions.save': 'Save',
        'workspace.claudeCode.outputStyles.dialog.validation.fileName': 'File name is required',
        'workspace.claudeCode.outputStyles.dialog.validation.content': 'Content is required',
        'workspace.agentSettings.common.slashCommands.dialog.title.create': 'Create command',
        'workspace.agentSettings.common.slashCommands.dialog.title.edit': 'Edit command',
        'workspace.agentSettings.common.slashCommands.dialog.description.create': 'Create command description',
        'workspace.agentSettings.common.slashCommands.dialog.description.edit': 'Edit command description',
        'workspace.agentSettings.common.slashCommands.dialog.fields.scope.label': 'Scope',
        'workspace.agentSettings.common.slashCommands.dialog.fields.fileName.label': 'File name',
        'workspace.agentSettings.common.slashCommands.dialog.fields.fileName.placeholder': 'command.md',
        'workspace.agentSettings.common.slashCommands.dialog.fields.namespace.label': 'Namespace',
        'workspace.agentSettings.common.slashCommands.dialog.fields.namespace.placeholder': 'ops',
        'workspace.agentSettings.common.slashCommands.dialog.fields.namespace.helper': 'Optional namespace',
        'workspace.agentSettings.common.slashCommands.dialog.fields.content.label': 'Content',
        'workspace.agentSettings.common.slashCommands.dialog.actions.cancel': 'Cancel',
        'workspace.agentSettings.common.slashCommands.dialog.actions.create': 'Create',
        'workspace.agentSettings.common.slashCommands.dialog.actions.save': 'Save',
        'workspace.agentSettings.common.slashCommands.dialog.validation.fileName': 'File name is required',
        'workspace.agentSettings.common.slashCommands.dialog.validation.content': 'Content is required',
      };

      if (key.endsWith('.estimatedSize') || key.endsWith('.sizeHint')) {
        return `Size ${options?.size ?? ''}`;
      }

      return map[key] ?? key;
    },
  }),
}));

describe('document-style shared dialogs', () => {
  it('preserves workspace agent submit payload after core extraction', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AgentDefinitionDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('agent.md'), 'researcher');
    await user.type(screen.getByLabelText('Markdown content'), 'Use sources');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      id: 'project:researcher.md',
      title: 'researcher.md',
      scope: 'project',
      content: 'Use sources',
      size: '1KB',
      metadata: { fileName: 'researcher.md' },
    }));
  });

  it('submits subagent source document content without metadata fields', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AgentDefinitionDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('agent.md'), 'reviewer.md');
    await user.type(screen.getByLabelText('Markdown content'), '---\nname: reviewer\ndescription: Reviews code\n---\n\nReview carefully');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      title: 'reviewer.md',
      content: '---\nname: reviewer\ndescription: Reviews code\n---\n\nReview carefully',
    }));
  });

  it('preserves workspace output-style submit payload after owner split', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <WorkspaceOutputStyleDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('style.md'), 'minimal');
    await user.type(screen.getByLabelText('Markdown content'), 'Short answers');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      id: 'project:minimal.md',
      title: 'minimal.md',
      scope: 'project',
      content: 'Short answers',
      size: '1KB',
      metadata: { fileName: 'minimal.md' },
    }));
  });

  it('preserves workspace command submit payload after owner split', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AgentCommandDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('command.md'), 'deploy');
    await user.type(screen.getByPlaceholderText('ops'), 'ops');
    await user.type(screen.getByLabelText('Markdown content'), 'Deploy service');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      id: 'project:deploy.md',
      title: 'deploy.md',
      scope: 'project',
      content: 'Deploy service',
      size: '1KB',
      metadata: {
        fileName: 'deploy.md',
        namespace: 'ops',
        format: 'markdown',
      },
    }));
  });

});
