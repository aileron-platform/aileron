import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { Bot } from 'lucide-react';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  DocumentEditorDialogCore,
  ensureMarkdownExtension,
  formatDocumentContentSize,
} from './DocumentEditorDialogCore';

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

describe('DocumentEditorDialogCore', () => {
  it('normalizes markdown filenames and content size', () => {
    expect(ensureMarkdownExtension('agent')).toBe('agent.md');
    expect(ensureMarkdownExtension('agent.md')).toBe('agent.md');
    expect(formatDocumentContentSize('')).toBe('1KB');
    expect(formatDocumentContentSize('x'.repeat(1200))).toBe('2KB');
  });

  it('renders shared document fields and submits through the adapter', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());

    render(
      <DocumentEditorDialogCore
        open
        isEdit
        submitting={false}
        icon={Bot}
        title="Edit document"
        description="Document settings"
        showScope
        scopeValue="project"
        scopeOptions={[{ value: 'project', label: 'Project' }]}
        scopeLabel="Scope"
        onScopeChange={vi.fn()}
        fileName="agent.md"
        fileNameLabel="File name"
        fileNamePlaceholder="agent.md"
        fileNameHelper="Use markdown"
        onFileNameChange={vi.fn()}
        content="hello"
        contentLabel="Content"
        contentHelper="Markdown supported"
        contentFooter={<span>1KB</span>}
        onContentChange={vi.fn()}
        cancelLabel="Cancel"
        submitLabel="Save"
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText('Edit document')).toBeInTheDocument();
    expect(screen.getByText('Project')).toBeInTheDocument();
    expect(screen.getByText('Use markdown')).toBeInTheDocument();
    expect(screen.getByText('Markdown supported')).toBeInTheDocument();
    expect(screen.getByText('1KB')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
