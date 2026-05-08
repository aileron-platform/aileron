import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceDetailView } from './MarketplaceDetailView';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  CodeTextEditor: ({ content, fileName }: { content: string; fileName: string }) => (
    <textarea aria-label={fileName} readOnly value={content} />
  ),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const mockDetail: MarketplacePackageDetail = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  version: '0.1.0',
  description: 'Review workflow helpers.',
  category: 'coding',
  tags: ['skill'],
  sourceType: 'created',
  indexedResourceNames: ['skills/review/config.toml'],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/review-tools',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  catalogMetadata: {},
  manifestMetadata: {},
  readmeMarkdown: '# Review Tools',
  featureContent: {
    agentsMd: '# AGENTS.md',
    hooks: [],
    mcpServers: [],
    agents: [],
    commands: [],
    outputStyles: [],
    skills: [
      {
        id: 'review-config',
        name: 'Review Config',
        path: 'skills/review/config.toml',
        content: 'description = "Review config"',
      },
    ],
  },
  packageFiles: [],
  validationResults: [],
  activity: [],
};

const mockGetPackage = vi.fn();
const mockDeletePackage = vi.fn();
const mockInstallPackage = vi.fn();
const mockExportPackage = vi.fn();
const mockGetInstallPreflight = vi.fn();

vi.mock('../../api/marketplaceApi', () => ({
  getPackage: (...args: unknown[]) => mockGetPackage(...args),
  getInstallPreflight: (...args: unknown[]) => mockGetInstallPreflight(...args),
  installPackage: (...args: unknown[]) => mockInstallPackage(...args),
  exportPackage: (...args: unknown[]) => mockExportPackage(...args),
  deletePackage: (...args: unknown[]) => mockDeletePackage(...args),
}));

vi.mock('@/features/workspace/services/workspaceRuntimeApi', () => ({
  fetchWorkspaceList: vi.fn(async () => ({
    items: [{ id: 'ws-1', name: 'Workspace One' }],
  })),
}));

