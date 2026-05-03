import React from 'react';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CodexRulesPage, { isValidCodexRulesPath } from './CodexRulesPage';

const apiMock = {
  listCodexRules: vi.fn(),
  getCodexRulesFile: vi.fn(),
  updateCodexRulesFile: vi.fn(),
  deleteCodexRulesFile: vi.fn(),
  validateCodexRulesFile: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.count !== undefined) return `${key}:${String(params.count)}`;
      if (params?.exitCode !== undefined) return `${key}:${String(params.exitCode)}`;
      if (params?.fileName !== undefined) return `${key}:${String(params.fileName)}`;
      if (params?.title !== undefined) return `${key}:${String(params.title)}`;
      if (params?.size !== undefined) return `${key}:${String(params.size)}`;
      return key;
    },
  }),
}));

vi.mock('@/shared/components/monaco/LocalizedMonacoEditor', () => ({
  LocalizedMonacoEditor: ({
    language,
    value,
    onChange,
  }: {
    language: string;
    value: string;
    onChange: (value: string | undefined) => void;
  }) => (
    <textarea
      aria-label={`monaco-${language}`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
}));

vi.mock('@/shared/components/ui/select', () => ({
  Select: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div>{children}</div>,
  SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <div data-value={value}>{children}</div>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectValue: () => null,
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('CodexRulesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiMock.listCodexRules.mockResolvedValue({ files: [] });
    apiMock.getCodexRulesFile.mockResolvedValue({
      content: 'prefix_rule(pattern = ["git"], decision = "allow")',
      exists: true,
    });
    apiMock.updateCodexRulesFile.mockResolvedValue({
      content: 'prefix_rule(pattern = ["git"], decision = "allow")',
      exists: true,
    });
    apiMock.deleteCodexRulesFile.mockResolvedValue(undefined);
    apiMock.validateCodexRulesFile.mockResolvedValue({
      valid: true,
      exitCode: 0,
      stdout: 'allow',
      stderr: '',
    });
  });

  it('renders rules in the document workflow and loads the selected file', async () => {
    apiMock.listCodexRules
      .mockResolvedValueOnce({
        files: [{ name: 'project.rules', path: 'project.rules', sizeBytes: 54 }],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.getCodexRulesFile.mockResolvedValue({
      content: 'prefix_rule(pattern = ["git"], decision = "allow")',
      exists: true,
    });

    render(<CodexRulesPage />);

    expect(await screen.findByText('workspace.agentSettings.codex.rules.title')).toBeInTheDocument();
    expect(screen.getByText('project.rules')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.rules.actions.create')).toBeInTheDocument();
    await waitFor(() => expect(apiMock.getCodexRulesFile).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      'project.rules',
    ));
  });

  it('reselects an available rules file when the external selection is stale', async () => {
    const onSelect = vi.fn();
    apiMock.listCodexRules
      .mockResolvedValueOnce({
        files: [{ name: 'default.rules', path: 'default.rules', sizeBytes: 8 }],
      })
      .mockResolvedValueOnce({ files: [] });

    render(
      <CodexRulesPage
        selectedId="project:missing.rules"
        onSelect={onSelect}
      />,
    );

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:default.rules'));
  });

  it('validates the selected rules file and displays stdout', async () => {
    apiMock.listCodexRules
      .mockResolvedValueOnce({
        files: [{ name: 'default.rules', path: 'default.rules', sizeBytes: 8 }],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.validateCodexRulesFile.mockResolvedValue({
      valid: true,
      exitCode: 0,
      stdout: 'decision allow',
      stderr: '',
    });

    render(<CodexRulesPage />);

    await screen.findByText('default.rules');
    fireEvent.click(screen.getAllByText('workspace.agentSettings.codex.rules.actions.validate')[0]);
    fireEvent.click(await screen.findByText('workspace.agentSettings.codex.rules.validationDialog.actions.validate'));

    await waitFor(() => expect(apiMock.validateCodexRulesFile).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      'default.rules',
      ['git', 'status'],
    ));
    expect(await screen.findByText('workspace.agentSettings.codex.rules.validation.valid:0')).toBeInTheDocument();
    expect(screen.getByText('decision allow')).toBeInTheDocument();
  });

  it('rejects invalid rules paths before save', () => {
    expect(isValidCodexRulesPath('default.rules')).toBe(true);
    expect(isValidCodexRulesPath('/default.rules')).toBe(false);
    expect(isValidCodexRulesPath('../default.rules')).toBe(false);
    expect(isValidCodexRulesPath('default.txt')).toBe(false);
  });
});
