import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentMetadataDialog } from './DocumentMetadataDialog';
import type { DocumentMetadataValue } from './documentMetadata';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe('DocumentMetadataDialog', () => {
  it('renders metadata fields without a markdown editor in create mode', () => {
    render(
      <DocumentMetadataDialog
        open
        mode="create"
        titleKey="title"
        descriptionKey="description"
        value={{ fileName: '', scope: 'project' }}
        capabilities={{ scope: true, namespace: true }}
        scopeOptions={[{ value: 'project', labelKey: 'scope.project' }]}
        onChange={() => undefined}
        onClose={() => undefined}
        onSubmit={() => undefined}
      />,
    );
    expect(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.documentWorkflow.metadata.namespace.label')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: /content/i })).not.toBeInTheDocument();
  });

  it('hides namespace when unsupported', () => {
    render(
      <DocumentMetadataDialog
        open
        mode="create"
        titleKey="title"
        descriptionKey="description"
        value={{ fileName: 'a.md' }}
        capabilities={{ scope: false, namespace: false }}
        scopeOptions={[]}
        onChange={() => undefined}
        onClose={() => undefined}
        onSubmit={() => undefined}
      />,
    );
    expect(screen.queryByLabelText('shared.documentWorkflow.metadata.namespace.label')).not.toBeInTheDocument();
  });

  it('hides scope when unsupported as a regression guard', () => {
    render(
      <DocumentMetadataDialog
        open
        mode="create"
        titleKey="title"
        descriptionKey="description"
        value={{ fileName: 'a.md', scope: 'project' }}
        capabilities={{ scope: false, namespace: true }}
        scopeOptions={[{ value: 'project', labelKey: 'scope.project' }]}
        onChange={() => undefined}
        onClose={() => undefined}
        onSubmit={() => undefined}
      />,
    );
    expect(screen.queryByLabelText('shared.documentWorkflow.metadata.scope.label')).not.toBeInTheDocument();
    expect(screen.getByLabelText('shared.documentWorkflow.metadata.namespace.label')).toBeInTheDocument();
  });

  it('submits the current metadata value', () => {
    const onSubmit = vi.fn();
    const StatefulDialog = () => {
      const [value, setValue] = React.useState<DocumentMetadataValue>({
        fileName: 'old.md',
        scope: 'project',
        path: 'team/old.md',
      });
      return (
        <DocumentMetadataDialog
          open
          mode="rename"
          titleKey="title"
          descriptionKey="description"
          value={value}
          capabilities={{ scope: true, namespace: false }}
          scopeOptions={[{ value: 'project', labelKey: 'scope.project' }]}
          onChange={setValue}
          onClose={() => undefined}
          onSubmit={onSubmit}
        />
      );
    };
    render(<StatefulDialog />);
    fireEvent.change(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), {
      target: { value: 'new.md' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ fileName: 'new.md' }));
  });

  it('disables actions while submitting', () => {
    render(
      <DocumentMetadataDialog
        open
        mode="create"
        titleKey="title"
        descriptionKey="description"
        value={{ fileName: 'busy.md', scope: 'project' }}
        capabilities={{ scope: true, namespace: false }}
        scopeOptions={[{ value: 'project', labelKey: 'scope.project' }]}
        submitting
        onChange={() => undefined}
        onClose={() => undefined}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.cancel' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' })).toBeDisabled();
  });
});
