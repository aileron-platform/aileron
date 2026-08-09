import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Wrench } from 'lucide-react';
import { SettingsWorkflowShell } from './SettingsWorkflowShell';

describe('SettingsWorkflowShell', () => {
  it('\u5728\u6c92\u6709\u9805\u76ee\u6642\u986f\u793a empty state', () => {
    render(
      <SettingsWorkflowShell
        title="Hooks"
        icon={Wrench}
        hasItems={false}
        emptyTitle="No hooks"
        emptyDescription="Create your first hook"
      />
    );

    expect(screen.getByText('No hooks')).toBeInTheDocument();
    expect(screen.getByText('Create your first hook')).toBeInTheDocument();
  });

  it('\u5728\u6709\u9805\u76ee\u6642\u986f\u793a\u4e3b header summary、controls \u8207\u5167\u5bb9', () => {
    render(
      <SettingsWorkflowShell
        title="MCP"
        icon={Wrench}
        hasItems
        summary={<div>2 items</div>}
        controls={<button type="button">Search</button>}
        emptyTitle="unused"
        emptyDescription="unused"
      >
        <div>Server A</div>
      </SettingsWorkflowShell>
    );

    expect(screen.getByRole('heading', { name: 'MCP' })).toBeInTheDocument();
    expect(screen.getAllByText('MCP')).toHaveLength(1);
    expect(screen.getByText('2 items')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
    expect(screen.getByText('Server A')).toBeInTheDocument();
  });

  it('summary \u6703\u6574\u5408\u9032\u4e3b header \u4e26\u96b1\u85cf\u6c92\u6709 controls \u7684\u6b21\u7d1a toolbar', () => {
    render(
      <SettingsWorkflowShell
        title="Hooks"
        icon={Wrench}
        hasItems
        summary={<div>3 items</div>}
        emptyTitle="unused"
        emptyDescription="unused"
      >
        <div>Hook A</div>
      </SettingsWorkflowShell>
    );

    expect(screen.getByText('3 items')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Hooks' })).toBeInTheDocument();
    expect(screen.getAllByText('Hooks')).toHaveLength(1);
  });
});
