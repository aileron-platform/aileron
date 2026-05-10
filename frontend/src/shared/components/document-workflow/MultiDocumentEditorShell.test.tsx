import React from 'react';
import { FileText } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';

import { MultiDocumentEditorShell } from './MultiDocumentEditorShell';

describe('MultiDocumentEditorShell', () => {
  it('renders sidebar, header actions, and the main area', () => {
    render(
      <MultiDocumentEditorShell
        title="shared.documentWorkflow.shell.title"
        icon={FileText}
        sidebar={<div>sidebar-slot</div>}
        headerActions={<button type="button">shared.documentWorkflow.shell.actions.save</button>}
        mainArea={<div>main-slot</div>}
        labels={{ loading: 'shared.documentWorkflow.shell.loading' }}
      />,
    );

    expect(screen.getByText('shared.documentWorkflow.shell.title')).toBeInTheDocument();
    expect(screen.getByText('shared.documentWorkflow.shell.actions.save')).toBeInTheDocument();
    expect(screen.getByText('sidebar-slot')).toBeInTheDocument();
    expect(screen.getByText('main-slot')).toBeInTheDocument();
  });

  it('can hide the sidebar and show the empty state', () => {
    render(
      <MultiDocumentEditorShell
        title="shared.documentWorkflow.shell.title"
        icon={FileText}
        emptyState={<div>empty-slot</div>}
        mainArea={<div>main-slot</div>}
        labels={{ loading: 'shared.documentWorkflow.shell.loading' }}
      />,
    );

    expect(screen.queryByText('sidebar-slot')).not.toBeInTheDocument();
    expect(screen.getByText('empty-slot')).toBeInTheDocument();
    expect(screen.queryByText('main-slot')).not.toBeInTheDocument();
  });

  it('renders the loading state instead of the main area', () => {
    render(
      <MultiDocumentEditorShell
        title="shared.documentWorkflow.shell.title"
        icon={FileText}
        sidebar={<div>sidebar-slot</div>}
        isLoading
        mainArea={<div>main-slot</div>}
        labels={{ loading: 'shared.documentWorkflow.shell.loading' }}
      />,
    );

    expect(screen.getByText('shared.documentWorkflow.shell.loading')).toBeInTheDocument();
    expect(screen.queryByText('main-slot')).not.toBeInTheDocument();
  });
});
