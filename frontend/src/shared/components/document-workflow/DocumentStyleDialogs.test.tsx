import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { TemplateAgentDialog } from '@/features/template-management/features/template-editor/components/TemplateAgentDialog';
import { TemplateCommandDialog } from '@/features/template-management/features/template-editor/components/TemplateCommandDialog';
import { TemplateOutputStyleDialog } from '@/features/template-management/features/template-editor/components/TemplateOutputStyleDialog';
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
        'workspace.agentSettings.common.slashCommands.dialog.tabs.basic': 'Basic',
        'workspace.agentSettings.common.slashCommands.dialog.tabs.editor': 'Editor',
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
        'template.editor.commands.dialog.title.create': 'Create template command',
        'template.editor.commands.dialog.title.edit': 'Edit template command',
        'template.editor.commands.dialog.description.create': 'Create template command description',
        'template.editor.commands.dialog.description.edit': 'Edit template command description',
        'template.editor.commands.dialog.fields.name.label': 'Name',
        'template.editor.commands.dialog.fields.name.placeholder': 'deploy',
        'template.editor.commands.dialog.fields.name.helper': 'Command name',
        'template.editor.commands.dialog.fields.namespace.label': 'Namespace',
        'template.editor.commands.dialog.fields.namespace.placeholder': 'ops',
        'template.editor.commands.dialog.fields.namespace.helper': 'Optional namespace',
        'template.editor.commands.dialog.fields.content.label': 'Content',
        'template.editor.commands.dialog.actions.create': 'Create',
        'template.editor.commands.dialog.actions.save': 'Save',
        'template.editor.commands.dialog.validation.nameRequired': 'Name is required',
        'template.editor.commands.dialog.validation.contentRequired': 'Content is required',
        'template.editor.outputStyle.dialog.title.create': 'Create template output style',
        'template.editor.outputStyle.dialog.title.edit': 'Edit template output style',
        'template.editor.outputStyle.dialog.description.create': 'Create template output style description',
        'template.editor.outputStyle.dialog.description.edit': 'Edit template output style description',
        'template.editor.outputStyle.dialog.fields.fileName.label': 'File name',
        'template.editor.outputStyle.dialog.fields.fileName.placeholder': 'style.md',
        'template.editor.outputStyle.dialog.fields.fileName.helper': 'Template style helper',
        'template.editor.outputStyle.dialog.fields.content.label': 'Content',
        'template.editor.outputStyle.dialog.actions.cancel': 'Cancel',
        'template.editor.outputStyle.dialog.actions.create': 'Create',
        'template.editor.outputStyle.dialog.actions.update': 'Update',
        'template.editor.outputStyle.dialog.actions.submitting': 'Saving',
        'template.editor.outputStyle.dialog.validation.fileName': 'File name is required',
        'template.editor.outputStyle.dialog.validation.content': 'Content is required',
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

  it('preserves template agent submit payload after owner split', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <TemplateAgentDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('template.editor.agents.dialog.fields.fileName.placeholder'), 'reviewer');
    await user.type(screen.getByLabelText('Markdown content'), 'Review carefully');
    await user.click(screen.getByRole('button', { name: 'template.editor.agents.dialog.actions.create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      fileName: 'reviewer.md',
      content: 'Review carefully',
      description: '',
    }));
  });

  it('preserves template output-style submit payload after core extraction', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <TemplateOutputStyleDialog
        open
        mode="edit"
        initialValue={{
          localId: 'style-1',
          fileName: 'brief.md',
          content: '',
          description: '',
        }}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText('Markdown content'), 'Be concise');
    await user.click(screen.getByRole('button', { name: 'Update' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      localId: 'style-1',
      fileName: 'brief.md',
      content: 'Be concise',
      description: '',
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
    await user.click(screen.getByRole('tab', { name: 'Editor' }));
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
        namespace: undefined,
        format: 'markdown',
      },
    }));
  });

  it('preserves template command namespace payload after owner split', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <TemplateCommandDialog
        open
        mode="create"
        initialValue={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByPlaceholderText('deploy'), 'release');
    await user.type(screen.getByPlaceholderText('ops'), 'ops');
    await user.type(screen.getByLabelText('Markdown content'), 'Run release');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      fileName: 'ops/release.md',
      content: 'Run release',
    }));
  });
});
