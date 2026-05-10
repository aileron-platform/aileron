import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MarketplaceEditorView,
  shouldUpdateMarketplaceEditorFileContent,
} from './MarketplaceEditorView';
import type { MarketplacePackageDetail, MarketplaceProvider } from '@/shared/types/marketplace';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange, placeholder }: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder ?? 'markdown-editor'}
      value={value}
      onChange={event => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => {
  const imageExtensions = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff'];
  const isImageFileName = (fileName: string): boolean => {
    const extension = fileName.split('.').pop()?.toLowerCase() ?? '';
    return imageExtensions.includes(extension);
  };

  type MockTab = {
    id: string;
    path: string;
    name: string;
    content: string;
    originalContent: string;
    isModified: boolean;
  };

  return {
    CodeTextEditor: ({ content, onContentChange, fileName }: {
      content: string;
      onContentChange: (content: string) => void;
      fileName: string;
    }) => (
      <textarea
        aria-label={fileName}
        value={content}
        onChange={event => onContentChange(event.target.value)}
      />
    ),
    FileViewerWorkbench: ({ tabs, activeTabId, onActiveTabChange, onTabsChange }: {
      tabs: MockTab[];
      activeTabId: string | null;
      onActiveTabChange: (id: string | null) => void;
      onTabsChange: (next: MockTab[]) => void;
    }) => {
      const activeTab = tabs.find(tab => tab.id === activeTabId) ?? null;
      return (
        <div data-testid="file-viewer-workbench">
          <div role="tablist">
            {tabs.map(tab => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={tab.id === activeTabId}
                onClick={() => onActiveTabChange(tab.id)}
              >
                {`${tab.name} (tab)`}
              </button>
            ))}
          </div>
          {activeTab ? (
            isImageFileName(activeTab.name) ? (
              <div data-testid="image-viewer">
                <button type="button" aria-label="shared.fileViewer.image.zoomIn">zoom-in</button>
                <button type="button" aria-label="shared.fileViewer.image.download">download</button>
              </div>
            ) : (
              <textarea
                aria-label={activeTab.path}
                value={activeTab.content}
                onChange={(event) => {
                  const value = event.target.value;
                  onTabsChange(tabs.map(tab => (
                    tab.id === activeTab.id
                      ? { ...tab, content: value, isModified: value !== tab.originalContent }
                      : tab
                  )));
                }}
              />
            )
          ) : null}
        </div>
      );
    },
    useFileViewerTabs: () => {
      const [tabs, setTabs] = React.useState<MockTab[]>([]);
      const [activeTabId, setActiveTabId] = React.useState<string | null>(null);
      const openFile = React.useCallback((node: { path: string; name: string }, content: string) => {
        setTabs(prev => {
          if (prev.some(tab => tab.id === node.path)) return prev;
          return [
            ...prev,
            {
              id: node.path,
              path: node.path,
              name: node.name,
              content,
              originalContent: content,
              isModified: false,
            },
          ];
        });
        setActiveTabId(node.path);
      }, []);
      const applyTabsChange = React.useCallback((nextTabs: MockTab[]) => {
        setTabs(nextTabs);
        setActiveTabId(prev => {
          if (prev && nextTabs.some(tab => tab.id === prev)) return prev;
          return nextTabs[nextTabs.length - 1]?.id ?? null;
        });
      }, []);
      const renamePath = React.useCallback((oldPath: string, newPath: string, newName: string) => {
        setTabs(prev => prev.map(tab => (
          tab.path === oldPath
            ? { ...tab, id: newPath, path: newPath, name: newName }
            : tab.path.startsWith(`${oldPath}/`)
              ? { ...tab, id: tab.path.replace(oldPath, newPath), path: tab.path.replace(oldPath, newPath) }
              : tab
        )));
        setActiveTabId(prev => {
          if (!prev) return prev;
          if (prev === oldPath) return newPath;
          return prev.startsWith(`${oldPath}/`) ? prev.replace(oldPath, newPath) : prev;
        });
      }, []);
      const removePaths = React.useCallback((paths: string[]) => {
        const isAffected = (id: string) => paths.some(path => id === path || id.startsWith(`${path}/`));
        setTabs(prev => prev.filter(tab => !isAffected(tab.id)));
        setActiveTabId(prev => (prev && isAffected(prev) ? null : prev));
      }, []);
      const activeTab = tabs.find(tab => tab.id === activeTabId) ?? null;

      return {
        tabs,
        activeTabId,
        activeTab,
        openFile,
        setActiveTabId,
        applyTabsChange,
        renamePath,
        removePaths,
      };
    },
  };
});

const marketplaceApiMock = vi.hoisted(() => ({
  getPackage: vi.fn(),
  createPackage: vi.fn(),
  savePackage: vi.fn(),
}));