const renderDetail = () => render(
  <MemoryRouter initialEntries={['/marketplace/packages/codex/review-tools']}>
    <Routes>
      <Route path="/marketplace/packages/:provider/:packageId" element={<MarketplaceDetailView />} />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceDetailView', () => {
  beforeEach(() => {
    mockGetPackage.mockReset();
    mockDeletePackage.mockReset();
    mockInstallPackage.mockReset();
    mockExportPackage.mockReset();
    mockGetInstallPreflight.mockReset();
    mockGetPackage.mockResolvedValue(mockDetail);
    mockGetInstallPreflight.mockResolvedValue({
      provider: 'codex',
      available: true,
      version: '1.2.3',
      capabilities: {
        supportsUserScope: true,
        supportsMarketplaceAdd: true,
        supportsExtensionInstall: false,
      },
    });
    mockDeletePackage.mockResolvedValue({ deleted: true });
    mockInstallPackage.mockResolvedValue({
      status: 'success',
      provider: 'codex',
      packageId: 'review-tools',
      workspaceId: 'ws-1',
      stdout: 'installed review-tools',
    });
    mockExportPackage.mockResolvedValue({ archiveName: 'review-tools.zip' });
  });

  it('renders TOML skill content through the shared code editor preview', async () => {
    const user = userEvent.setup();
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: /marketplace\.features\.skills/ }));

    expect(screen.getByLabelText('config.toml')).toHaveValue('description = "Review config"');
    const refreshButton = screen.getByRole('button', { name: 'marketplace.detail.viewer.refresh' });
    const collapseButton = screen.getByRole('button', { name: 'marketplace.detail.viewer.collapseSidebar' });
    expect(refreshButton.compareDocumentPosition(collapseButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    await user.click(collapseButton);
    expect(screen.getByRole('button', { name: 'marketplace.detail.viewer.expandSidebar' })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('marketplace.editor.fileManager.search.placeholder')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.detail.viewer.expandSidebar' }));
    expect(screen.getByPlaceholderText('marketplace.editor.fileManager.search.placeholder')).toBeInTheDocument();
    const resizeHandle = screen.getByRole('separator', { name: 'marketplace.detail.viewer.resizeSidebar' });
    fireEvent.mouseDown(resizeHandle, { clientX: 320 });
    fireEvent.mouseMove(window, { clientX: 420 });
    fireEvent.mouseUp(window);
    expect(resizeHandle.parentElement).toHaveStyle({ width: '420px' });
  });

  it('blocks destructive delete until the package id confirmation matches', async () => {
    const user = userEvent.setup();
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.delete' }));

    const confirmDelete = screen.getByRole('button', { name: 'marketplace.delete.actions.delete' });
    expect(confirmDelete).toBeDisabled();

    await user.type(screen.getByLabelText('marketplace.delete.fields.confirm'), 'wrong-id');
    expect(confirmDelete).toBeDisabled();

    await user.clear(screen.getByLabelText('marketplace.delete.fields.confirm'));
    await user.type(screen.getByLabelText('marketplace.delete.fields.confirm'), 'review-tools');
    await user.click(confirmDelete);

    await waitFor(() => {
      expect(mockDeletePackage).toHaveBeenCalledWith({
        provider: 'codex',
        packageId: 'review-tools',
        revision: 'rev-1',
      });
    });
    expect(await screen.findByText('marketplace-center-route')).toBeInTheDocument();
  });

  it('installs a package into the selected workspace and shows command output', async () => {
    const user = userEvent.setup();
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.install' }));
    expect(await screen.findByText('marketplace.install.preflight.ready')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.install.actions.install' }));

    await waitFor(() => {
      expect(mockGetInstallPreflight).toHaveBeenCalledWith('codex', 'ws-1');
      expect(mockInstallPackage).toHaveBeenCalledWith({
        provider: 'codex',
        packageId: 'review-tools',
        revision: 'rev-1',
        workspaceId: 'ws-1',
      });
    });
    expect(screen.getByText('marketplace.install.result.success')).toBeInTheDocument();
    expect(screen.getByText('installed review-tools')).toBeInTheDocument();
  });

  it('exports a package and shows the ready state', async () => {
    const user = userEvent.setup();
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.export' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.export.actions.export' }));

    await waitFor(() => {
      expect(mockExportPackage).toHaveBeenCalledWith({
        provider: 'codex',
        packageId: 'review-tools',
        revision: 'rev-1',
      });
    });
    expect(screen.getByText('marketplace.export.result.ready')).toBeInTheDocument();
  });

  it('shows the localized not-found state and returns to the center route', async () => {
    const user = userEvent.setup();
    mockGetPackage.mockRejectedValue(new Error('marketplace.errors.packageNotFound'));
    renderDetail();

    expect(await screen.findByText('marketplace.errors.packageNotFound')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.backToCenter' }));
    expect(await screen.findByText('marketplace-center-route')).toBeInTheDocument();
  });

  it('renders metadata conflict, validation rows, and empty readme messaging', async () => {
    mockGetPackage.mockResolvedValue({
      ...mockDetail,
      readmeMarkdown: '',
      metadataConflict: true,
      validationSeverity: 'error',
      validationResults: [
        {
          severity: 'error',
          code: 'marketplace.validation.required_manifest_missing',
          messageKey: 'marketplace.validation.required_manifest_missing',
          filePath: '.codex-plugin/plugin.json',
        },
      ],
    });
    renderDetail();

    expect(await screen.findByText('marketplace.detail.readme.empty')).toBeInTheDocument();
    expect(screen.getByText('marketplace.detail.validation.metadataConflict')).toBeInTheDocument();
    expect(screen.getByText('marketplace.metadata.conflict')).toBeInTheDocument();
    expect(screen.getAllByText('marketplace.validation.required_manifest_missing').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('.codex-plugin/plugin.json')).toBeInTheDocument();
  });

  it('surfaces install failures with redacted command output', async () => {
    const user = userEvent.setup();
    mockInstallPackage.mockResolvedValue({
      status: 'runtimeUnavailable',
      provider: 'codex',
      packageId: 'review-tools',
      workspaceId: 'ws-1',
      errorCode: 'marketplace.install.runtime_delegation_unavailable',
      stderr: 'runtime failed',
      truncated: false,
    });
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.install' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.install.actions.install' }));

    expect(await screen.findByText('marketplace.install.result.runtimeUnavailable')).toBeInTheDocument();
    expect(screen.getByText('runtime failed')).toBeInTheDocument();
  });

  it('keeps the delete dialog open and reports revision conflicts', async () => {
    const user = userEvent.setup();
    mockDeletePackage.mockResolvedValue({
      deleted: false,
      errorCode: 'marketplace.package.revision_conflict',
    });
    renderDetail();

    await screen.findByText('Review Tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.detail.actions.delete' }));
    await user.type(screen.getByLabelText('marketplace.delete.fields.confirm'), 'review-tools');
    await user.click(screen.getByRole('button', { name: 'marketplace.delete.actions.delete' }));

    expect(await screen.findByText('marketplace.delete.result.failed')).toBeInTheDocument();
    expect(screen.queryByText('marketplace-center-route')).not.toBeInTheDocument();
  });

  it('renders provider feature panels for hooks, MCP servers, agents, commands, and output styles', async () => {
    const user = userEvent.setup();
    mockGetPackage.mockResolvedValue({
      ...mockDetail,
      provider: 'claude-code',
      featureContent: {
        agentsMd: '# Claude guidance',
        hooks: [
          {
            id: 'pre-tool',
            name: 'PreToolUse',
            path: 'hooks/pre-tool.json',
            description: 'Runs before tool use.',
            data: {
              event: 'PreToolUse',
              matchers: [
                {
                  matcher: 'Edit',
                  hooks: [
                    {
                      type: 'command',
                      command: 'npm test',
                      timeout: 120,
                      statusMessage: 'checking',
                      shell: 'bash',
                      async: true,
                      asyncRewake: true,
                      if: 'tool.name == "Edit"',
                    },
                    { type: 'http', url: 'https://hooks.example.local', timeout: 60 },
                    { type: 'command', command: 'npm run lint' },
                  ],
                },
              ],
            },
          },
          {
            id: 'native-hooks',
            name: 'hooks',
            path: 'hooks/hooks.json',
            data: {
              description: 'Optional stop-time review gate for Codex Companion.',
              hooks: {
                SessionStart: [
                  {
                    hooks: [
                      {
                        type: 'command',
                        command: 'node "${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs" SessionStart',
                        timeout: 5,
                      },
                    ],
                  },
                ],
                Stop: [
                  {
                    hooks: [
                      {
                        type: 'command',
                        command: 'node "${CLAUDE_PLUGIN_ROOT}/scripts/stop-review-gate-hook.mjs"',
                        timeout: 900,
                      },
                    ],
                  },
                ],
              },
            },
          },
        ],
        mcpServers: [
          {
            id: 'design-context',
            name: 'design-context',
            path: 'mcp/design-context.json',
            description: 'Design MCP server.',
            data: {
              type: 'stdio',
              command: 'npx',
              args: ['design-mcp'],
              env: { FIGMA_TOKEN: 'secret-token' },
              headers: { Authorization: 'Bearer token' },
            },
          },
        ],
        agents: [
          {
            id: 'review-agent',
            name: 'review-agent',
            path: 'agents/review.md',
            content: '# Review Agent',
          },
          {
            id: 'qa-agent',
            name: 'qa-agent',
            path: 'agents/qa.md',
            content: '# QA Agent',
          },
        ],
        commands: [
          {
            id: 'review-command',
            name: 'review',
            path: 'commands/review.md',
            content: '# Review command',
          },
        ],
        outputStyles: [
          {
            id: 'concise-style',
            name: 'concise',
            path: 'output-styles/concise.md',
            content: '# Concise output',
          },
        ],
        skills: mockDetail.featureContent.skills,
      },
    });
    renderDetail();

    await screen.findByText('Review Tools');

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.claudeMd/ }));
    expect(screen.getByText('# Claude guidance')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.detail.agentsMd.actions.copy' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.hooks/ }));
    expect(screen.getByText('PreToolUse')).toBeInTheDocument();
    expect(screen.getByText('npm test')).toBeInTheDocument();
    expect(screen.getByText('https://hooks.example.local')).toBeInTheDocument();
    expect(screen.getByText('marketplace.detail.hooks.card.moreActions')).toBeInTheDocument();
    expect(screen.getByText('Optional stop-time review gate for Codex Companion.')).toBeInTheDocument();
    expect(screen.getByText('SessionStart')).toBeInTheDocument();
    expect(screen.getByText('node "${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs" SessionStart')).toBeInTheDocument();
    expect(screen.getByText('Stop')).toBeInTheDocument();
    expect(screen.getByText('node "${CLAUDE_PLUGIN_ROOT}/scripts/stop-review-gate-hook.mjs"')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.mcp/ }));
    expect(screen.getByText('design-context')).toBeInTheDocument();
    expect(screen.getByText('FIGMA_TOKEN')).toBeInTheDocument();
    expect(screen.getByText('***')).toBeInTheDocument();
    await user.click(screen.getByTitle('marketplace.detail.mcp.card.showEnvValues'));
    expect(screen.getByText('secret-token')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.subagents/ }));
    expect(screen.getAllByText('review.md').length).toBeGreaterThanOrEqual(1);
    await user.type(screen.getByPlaceholderText('marketplace.center.filters.searchPlaceholder'), 'qa');
    expect(screen.getAllByText('qa.md').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('review.md')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.slashCommands/ }));
    expect(screen.getAllByText('review.md').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('# Review command')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.features\.outputStyle/ }));
    expect(screen.getAllByText('concise.md').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('# Concise output')).toBeInTheDocument();
  });
});
