import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import React from 'react';

import { TemplateInstallDialog } from './TemplateInstallDialog';

const getTemplateCompilePreviewMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'template.common.features.mcp': 'MCP',
        'template.common.features.commands': 'Commands',
        'template.common.features.hooks': 'Hooks',
        'template.common.features.agentsMd': 'AGENTS.md',
        'template.common.features.agents': 'Agents',
        'template.common.features.outputStyle': 'Output Style',
        'template.common.features.scripts': 'Scripts',
        'template.common.features.skills': 'Skills',
        'template.center.install.title': `安裝模板 ${String(params?.name ?? '')}`,
        'template.center.install.description': '安裝描述',
        'template.center.install.workspace.label': '選擇工作區',
        'template.center.install.workspace.placeholder': '請選擇工作區',
        'template.center.install.components.label': '安裝項目',
        'template.center.install.components.selectedCount': `${params?.selected}/${params?.total}`,
        'template.center.install.options.mcp.description': 'MCP 描述',
        'template.center.install.options.commands.description': 'Commands 描述',
        'template.center.install.options.hooks.description': 'Hooks 描述',
        'template.center.install.options.agentsMd.description': 'AGENTS.md 描述',
        'template.center.install.options.agents.description': 'Agents 描述',
        'template.center.install.options.outputStyle.description': 'Output Style 描述',
        'template.center.install.options.scripts.description': 'Scripts 描述',
        'template.center.install.options.skills.description': 'Skills 描述',
        'template.center.install.actions.cancel': '取消',
        'template.center.install.actions.confirm': `安裝到 ${String(params?.workspace ?? '')}`,
        'template.center.install.preview.title': '安裝預覽',
        'template.center.install.preview.summary': `${params?.files} files / ${params?.warnings} warnings / ${params?.unsupported} unsupported / ${params?.degradation} degradation`,
        'template.center.install.preview.target': `目標：${String(params?.target ?? '')}`,
        'template.center.install.preview.loading': '載入編譯預覽中...',
        'template.center.install.preview.none': '沒有額外項目',
        'template.center.install.preview.sections.warnings': 'Warnings',
        'template.center.install.preview.sections.unsupported': 'Unsupported',
        'template.center.install.preview.sections.degradation': 'Degradation',
        'template.common.targets.codex': 'Codex',
        'template.common.targets.gemini': 'Gemini',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/features/template-management/api/templateApi', () => ({
  getTemplateCompilePreview: (...args: unknown[]) => getTemplateCompilePreviewMock(...args),
}));

vi.mock('@/features/template-management/utils/templateSelectors', () => ({
  buildFeatureFlags: () => ({
    hasMcp: true,
    hasCommands: true,
    hasHooks: false,
    hasAgentsMd: true,
    hasAgents: true,
    hasOutputStyle: true,
    hasScripts: false,
    hasSkills: true,
  }),
}));

vi.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h1>{children}</h1>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => (
    <button type="button" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

vi.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/shared/components/ui/select', () => {
  const SelectContent = ({ children }: { children: React.ReactNode }) => <>{children}</>;
  (SelectContent as React.FC).displayName = 'MockSelectContent';

  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value: string;
      onValueChange: (value: string) => void;
      children: React.ReactNode;
    }) => {
      const childArray = React.Children.toArray(children) as React.ReactElement[];
      const contentChild = childArray.find(
        child => React.isValidElement(child) && (child.type as { displayName?: string }).displayName === 'MockSelectContent',
      );

      return (
        <div>
          <label htmlFor="workspace-select">workspace</label>
          <select id="workspace-select" value={value} onChange={(e) => onValueChange(e.target.value)}>
            {contentChild}
          </select>
        </div>
      );
    },
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent,
    SelectItem: ({
      value,
      children,
    }: {
      value: string;
      children: React.ReactNode;
    }) => <option value={value}>{typeof children === 'string' ? children : value}</option>,
  };
});

describe('TemplateInstallDialog', () => {
  it('renders canonical labels and installs selected workspace', async () => {
    getTemplateCompilePreviewMock.mockResolvedValue({
      target: 'gemini',
      files: [{ path: 'GEMINI.md', source: 'agents.md', content: '# agents' }],
      warnings: [{ feature: 'outputStyle', target: 'gemini', message: 'fallback' }],
      unsupported: [],
      degradationNotes: [],
      installHints: {},
    });

    const onInstall = vi.fn();
    const onOpenChange = vi.fn();

    render(
      <TemplateInstallDialog
        open
        template={{
          id: 'tpl-1',
          name: 'Review Template',
          description: '',
          category: 'general',
          version: '1.0.0',
          authorName: '',
          authorEmail: '',
          authorUrl: '',
          cliType: 'codex',
          keywords: [],
          status: 'active',
          documentation: '',
          initCommands: '',
          mcpServers: [],
          commands: [{ id: 'cmd-1', fileName: 'review.md', description: '', content: '# review' }],
          hooks: [],
          agentsMd: '# agents',
          agents: [{ id: 'agent-1', fileName: 'auditor.md', description: '', content: '# agent' }],
          outputStyle: [{ id: 'style-1', fileName: 'concise.md', description: '', content: 'concise' }],
          scripts: [],
          skills: [{ id: 'skill-1', fileName: 'review/SKILL.md', path: 'review/SKILL.md', content: '# skill' }],
          createdAt: '',
          updatedAt: '',
        }}
        workspaces={[
          { id: 'ws-1', name: 'Workspace One', description: 'main workspace', cliType: 'codex' },
          { id: 'ws-2', name: 'Workspace Two', description: '', cliType: 'gemini' },
        ]}
        onOpenChange={onOpenChange}
        onInstall={onInstall}
      />,
    );

    expect(screen.getByText('AGENTS.md')).toBeInTheDocument();
    expect(screen.getByText('Commands')).toBeInTheDocument();
    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('Output Style')).toBeInTheDocument();
    expect(screen.getByText('6/6')).toBeInTheDocument();
    expect(await screen.findByText('安裝預覽')).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('workspace'), 'ws-2');
    expect(await screen.findByText('fallback')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '安裝到 Workspace Two' }));

    expect(onInstall).toHaveBeenCalledWith(
      'ws-2',
      expect.objectContaining({
        mcp: true,
        commands: true,
        agentsMd: true,
        agents: true,
        outputStyle: true,
        skills: true,
      }),
    );
  });
});