vi.mock('../../api/marketplaceApi', () => marketplaceApiMock);

const createMockFeatureContent = (provider: MarketplaceProvider): MarketplacePackageDetail['featureContent'] => {
  if (provider === 'gemini') {
    return {
      agentsMd: '# GEMINI.md',
      hooks: [
        {
          id: 'session-start-context',
          name: 'session-start-context',
          description: 'Loads workspace context when a Gemini session starts.',
          path: 'hooks/session-start-context.json',
          content: '{\n  "hooks": {\n    "BeforeTool": [{ "matcher": "*", "sequential": true, "hooks": [{ "type": "command", "name": "load-context", "command": "gemini context load", "timeout": 60000, "description": "Load workspace context before tool execution." }] }]\n  }\n}',
        },
      ],
      mcpServers: [],
      agents: [
        {
          id: 'research-subagent',
          name: 'research-subagent',
          description: 'Gemini subagent for local documentation and codebase research.',
          path: 'agents/research-subagent.md',
          content: '# Research subagent\n\nGather local context, cite relevant files, and return concise findings.',
        },
      ],
      commands: [
        {
          id: 'workspace-summary',
          name: '/workspace-summary',
          description: 'Gemini slash command for workspace status summaries.',
          path: 'commands/workspace-summary.toml',
          content: 'prompt = """\nSummarize workspace structure, changed files, and likely next steps for `{{args}}`.\n"""',
        },
      ],
      outputStyles: [],
      skills: [
        {
          id: 'workspace-scan',
          name: 'Workspace scan',
          description: 'Gemini skill for summarizing workspace structure.',
          path: 'skills/workspace-scan/SKILL.md',
          content: '# Workspace scan\n\nScan workspace folders and produce a concise project map for Gemini CLI.',
        },
      ],
      policies: [
        {
          id: 'safe-shell',
          name: 'safe-shell',
          description: 'Gemini policy rules for blocking destructive shell patterns.',
          path: 'policies/safe-shell.toml',
          content: '[rule]\nname = "block-destructive-shell"\ndescription = "Block destructive shell commands in shared workspaces."\n\n[[rule.matchers]]\ntool = "run_shell_command"\npattern = "rm -rf"\n',
        },
      ],
    };
  }

  return {
    agentsMd: '# AGENTS.md',
    hooks: [
      {
        id: 'test-before-finish',
        name: 'test-before-finish',
        description: 'Runs targeted verification before finishing a Codex change.',
        path: 'hooks/test-before-finish.json',
        content: '{\n  "hooks": {\n    "Stop": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "npm test", "timeout": 120 }] }]\n  }\n}',
      },
    ],
    mcpServers: [
      {
        id: 'figma-context',
        name: 'figma-context',
        description: 'Codex MCP server for Figma design metadata.',
        path: 'mcp/figma-context.json',
        content: '{\n  "name": "figma-context",\n  "transport": "http",\n  "url": "https://api.figma.com/mcp"\n}',
      },
    ],
    agents: [
      {
        id: 'implementation-subagent',
        name: 'implementation-subagent',
        description: 'Codex subagent for bounded implementation work.',
        path: 'agents/implementation-subagent.md',
        content: '# Implementation subagent\n\nYou own a narrow code change and report files changed, tests run, and follow-up risks.',
      },
    ],
    commands: [
      {
        id: 'plan-change',
        name: '/plan-change',
        description: 'Draft a compact implementation plan for the current Codex task.',
        path: 'commands/plan-change.md',
        content: '# /plan-change\n\nCreate a short implementation plan from the current request and code context.',
      },
    ],
    outputStyles: provider === 'claude-code'
      ? [
        {
          id: 'review-findings',
          name: 'review-findings',
          description: 'Review output format.',
          path: 'output-styles/review-findings.md',
          content: '# Review findings\n\nFormat review output with findings first.',
        },
      ]
      : [],
    skills: [
      {
        id: provider === 'claude-code' ? 'review-checklist' : 'codebase-map',
        name: provider === 'claude-code' ? 'review-checklist' : 'Codebase map',
        description: provider === 'claude-code'
          ? 'Use this skill to review staged changes with findings-first output.'
          : 'Codex skill for mapping app boundaries before implementation.',
        path: provider === 'claude-code' ? 'skills/review-checklist/SKILL.md' : 'skills/codebase-map/SKILL.md',
        content: provider === 'claude-code'
          ? '# Review checklist\n\nUse this skill to review staged changes with findings-first output.'
          : '# Codebase map\n\nMap files, ownership boundaries, and likely test surfaces before changing code.',
      },
    ],
  };
};

