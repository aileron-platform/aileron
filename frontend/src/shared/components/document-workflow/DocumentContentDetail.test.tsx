import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentContentDetail } from './DocumentContentDetail';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange }: { value: string; onChange(value: string): void }) => (
    <textarea aria-label="markdown-editor" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <article>{content}</article>,
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  CodeTextEditor: ({ content, onContentChange }: { content: string; onContentChange(value: string): void }) => (
    <textarea aria-label="code-editor" value={content} onChange={(event) => onContentChange(event.target.value)} />
  ),
}));

describe('DocumentContentDetail', () => {
  it('renders markdown preview before editing', () => {
    render(
      <DocumentContentDetail
        title="review.md"
        content="# Review"
        format="markdown"
        metadata={[{ label: 'Scope', value: 'project' }]}
        onSave={() => undefined}
      />,
    );
    expect(screen.getByText('# Review')).toBeInTheDocument();
    expect(screen.getByText('Scope')).toBeInTheDocument();
    expect(screen.queryByLabelText('markdown-editor')).not.toBeInTheDocument();
  });

  it('supports read-only header actions and an empty preview surface', () => {
    render(
      <DocumentContentDetail
        title="review.md"
        content=""
        format="markdown"
        metadata={[]}
        headerLeading={<span data-testid="document-leading">icon</span>}
        headerActions={<button type="button">download</button>}
        emptyPreview={<p data-testid="document-empty">No content</p>}
        readOnly
        onSave={() => undefined}
      />,
    );

    expect(screen.getByTestId('document-leading')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'download' })).toBeInTheDocument();
    expect(screen.getByTestId('document-empty')).toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'shared.documentWorkflow.detail.actions.edit',
    })).not.toBeInTheDocument();
  });

  it('stages markdown edits and reports dirty state until save', async () => {
    const onDirtyChange = vi.fn();
    const onSave = vi.fn();
    render(
      <DocumentContentDetail
        title="review.md"
        content="# Review"
        format="markdown"
        metadata={[]}
        onDirtyChange={onDirtyChange}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.edit' }));
    fireEvent.change(screen.getByLabelText('markdown-editor'), { target: { value: '# Updated' } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);

    fireEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.save' }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith('# Updated'));
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it('can cancel staged markdown edits', () => {
    const onDirtyChange = vi.fn();
    const onSave = vi.fn();
    render(
      <DocumentContentDetail
        title="review.md"
        content="# Review"
        format="markdown"
        metadata={[]}
        onDirtyChange={onDirtyChange}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.edit' }));
    fireEvent.change(screen.getByLabelText('markdown-editor'), { target: { value: '# Updated' } });
    fireEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.cancel' }));

    expect(onSave).not.toHaveBeenCalled();
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    expect(screen.getByText('# Review')).toBeInTheDocument();
  });

  it('uses the general code editor for TOML edit mode', () => {
    render(
      <DocumentContentDetail
        title="agent.toml"
        content={'name = "agent"'}
        format="toml"
        metadata={[]}
        initialMode="edit"
        onSave={() => undefined}
      />,
    );
    expect(screen.getByLabelText('code-editor')).toBeInTheDocument();
    expect(screen.queryByLabelText('markdown-editor')).not.toBeInTheDocument();
  });
});
