import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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
  FileViewerWorkbench: ({ tabs, activeTabId, adapter, capabilities, readOnly, onActiveTabChange, onTabsChange }: {
    tabs: Array<{ id: string; name: string; content: string }>;
    activeTabId: string | null;
    adapter?: { readBlob?: (path: string) => Promise<Blob> };
    capabilities?: { canEdit?: boolean; canSave?: boolean; canReadBlob?: boolean; canCloseTabs?: boolean };
    readOnly?: boolean;
    onActiveTabChange: (tabId: string | null) => void;
    onTabsChange: (tabs: Array<{ id: string; name: string; content: string }>) => void;
  }) => {
    const tab = tabs.find(item => item.id === activeTabId) ?? tabs[0];
    const [blobSummary, setBlobSummary] = React.useState('');

    React.useEffect(() => {
      if (!tab?.name.endsWith('.png')) return;
      if (!capabilities?.canReadBlob || !adapter?.readBlob) {
        setBlobSummary('missing-readBlob');
        return;
      }
      void adapter.readBlob(tab.id).then(blob => setBlobSummary(`${blob.type}:${blob.size}`));
    }, [adapter, capabilities?.canReadBlob, tab]);

    return (
      <div data-testid="file-viewer-workbench" data-readonly={readOnly ? 'true' : 'false'}>
        <div role="tablist">
          {tabs.map(item => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === activeTabId}
              onClick={() => onActiveTabChange(item.id)}
            >
              {`${item.name} tab`}
            </button>
          ))}
        </div>
        {capabilities?.canCloseTabs !== false && tabs.map(item => (
          <button
            key={`close-${item.id}`}
            type="button"
            aria-label={`close ${item.name}`}
            onClick={() => onTabsChange(tabs.filter(candidate => candidate.id !== item.id))}
          >
            close
          </button>
        ))}
        {capabilities?.canSave !== false ? (
          <button type="button" aria-label="shared.fileViewer.toolbar.save">save</button>
        ) : null}
        {tab?.name.endsWith('.png') ? (
          <div aria-label={tab.name}>{blobSummary}</div>
        ) : tab ? (
          <textarea
            aria-label={tab.name}
            readOnly={readOnly || capabilities?.canEdit === false}
            value={tab.content}
            onChange={event => onTabsChange(tabs.map(item => (
              item.id === tab.id ? { ...item, content: event.target.value } : item
            )))}
          />
        ) : null}
      </div>
    );
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
    {
      path: 'assets/logo.png',
      content: 'aGVsbG8=',
      binary: true,
      mimeType: 'image/png',
      size: 5,
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
    await user.dblClick(screen.getByText('.codex-plugin'));
    expect(screen.getAllByText('plugin.json').length).toBeGreaterThan(0);

    await user.click(screen.getByText('README.md'));

    expect(screen.getByText('# Package README')).toBeInTheDocument();
  });

  it('opens multiple package files as read-only tabs', async () => {
    const user = userEvent.setup();

    render(<MarketplaceFilesSection mode="package" detail={detail} />);

    await user.click(screen.getByText('README.md'));
    await user.dblClick(screen.getByText('.codex-plugin'));
    await user.click(screen.getAllByText('plugin.json')[0]);

    expect(screen.getByRole('tab', { name: 'README.md tab' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('tab', { name: 'plugin.json tab' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('plugin.json')).toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: 'shared.fileViewer.toolbar.save' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'README.md tab' }));
    expect(screen.getByRole('tab', { name: 'README.md tab' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('README.md')).toHaveValue('# Package README');
  });

  it('closes read-only package file tabs back to the empty state', async () => {
    const user = userEvent.setup();

    render(<MarketplaceFilesSection mode="package" detail={detail} />);

    await user.click(screen.getByText('README.md'));
    expect(screen.getByRole('tab', { name: 'README.md tab' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'close README.md' }));
    expect(screen.queryByRole('tab', { name: 'README.md tab' })).not.toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.fileManager.viewer.noFile')).toBeInTheDocument();
  });

  it('loads package image files through the shared blob image viewer', async () => {
    const user = userEvent.setup();

    render(<MarketplaceFilesSection mode="package" detail={detail} />);

    await user.dblClick(screen.getByText('assets'));
    await user.click(screen.getByText('logo.png'));

    await waitFor(() => {
      expect(screen.getByLabelText('logo.png')).toHaveTextContent('image/png:5');
    });
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
