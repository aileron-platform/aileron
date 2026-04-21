import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Wrench } from 'lucide-react';
import { SettingsWorkflowShell } from './SettingsWorkflowShell';

describe('SettingsWorkflowShell', () => {
  it('在沒有項目時顯示 empty state', () => {
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

  it('在有項目時顯示 summary、controls 與內容', () => {
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

    expect(screen.getByText('2 items')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
    expect(screen.getByText('Server A')).toBeInTheDocument();
  });

  it('singleHeader 模式會把 summary 整合進主 header 並隱藏次級 toolbar', () => {
    render(
      <SettingsWorkflowShell
        title="Hooks"
        icon={Wrench}
        hasItems
        singleHeader
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
