import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';
import { MarketplaceFilesSection } from './MarketplaceFilesSection';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  FileFocusToolbar: () => null,
  FileViewerWorkbench: ({ tabs, activeTabId }: {
    tabs: Array<{ id: string; name: string; content: string }>;
    activeTabId: string | null;
  }) => {
    const tab = tabs.find(item => item.id === activeTabId) ?? tabs[0];
    return tab ? <textarea aria-label={tab.name} readOnly value={tab.content} /> : null;
  },
  useFileViewerTabs: () => {
    const [tabs, setTabs] = React.useState<Array<{ id: string; path: string; name: string; content: string }>>([]);
    const [activeTabId, setActiveTabId] = React.useState<string | null>(null);
    return {
      tabs,
      activeTabId,
      openFile: (node: { path: string; name: string }, content: string) => {
        const tab = { id: node.path, path: node.path, name: node.name, content };
        setTabs(prev => (prev.some(item => item.id === tab.id) ? prev : [...prev, tab]));
        setActiveTabId(tab.id);
      },
      renamePath: vi.fn(),
      removePaths: vi.fn(),
      applyTabsChange: setTabs,
      setActiveTabId,
    };
  },
}));

const detail = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/review-tools',
  revision: 'rev-1',
  updatedAt: '2026-01-01T00:00:00.000Z',
  variants: [],
  catalogMetadata: {},
  manifestMetadata: {},
  featureContent: {
    hooks: [],
    mcpServers: [],
    agents: [],
    commands: [],
    outputStyles: [],
    skills: [],
  },
  packageFiles: [
    {
      path: 'README.md',
      content: '# Package README',
      binary: false,
      mimeType: 'text/markdown',
      size: 16,
    },
    {
      path: '.codex-plugin/plugin.json',
      content: '{ "id": "review-tools" }',
      binary: false,
      mimeType: 'application/json',
      size: 24,
    },
  ],
  validationResults: [],
  activity: [],
} satisfies MarketplacePackageDetail;

describe('MarketplaceFilesSection', () => {
  it('renders package files through the read-only file tree', async () => {
    const user = userEvent.setup();

    render(<MarketplaceFilesSection mode="package" detail={detail} />);

    expect(screen.getByText('marketplace.editor.fileManager.packageFiles.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.fileManager.packageFiles.rootLabel')).toBeInTheDocument();
    expect(screen.getByText('codex/plugins/review-tools')).toBeInTheDocument();
    expect(screen.getAllByText('plugin.json').length).toBeGreaterThan(0);

    await user.click(screen.getByText('README.md'));

    expect(screen.getByText('# Package README')).toBeInTheDocument();
  });

  it('renders skills as read-only files', async () => {
    const user = userEvent.setup();

    render(
      <MarketplaceFilesSection
        mode="skills"
        items={[{
          id: 'review-config',
          name: 'Review Config',
          path: 'skills/review/config.toml',
          content: 'description = "Review config"',
        }]}
      />,
    );

    expect(screen.getByText('marketplace.editor.fileManager.skills.title')).toBeInTheDocument();
    expect(screen.getByText('review')).toBeInTheDocument();

    await user.dblClick(screen.getByText('review'));
    await user.click(screen.getAllByText('config.toml')[0]);

    expect(screen.getByLabelText('config.toml')).toHaveValue('description = "Review config"');
  });

  it('renders editable skill files through the shared files section', async () => {
    const user = userEvent.setup();
    const onDirty = vi.fn();
    const onPackageFilesChange = vi.fn();

    render(
      <MarketplaceFilesSection
        mode="editor-skills"
        items={[{
          id: 'review-config',
          path: 'skills/review/config.toml',
          content: 'description = "Review config"',
        }]}
        onDirty={onDirty}
        onPackageFilesChange={onPackageFilesChange}
      />,
    );

    expect(screen.getByText('marketplace.editor.fileManager.skills.title')).toBeInTheDocument();
    await user.dblClick(screen.getByText('review'));
    await user.click(screen.getAllByText('config.toml')[0]);

    expect(screen.getByLabelText('config.toml')).toHaveValue('description = "Review config"');
    expect(onPackageFilesChange).toHaveBeenCalled();
  });

  it('renders editable package files through the shared files section', async () => {
    const user = userEvent.setup();
    const onDirty = vi.fn();
    const onPackageFilesChange = vi.fn();

    render(
      <MarketplaceFilesSection
        mode="editor-package"
        provider="codex"
        packageId="review-tools"
        packageRoot="codex/plugins/review-tools"
        displayName="Review Tools"
        packageFiles={detail.packageFiles}
        initialNodes={[{
          id: '/codex/plugins/review-tools',
          name: 'review-tools',
          path: '/codex/plugins/review-tools',
          type: 'directory',
          children: [{
            id: '/codex/plugins/review-tools/README.md',
            name: 'README.md',
            path: '/codex/plugins/review-tools/README.md',
            type: 'file',
            extension: 'md',
            size: 16,
            metadata: { content: '# Package README' },
          }],
        }]}
        onDirty={onDirty}
        onPackageFilesChange={onPackageFilesChange}
      />,
    );

    expect(screen.getByText('marketplace.editor.fileManager.packageFiles.title')).toBeInTheDocument();
    expect(screen.getByText('codex/plugins/review-tools')).toBeInTheDocument();
    await user.dblClick(screen.getByText('review-tools'));
    await user.click(screen.getAllByText('README.md')[0]);

    expect(screen.getByLabelText('README.md')).toHaveValue('# Package README');
    expect(onPackageFilesChange).toHaveBeenCalled();
  });
});