const createMockPackageFiles = (provider: MarketplaceProvider, packageId: string): MarketplacePackageDetail['packageFiles'] => {
  if (provider === 'gemini') {
    return [
      {
        path: 'gemini-extension.json',
        content: JSON.stringify({ name: packageId, version: '0.1.0' }, null, 2),
        binary: false,
        mimeType: 'application/json',
        size: 48,
      },
      {
        path: 'README.md',
        content: '# Package',
        binary: false,
        mimeType: 'text/markdown',
        size: 9,
      },
    ];
  }
  return [
    {
      path: `${provider === 'codex' ? '.codex-plugin' : '.claude-plugin'}/plugin.json`,
      content: JSON.stringify({ name: packageId, version: '0.1.0' }, null, 2),
      binary: false,
      mimeType: 'application/json',
      size: 48,
    },
    {
      path: 'README.md',
      content: '# Package',
      binary: false,
      mimeType: 'text/markdown',
      size: 9,
    },
  ];
};

const createMockDetail = (provider: MarketplaceProvider, packageId: string): MarketplacePackageDetail => ({
  provider,
  packageType: provider === 'gemini' ? 'extension' : 'plugin',
  packageId,
  displayName: packageId,
  version: '0.1.0',
  description: 'Package description',
  category: 'Productivity',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: provider === 'gemini' ? `gemini/extensions/${packageId}` : `${provider}/plugins/${packageId}`,
  revision: `rev-${packageId}`,
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    provider,
    packageId,
    displayName: packageId,
    registryPath: provider === 'gemini' ? `gemini/extensions/${packageId}` : `${provider}/plugins/${packageId}`,
    revision: `rev-${packageId}`,
  }],
  catalogMetadata: {},
  manifestMetadata: provider === 'gemini'
    ? { name: packageId, version: '0.1.0' }
    : provider === 'codex'
      ? { name: packageId, version: '0.1.0', description: 'Package description' }
      : { name: packageId },
  readmeMarkdown: '# Package',
  featureContent: createMockFeatureContent(provider),
  packageFiles: createMockPackageFiles(provider, packageId),
  validationResults: [],
  activity: [],
});

const renderCodexEditor = () => render(
  <MemoryRouter initialEntries={['/marketplace/packages/codex/demo-plugin/edit']}>
    <Routes>
      <Route
        path="/marketplace/packages/:provider/:packageId/edit"
        element={<MarketplaceEditorView mode="edit" />}
      />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

const renderCodexEditorForPackage = (packageId: string) => render(
  <MemoryRouter initialEntries={[`/marketplace/packages/codex/${packageId}/edit`]}>
    <Routes>
      <Route
        path="/marketplace/packages/:provider/:packageId/edit"
        element={<MarketplaceEditorView mode="edit" />}
      />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

const renderGeminiEditor = () => render(
  <MemoryRouter initialEntries={['/marketplace/packages/gemini/workspace-tools/edit']}>
    <Routes>
      <Route
        path="/marketplace/packages/:provider/:packageId/edit"
        element={<MarketplaceEditorView mode="edit" />}
      />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

const renderCreateEditor = () => render(
  <MemoryRouter initialEntries={['/marketplace/packages/new']}>
    <Routes>
      <Route
        path="/marketplace/packages/new"
        element={<MarketplaceEditorView mode="create" />}
      />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceEditorView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    marketplaceApiMock.getPackage.mockImplementation((provider: MarketplaceProvider, packageId: string) => (
      Promise.resolve(createMockDetail(provider, packageId))
    ));
    marketplaceApiMock.createPackage.mockImplementation(({ provider, packageId }: { provider: MarketplaceProvider; packageId: string }) => (
      Promise.resolve({
        provider,
        packageType: provider === 'gemini' ? 'extension' : 'plugin',
        packageId,
        displayName: packageId,
        tags: [],
        sourceType: 'created',
        indexedResourceNames: [],
        validationSeverity: 'none',
        registryPath: provider === 'gemini' ? `gemini/extensions/${packageId}` : `${provider}/plugins/${packageId}`,
        revision: `rev-${packageId}`,
        updatedAt: '2026-05-07T00:00:00.000Z',
        variants: [{
          provider,
          packageId,
          displayName: packageId,
          registryPath: provider === 'gemini' ? `gemini/extensions/${packageId}` : `${provider}/plugins/${packageId}`,
          revision: `rev-${packageId}`,
        }],
      })
    ));
    marketplaceApiMock.savePackage.mockImplementation(({ provider, packageId }: { provider: MarketplaceProvider; packageId: string }) => (
      Promise.resolve({
        package: createMockDetail(provider, packageId),
        revision: `rev-${packageId}-saved`,
        validationResults: [],
      })
    ));
  });

  it('syncs Codex required form fields from listing and manifest JSON tabs', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));

    fireEvent.change(screen.getByLabelText('codex/.agents/plugins/marketplace.json'), { target: { value: JSON.stringify({
      name: 'demo-next',
      source: { source: 'local', path: './plugins/demo-next' },
      policy: {
        installation: 'INSTALLED_BY_DEFAULT',
        authentication: 'ON_USE',
      },
      category: 'Coding',
    }, null, 2) } });

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.form' }));

    expect(screen.getAllByDisplayValue('demo-next').length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue('./plugins/demo-next')).toBeInTheDocument();
    expect(screen.getByDisplayValue('INSTALLED_BY_DEFAULT')).toBeInTheDocument();
    expect(screen.getByDisplayValue('ON_USE')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Coding')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));
    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.required.json.tabs.plugin' }));
    fireEvent.change(screen.getByLabelText('codex/plugins/demo-next/.codex-plugin/plugin.json'), { target: { value: JSON.stringify({
      name: 'manifest-demo',
      version: '2.0.0',
      description: 'Codex required description',
    }, null, 2) } });
    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.form' }));

    expect(screen.getAllByDisplayValue('manifest-demo').length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue('2.0.0')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Codex required description')).toBeInTheDocument();
  });

  it('keeps the last valid form values when JSON is invalid', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));
    fireEvent.change(screen.getByLabelText('codex/.agents/plugins/marketplace.json'), { target: { value: '{' } });

    expect(screen.getByText('marketplace.editor.required.json.parseError')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.form' }));
    expect(screen.getAllByDisplayValue('demo-plugin').length).toBeGreaterThan(0);
  });

  it('shows only the current package entry in listing JSON', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));

    const listingJson = JSON.parse((screen.getByLabelText('codex/.agents/plugins/marketplace.json') as HTMLTextAreaElement).value);
    expect(listingJson).toMatchObject({
      name: 'demo-plugin',
      source: {
        source: 'local',
        path: './plugins/demo-plugin',
      },
    });
    expect(listingJson.plugins).toBeUndefined();
    expect(listingJson.owner).toBeUndefined();
    expect(listingJson.description).toBeUndefined();
  });

  it('uses the shared code editor for Gemini TOML policy resources', async () => {
    const user = userEvent.setup();
    renderGeminiEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.policies/ }));

    expect((screen.getByLabelText('policies/safe-shell.toml') as HTMLTextAreaElement).value).toContain('pattern = "rm -rf"');
  });

  it('edits Gemini provider guidance and README drafts from the basic tab', async () => {
    const user = userEvent.setup();
    renderGeminiEditor();

    await user.type(
      screen.getByLabelText('marketplace.editor.packageSections.providerGuidance.placeholder'),
      '\nGemini provider guidance.',
    );
    await user.type(
      screen.getByLabelText('marketplace.editor.packageSections.readme.placeholder'),
      '\nREADME update.',
    );

    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();
  });

  it('renders Claude Code skills without tripping the module error boundary', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/marketplace/packages/claude-code/review-assistant/edit']}>
        <Routes>
          <Route
            path="/marketplace/packages/:provider/:packageId/edit"
            element={<MarketplaceEditorView mode="edit" />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.skills/ }));

    expect(screen.getByText('review-checklist')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.errors.module.title')).not.toBeInTheDocument();
  });

  it('edits, saves, and refreshes AGENTS.md guidance drafts', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.agentsMd/ }));

    const guidanceEditor = screen.getByLabelText('marketplace.editor.agentsMd.placeholder');
    const initialContent = (guidanceEditor as HTMLTextAreaElement).value;
    const saveButton = screen.getByRole('button', { name: 'marketplace.common.actions.save' });
    expect(saveButton).toBeDisabled();

    await user.type(guidanceEditor, '\n\nAdditional Codex guidance.');
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();
    expect(saveButton).toBeEnabled();

    await user.click(saveButton);
    expect(saveButton).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));
    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'AGENTS.md',
            content: expect.stringContaining('Additional Codex guidance.'),
          }),
        ]),
      }));
    });

    await user.type(guidanceEditor, '\nTemporary local change.');
    expect(saveButton).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.refresh' }));

    expect(guidanceEditor).toHaveValue(`${initialContent}\n\nAdditional Codex guidance.`);
  });

  it('shows the unsaved changes alert before leaving a dirty package draft', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));
    fireEvent.change(screen.getByLabelText('codex/.agents/plugins/marketplace.json'), { target: { value: JSON.stringify({
      name: 'dirty-plugin',
      source: { source: 'local', path: './plugins/dirty-plugin' },
    }, null, 2) } });

    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.back' }));

    expect(screen.getByText('marketplace.editor.unsaved.title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.actions.discard' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.actions.save' })).toBeInTheDocument();
  });

  it('marks beforeunload when the editor has dirty required JSON and supports discard', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));
    fireEvent.change(screen.getByLabelText('codex/.agents/plugins/marketplace.json'), { target: { value: JSON.stringify({
      name: 'dirty-before-unload',
      source: { source: 'local', path: './plugins/dirty-before-unload' },
    }, null, 2) } });

    const event = new Event('beforeunload', { cancelable: true }) as BeforeUnloadEvent;
    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.discard' }));
    expect(screen.queryByText('marketplace.editor.dirty')).not.toBeInTheDocument();
  });

  it('shows a localized error when loading an existing package fails', async () => {
    marketplaceApiMock.getPackage.mockRejectedValueOnce(new Error('load failed'));
    renderCodexEditor();

    expect(await screen.findByText('marketplace.editor.saveStatus.validationError')).toBeInTheDocument();
  });

  it('creates package files through the shared file operation dialog', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.files/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.fileManager.actions.create.trigger' }));
    await user.click(screen.getByRole('menuitem', { name: 'marketplace.editor.fileManager.sidebar.createFile' }));
    await user.type(screen.getByLabelText('common.fileOperations.create.nameLabel'), 'notes.md');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    expect(screen.getByLabelText('/codex/plugins/demo-plugin/notes.md')).toHaveValue('');
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();
  });

  it('creates and edits skill files through the skill file manager', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await screen.findByDisplayValue('Package description');
    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.skills/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.fileManager.actions.create.trigger' }));
    await user.click(screen.getByRole('menuitem', { name: 'marketplace.editor.fileManager.sidebar.createFolder' }));
    await user.type(screen.getByLabelText('common.fileOperations.create.nameLabel'), 'new-skill');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    expect(screen.getByText('new-skill')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.fileManager.actions.create.trigger' }));
    await user.click(screen.getByRole('menuitem', { name: 'marketplace.editor.fileManager.sidebar.createFile' }));
    await user.type(screen.getByLabelText('common.fileOperations.create.nameLabel'), 'extra.md');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    expect(screen.getByText('extra.md')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'skills/extra.md',
          }),
        ]),
      }));
    });
  });

  it('does not mark the package dirty when opening a skill file without content changes', async () => {
    const content = '# Codebase map\n\nMap files, ownership boundaries, and likely test surfaces before changing code.';

    expect(shouldUpdateMarketplaceEditorFileContent(content, content)).toBe(false);
    expect(shouldUpdateMarketplaceEditorFileContent(`${content}\n`, content)).toBe(true);
  });

  it('keeps uploaded binary assets out of the text editor and shows the shared image viewer', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.files/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.fileManager.sidebar.upload' }));

    const tabHeader = await screen.findByRole('tab', { name: /uploaded-image\.png/ });
    expect(tabHeader).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('button', { name: 'shared.fileViewer.image.zoomIn' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.fileViewer.image.download' })).toBeInTheDocument();
    expect(screen.queryByLabelText('/codex/plugins/demo-plugin/assets/uploaded-image.png')).not.toBeInTheDocument();
  });

  it('requires provider selection before showing create metadata controls', async () => {
    const user = userEvent.setup();
    renderCreateEditor();

    expect(screen.getByText('marketplace.editor.providerStep.title')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.editor.createTitle')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.providers\.codex/ }));

    expect(screen.getByText('marketplace.editor.createTitle')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.basic/ })).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.fields.providerHint')).toBeInTheDocument();
  });

  it('renders per-package JSON document tabs with hover-only guidance and file badges', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));

    expect(screen.getByRole('tab', { name: 'marketplace.editor.required.json.tabs.entry' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'marketplace.editor.required.json.tabs.plugin' })).toBeInTheDocument();
    expect(screen.getByText('codex/.agents/plugins/marketplace.json')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.required.json.fileBadge.thisEntryOnly')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.editor.required.json.popovers.entry')).not.toBeInTheDocument();

    await user.hover(screen.getAllByRole('button', { name: 'marketplace.editor.required.json.infoLabel' })[0]);

    expect(screen.getByText('marketplace.editor.required.json.popovers.entry')).toBeInTheDocument();
  });

  it('renders Gemini JSON mode as a single extension settings document', async () => {
    const user = userEvent.setup();
    renderGeminiEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));

    expect(screen.getByText('marketplace.editor.required.json.tabs.extension')).toBeInTheDocument();
    expect(screen.getByLabelText('gemini/extensions/workspace-tools/gemini-extension.json')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'marketplace.editor.required.json.tabs.entry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'marketplace.editor.required.json.tabs.plugin' })).not.toBeInTheDocument();
  });

  it('reports create save validation and successful saves', async () => {
    const user = userEvent.setup();
    renderCreateEditor();

    await user.click(screen.getByRole('button', { name: /marketplace\.providers\.codex/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));
    expect(screen.getByText('marketplace.editor.saveStatus.validationError')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('marketplace.editor.fields.packageIdPlaceholder'), 'new-plugin');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));
    expect(screen.getByText('marketplace.editor.saveStatus.success')).toBeInTheDocument();
    expect(marketplaceApiMock.createPackage).toHaveBeenCalledWith({
      provider: 'codex',
      packageId: 'new-plugin',
      displayName: 'new-plugin',
      description: '',
    });
  });

  it('reports revision conflicts while saving an existing package', async () => {
    const user = userEvent.setup();
    marketplaceApiMock.savePackage.mockRejectedValueOnce(new Error('marketplace.package.revision_conflict'));
    renderCodexEditorForPackage('revision-conflict');

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    expect(screen.getByText('marketplace.editor.saveStatus.revisionConflict')).toBeInTheDocument();
    expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
      provider: 'codex',
      packageId: 'revision-conflict',
      revision: 'rev-revision-conflict',
    }));
  });

  it('saves an existing package draft before leaving the editor', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.requiredTabs.json' }));
    await user.click(screen.getByRole('tab', { name: 'marketplace.editor.required.json.tabs.plugin' }));
    fireEvent.change(screen.getByLabelText('codex/plugins/demo-plugin/.codex-plugin/plugin.json'), { target: { value: JSON.stringify({
      name: 'demo-plugin',
      version: '0.2.0',
      description: 'Saved from leave dialog',
    }, null, 2) } });

    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.back' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
      provider: 'codex',
      packageId: 'demo-plugin',
      revision: 'rev-demo-plugin',
      manifest: expect.objectContaining({
        version: '0.2.0',
        description: 'Saved from leave dialog',
      }),
    }));
    expect(await screen.findByText('marketplace-center-route')).toBeInTheDocument();
  });

  it('copies and downloads provider guidance from AGENTS.md actions', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = navigator.clipboard;
    const originalCreateObjectUrl = URL.createObjectURL;
    const originalRevokeObjectUrl = URL.revokeObjectURL;
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:agents-md'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });

    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.agentsMd/ }));
    await user.type(
      screen.getByLabelText('marketplace.editor.agentsMd.placeholder'),
      '# AGENTS.md\n\nGuidance body.',
    );
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.agentsMd.actions.copy' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.agentsMd.actions.download' }));

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('# AGENTS.md'));

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: originalCreateObjectUrl,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: originalRevokeObjectUrl,
    });
    clickSpy.mockRestore();
  });

  it('validates and creates MCP servers from the provider feature section', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.mcp/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' }));

    expect(screen.getByText('marketplace.editor.mcp.dialog.titleCreate')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.editor.mcp.dialog.fields.scope.label')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.mcp.dialog.actions.create' }));
    expect(screen.getByText('marketplace.editor.mcp.dialog.validation.nameRequired')).toBeInTheDocument();

    await user.type(screen.getByLabelText('marketplace.editor.mcp.dialog.fields.name.label'), 'local-context');
    await user.type(screen.getByLabelText('marketplace.editor.mcp.dialog.fields.description.label'), 'Local context server');
    await user.type(screen.getByPlaceholderText('marketplace.editor.mcp.dialog.fields.command.placeholder'), 'npx');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.mcp.dialog.actions.create' }));

    expect(screen.getByText('local-context')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();
  });

  it('edits an existing MCP server card and marks the package draft dirty', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.mcp/ }));

    const card = screen.getByText('figma-context').closest('[class*="rounded-lg"][class*="border"]') as HTMLElement;
    await user.click(within(card).getAllByRole('button')[0]);

    expect(screen.getByText('marketplace.editor.mcp.dialog.title')).toBeInTheDocument();
    expect(screen.getByLabelText('marketplace.editor.mcp.dialog.fields.name.label')).toBeDisabled();
    await user.clear(screen.getByLabelText('marketplace.editor.mcp.dialog.fields.description.label'));
    await user.type(screen.getByLabelText('marketplace.editor.mcp.dialog.fields.description.label'), 'Updated Figma MCP server');

    const httpUrlInput = screen.queryByPlaceholderText('marketplace.editor.mcp.dialog.fields.url.placeholderHttp');
    if (httpUrlInput) {
      await user.clear(httpUrlInput);
      await user.type(httpUrlInput, 'https://api.figma.com/mcp/v2');
    }

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.mcp.dialog.actions.save' }));

    expect(screen.getByText('figma-context')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
      packageFiles: expect.arrayContaining([
        expect.objectContaining({
          path: 'mcp/figma-context.json',
          content: expect.stringContaining('Updated Figma MCP server'),
        }),
      ]),
    }));
  });

  it('renders MCP servers imported from a root .mcp.json data entry', async () => {
    const user = userEvent.setup();
    marketplaceApiMock.getPackage.mockResolvedValueOnce({
      ...createMockDetail('claude-code', 'discord'),
      featureContent: {
        ...createMockFeatureContent('claude-code'),
        mcpServers: [
          {
            id: '.mcp.json:discord',
            name: 'discord',
            path: '.mcp.json',
            data: {
              command: 'bun',
              args: ['run', '--cwd', '${CLAUDE_PLUGIN_ROOT}', '--shell=bun', '--silent', 'start'],
            },
          },
        ],
      },
      packageFiles: [
        {
          path: '.claude-plugin/plugin.json',
          content: JSON.stringify({ name: 'discord', version: '0.1.0' }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 48,
        },
        {
          path: '.mcp.json',
          content: JSON.stringify({
            mcpServers: {
              discord: {
                command: 'bun',
                args: ['run', '--cwd', '${CLAUDE_PLUGIN_ROOT}', '--shell=bun', '--silent', 'start'],
              },
            },
          }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 180,
        },
        {
          path: 'package.json',
          content: JSON.stringify({ scripts: { start: 'bun src/index.ts' } }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 64,
        },
      ],
    });
    render(
      <MemoryRouter initialEntries={['/marketplace/packages/claude-code/discord/edit']}>
        <Routes>
          <Route
            path="/marketplace/packages/:provider/:packageId/edit"
            element={<MarketplaceEditorView mode="edit" />}
          />
          <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('tab', { name: /^marketplace\.editor\.tabs\.mcp/ }));

    const card = screen.getByText('discord').closest('[class*="rounded-lg"][class*="border"]') as HTMLElement;
    expect(within(card).getByText('bun')).toBeInTheDocument();
    expect(within(card).getByText('run --cwd ${CLAUDE_PLUGIN_ROOT} --shell=bun --silent start')).toBeInTheDocument();

    await user.click(within(card).getAllByRole('button')[0]);

    expect(screen.getByDisplayValue('bun')).toBeInTheDocument();
    expect(screen.getByDisplayValue('run')).toBeInTheDocument();
    expect(screen.getByDisplayValue('${CLAUDE_PLUGIN_ROOT}')).toBeInTheDocument();
  });

  it('shows imported root .mcp.json in the package file tree', async () => {
    const user = userEvent.setup();
    marketplaceApiMock.getPackage.mockResolvedValueOnce({
      ...createMockDetail('claude-code', 'discord'),
      featureContent: {
        ...createMockFeatureContent('claude-code'),
        mcpServers: [
          {
            id: '.mcp.json:discord',
            name: 'discord',
            path: '.mcp.json',
            data: {
              command: 'bun',
              args: ['run', '--cwd', '${CLAUDE_PLUGIN_ROOT}', '--shell=bun', '--silent', 'start'],
            },
          },
        ],
      },
      packageFiles: [
        {
          path: '.claude-plugin/plugin.json',
          content: JSON.stringify({ name: 'discord', version: '0.1.0' }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 48,
        },
        {
          path: '.mcp.json',
          content: JSON.stringify({
            mcpServers: {
              discord: {
                command: 'bun',
                args: ['run', '--cwd', '${CLAUDE_PLUGIN_ROOT}', '--shell=bun', '--silent', 'start'],
              },
            },
          }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 180,
        },
        {
          path: 'package.json',
          content: JSON.stringify({ scripts: { start: 'bun src/index.ts' } }, null, 2),
          binary: false,
          mimeType: 'application/json',
          size: 64,
        },
      ],
    });
    render(
      <MemoryRouter initialEntries={['/marketplace/packages/claude-code/discord/edit']}>
        <Routes>
          <Route
            path="/marketplace/packages/:provider/:packageId/edit"
            element={<MarketplaceEditorView mode="edit" />}
          />
          <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('tab', { name: /^marketplace\.editor\.tabs\.files/ }));
    expect(screen.queryByText('discord')).not.toBeInTheDocument();
    await user.click(screen.getByText('.mcp.json'));

    const editor = screen.getByLabelText('/claude-code/plugins/discord/.mcp.json') as HTMLTextAreaElement;
    expect(editor.value).toContain('"discord"');
    expect(editor.value).toContain('"args"');
    expect(screen.getByText('package.json')).toBeInTheDocument();
  });

  it('opens Codex hook creation with provider-specific validation', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.hooks/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' }));

    expect(screen.getByText('marketplace.editor.hooks.dialog.titleCreate')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.editor.hooks.dialog.codexFeatureFlag')).not.toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.validation.commandRequired')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.hooks.dialog.actions.save' })).toBeDisabled();
  });

  it('edits an existing hook card and marks the package draft dirty', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.hooks/ }));

    const card = screen.getByText('test-before-finish').closest('[class*="rounded-lg"][class*="border"]') as HTMLElement;
    await user.click(within(card).getAllByRole('button')[0]);

    expect(screen.getByText('marketplace.editor.hooks.dialog.title')).toBeInTheDocument();
    await user.clear(screen.getByLabelText('marketplace.editor.hooks.dialog.fields.name.label'));
    await user.type(screen.getByLabelText('marketplace.editor.hooks.dialog.fields.name.label'), 'test-before-save');
    await user.clear(screen.getByPlaceholderText('marketplace.editor.hooks.dialog.executions.commandPlaceholder.codex'));
    await user.type(screen.getByPlaceholderText('marketplace.editor.hooks.dialog.executions.commandPlaceholder.codex'), 'npm run test:unit');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.hooks.dialog.actions.save' }));

    expect(screen.getByText('test-before-save')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'hooks/test-before-finish.json',
            content: expect.stringContaining('npm run test:unit'),
          }),
        ]),
      }));
    });
  });

  it('opens Gemini hook creation with sequential matchers and execution metadata fields', async () => {
    const user = userEvent.setup();
    renderGeminiEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.hooks/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' }));

    expect(screen.getByText('marketplace.editor.hooks.dialog.titleCreate')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.description.gemini')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.matchers.sequentialLabel')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.nameLabel')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.descriptionLabel')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.timeoutLabel.gemini')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.editor.hooks.dialog.codexFeatureFlag')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.hooks.dialog.actions.save' })).toBeDisabled();
  });

  it('creates Markdown resources in document viewer tabs and marks the draft dirty', async () => {
    const user = userEvent.setup();
    renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.subagents/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.actions.add' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.create.actions.create' }));

    expect(screen.getByText('marketplace.editor.documentViewer.create.validation.contentRequired')).toBeInTheDocument();

    await user.clear(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'));
    await user.type(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'), 'agents/new-reviewer');
    const contentEditors = screen.getAllByLabelText('marketplace.editor.documentViewer.editor.placeholder');
    await user.type(contentEditors[contentEditors.length - 1], '# New Reviewer');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.create.actions.create' }));

    expect(screen.getAllByText('new-reviewer.md').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('marketplace.editor.documentViewer.unsavedFile')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'agents/new-reviewer.md',
            content: '# New Reviewer',
          }),
        ]),
      }));
    });
  });

  it('persists slash commands and output styles from document viewer tabs', async () => {
    const user = userEvent.setup();
    const codexEditor = renderCodexEditor();

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.slashCommand/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.actions.add' }));
    await user.clear(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'));
    await user.type(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'), 'commands/sync-check');
    let contentEditors = screen.getAllByLabelText('marketplace.editor.documentViewer.editor.placeholder');
    await user.type(contentEditors[contentEditors.length - 1], '# /sync-check');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.create.actions.create' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'commands/sync-check.md',
            content: '# /sync-check',
          }),
        ]),
      }));
    });

    vi.clearAllMocks();
    codexEditor.unmount();
    render(
      <MemoryRouter initialEntries={['/marketplace/packages/claude-code/review-assistant/edit']}>
        <Routes>
          <Route
            path="/marketplace/packages/:provider/:packageId/edit"
            element={<MarketplaceEditorView mode="edit" />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: /^marketplace\.editor\.tabs\.outputStyle/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.actions.add' }));
    await user.clear(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'));
    await user.type(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'), 'output-styles/brief-review');
    contentEditors = screen.getAllByLabelText('marketplace.editor.documentViewer.editor.placeholder');
    await user.type(contentEditors[contentEditors.length - 1], '# Brief Review');
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.create.actions.create' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.actions.save' }));

    await waitFor(() => {
      expect(marketplaceApiMock.savePackage).toHaveBeenCalledWith(expect.objectContaining({
        packageFiles: expect.arrayContaining([
          expect.objectContaining({
            path: 'output-styles/brief-review.md',
            content: '# Brief Review',
          }),
        ]),
      }));
    });
  });

  it('counts skills tab by top-level folder in editor mode', async () => {
    const user = userEvent.setup();
    const provider = 'codex' as const;
    const packageId = 'grouped-skill-package';
    const baseDetail = createMockDetail(provider, packageId) as MarketplacePackageDetail;
    marketplaceApiMock.getPackage.mockResolvedValueOnce({
      ...baseDetail,
      featureContent: {
        ...baseDetail.featureContent,
        skills: [
          { id: 'review-main', name: 'Review Main', path: 'skills/review/README.md', content: '# Review Main' },
          { id: 'review-config', name: 'Review Config', path: 'skills/review/config.toml', content: 'title = \"Review config\"' },
          { id: 'auth', name: 'Auth', path: 'skills/auth/SKILL.md', content: '# Auth' },
        ],
      },
    });

    renderCodexEditorForPackage(packageId);

    const skillsTab = await screen.findByRole('tab', { name: /^marketplace\.editor\.tabs\.skills/ });
    expect(skillsTab).toHaveTextContent(/marketplace\.editor\.tabs\.skills/);
    expect(skillsTab).toHaveTextContent(/2/);
  });
});
