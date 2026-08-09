import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import {
  MarketplaceFileResourcePage,
  runMarketplaceUploadBatch,
} from './MarketplaceFileResourcePage';

const apiMock = vi.hoisted(() => ({
  listSkillTree: vi.fn(),
  loadSkillFile: vi.fn(),
  saveSkillFile: vi.fn(),
  createSkillEntry: vi.fn(),
  deleteSkillEntry: vi.fn(),
  moveSkillEntry: vi.fn(),
  listPackageFilesTree: vi.fn(),
  loadPackageFile: vi.fn(),
  savePackageFile: vi.fn(),
  createPackageFileEntry: vi.fn(),
  deletePackageFileEntry: vi.fn(),
  movePackageFileEntry: vi.fn(),
  getPackage: vi.fn(),
}));
const fileConflictStartMock = vi.hoisted(() => vi.fn());
const fileConflictControllerOptionsMock = vi.hoisted(() => vi.fn());
const queryClientMock = vi.hoisted(() => ({
  getQueryCache: vi.fn(() => ({ findAll: () => [] })),
  invalidateQueries: vi.fn(),
  refetchQueries: vi.fn(),
}));

vi.mock('@tanstack/react-query', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@tanstack/react-query')>()),
  useQueryClient: () => queryClientMock,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    state: { currentLanguage: 'en' },
  }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  listSkillTree: (...args: unknown[]) => apiMock.listSkillTree(...args),
  loadSkillFile: (...args: unknown[]) => apiMock.loadSkillFile(...args),
  saveSkillFile: (...args: unknown[]) => apiMock.saveSkillFile(...args),
  createSkillEntry: (...args: unknown[]) => apiMock.createSkillEntry(...args),
  deleteSkillEntry: (...args: unknown[]) => apiMock.deleteSkillEntry(...args),
  moveSkillEntry: (...args: unknown[]) => apiMock.moveSkillEntry(...args),
  listPackageFilesTree: (...args: unknown[]) => apiMock.listPackageFilesTree(...args),
  loadPackageFile: (...args: unknown[]) => apiMock.loadPackageFile(...args),
  savePackageFile: (...args: unknown[]) => apiMock.savePackageFile(...args),
  createPackageFileEntry: (...args: unknown[]) => apiMock.createPackageFileEntry(...args),
  deletePackageFileEntry: (...args: unknown[]) => apiMock.deletePackageFileEntry(...args),
  movePackageFileEntry: (...args: unknown[]) => apiMock.movePackageFileEntry(...args),
  getPackage: (...args: unknown[]) => apiMock.getPackage(...args),
}));

vi.mock('@/shared/components/file-workbench', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/file-workbench')>();
  return {
    ...actual,
    FileConflictDialog: () => null,
    useFileConflictController: (options: unknown) => {
      fileConflictControllerOptionsMock(options);
      return {
        open: false, pending: false, operation: null, conflicts: [], defaultStrategy: 'keep-both', itemStrategies: {}, error: null,
        start: fileConflictStartMock, setDefaultStrategy: vi.fn(), setItemStrategy: vi.fn(), cancel: vi.fn(), confirm: vi.fn(),
      };
    },
  };
});

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: {
    value?: string;
    onChange?: (value: string) => void;
  }) => (
    <textarea
      aria-label="code-editor"
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
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
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const buildPackageDetail = (
  overrides: Partial<MarketplacePackageDetail> = {},
): MarketplacePackageDetail => ({
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'codex-toolkit',
  displayName: 'Codex Toolkit',
  version: '0.1.0',
  description: 'Package description',
  category: 'coding',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  lifecycleStatus: 'draft',
  registryPath: 'codex/plugins/codex-toolkit',
  revision: 'rev1',
  updatedAt: '2026-06-26T00:00:00.000Z',
  variants: [],
  catalogMetadata: {},
  manifestMetadata: {},
  validationResults: [],
  ...overrides,
});

const mutationResult = (
  path: string,
  revision = 'rev2',
) => ({
  success: true as const,
  path,
  revision,
  ownerFilePath: null,
  baseEntryFingerprint: null,
});

describe('runMarketplaceUploadBatch', () => {
  it('chains revisions directly from each canonical upload result', async () => {
    const files = [new File(['a'], 'a.txt'), new File(['b'], 'b.txt')];
    const upload = vi.fn()
      .mockResolvedValueOnce(mutationResult('a.txt', 'rev2'))
      .mockResolvedValueOnce(mutationResult('b.txt', 'rev3'));

    const result = await runMarketplaceUploadBatch({
      files,
      initialRevision: 'rev1',
      upload,
    });

    expect(upload).toHaveBeenNthCalledWith(1, files[0], 'rev1');
    expect(upload).toHaveBeenNthCalledWith(2, files[1], 'rev2');
    expect(result).toEqual(mutationResult('b.txt', 'rev3'));
  });
});

describe('MarketplaceFileResourcePage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiMock.getPackage.mockResolvedValue(buildPackageDetail({ revision: 'rev2' }));
    apiMock.listSkillTree.mockResolvedValue({
      path: 'skills',
      nodes: [
        { id: 'skills/example/SKILL.md', path: 'skills/example/SKILL.md', name: 'SKILL.md', type: 'file' },
      ],
      total: 1,
    });
    apiMock.loadSkillFile.mockResolvedValue({
      path: 'skills/example/SKILL.md',
      name: 'SKILL.md',
      content: '# Original skill',
    });
    apiMock.listPackageFilesTree.mockResolvedValue({
      path: '',
      nodes: [
        { id: 'README.md', path: 'README.md', name: 'README.md', type: 'file' },
      ],
      total: 1,
    });
    apiMock.loadPackageFile.mockResolvedValue({
      path: 'README.md',
      name: 'README.md',
      content: '# Original readme',
    });
  });

  it('retries after the initial file tree fails to load', async () => {
    const user = userEvent.setup();
    apiMock.listSkillTree
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce({
        path: 'skills',
        nodes: [],
        total: 0,
      });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    expect(await screen.findByText('marketplace.common.resourceLoadError')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));

    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();
  }, 20_000);

  it('keeps the last file tree snapshot when a refresh fails', async () => {
    const user = userEvent.setup();
    apiMock.listPackageFilesTree
      .mockResolvedValueOnce({
        path: '',
        nodes: [
          { id: 'README.md', path: 'README.md', name: 'README.md', type: 'file' },
        ],
        total: 1,
      })
      .mockRejectedValueOnce(new Error('refresh unavailable'))
      .mockResolvedValueOnce({
        path: '',
        nodes: [
          { id: 'README.md', path: 'README.md', name: 'README.md', type: 'file' },
        ],
        total: 1,
      });

    render(
      <MarketplaceFileResourcePage
        title="Files"
        resourceType="files"
        packageDetail={buildPackageDetail()}
        onMutation={vi.fn()}
      />,
    );

    expect((await screen.findAllByText('README.md')).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'common.fileTree.contextMenu.refresh' }));

    expect(await screen.findByText('marketplace.common.resourceSyncError')).toBeInTheDocument();
    expect((await screen.findAllByText('README.md')).length).toBeGreaterThan(0);
    expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));
    await waitFor(() => expect(apiMock.listPackageFilesTree).toHaveBeenCalledTimes(3));
    expect(screen.queryByText('marketplace.common.resourceSyncError')).not.toBeInTheDocument();
  });

  it('ignores stale tree error and loading completion after the resource identity changes', async () => {
    const staleSkills = deferred<unknown>();
    const currentFiles = deferred<unknown>();
    apiMock.listSkillTree.mockReturnValueOnce(staleSkills.promise);
    apiMock.listPackageFilesTree.mockReturnValueOnce(currentFiles.promise);

    const { rerender } = render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(1));

    rerender(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail({
              provider: 'claude-code',
              packageId: 'claude-toolkit',
            })}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    await waitFor(() => {
      expect(apiMock.listPackageFilesTree)
        .toHaveBeenCalledWith('claude-code', 'claude-toolkit');
    });
    staleSkills.reject(new Error('stale failure'));

    expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();
    expect(screen.getByText('marketplace.common.loading')).toBeInTheDocument();

    currentFiles.resolve({
      path: '',
      nodes: [
        { id: 'CURRENT.md', path: 'CURRENT.md', name: 'CURRENT.md', type: 'file' },
      ],
      total: 1,
    });

    expect((await screen.findAllByText('CURRENT.md')).length).toBeGreaterThan(0);
    expect(screen.queryByText('SKILL.md')).not.toBeInTheDocument();
  });

  it('ignores a stale tree success after the latest identity has loaded', async () => {
    const staleSkills = deferred<unknown>();
    apiMock.listSkillTree.mockReturnValueOnce(staleSkills.promise);
    apiMock.listPackageFilesTree.mockResolvedValueOnce({
      path: '',
      nodes: [
        { id: 'CURRENT.md', path: 'CURRENT.md', name: 'CURRENT.md', type: 'file' },
      ],
      total: 1,
    });

    const { rerender } = render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );
    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(1));

    rerender(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );
    expect((await screen.findAllByText('CURRENT.md')).length).toBeGreaterThan(0);

    staleSkills.resolve({
      path: 'skills',
      nodes: [
        {
          id: 'skills/stale/SKILL.md',
          path: 'skills/stale/SKILL.md',
          name: 'STALE.md',
          type: 'file',
        },
      ],
      total: 1,
    });

    await waitFor(() => {
      expect(screen.queryByText('STALE.md')).not.toBeInTheDocument();
      expect(screen.getAllByText('CURRENT.md').length).toBeGreaterThan(0);
    });
  });

  it('does not reuse same-path content or tabs across resource identities', async () => {
    const user = userEvent.setup();
    const sharedNode = {
      id: 'skills/shared/SKILL.md',
      path: 'skills/shared/SKILL.md',
      name: 'SKILL.md',
      type: 'file',
    };
    apiMock.listSkillTree.mockResolvedValueOnce({
      path: 'skills',
      nodes: [sharedNode],
      total: 1,
    });
    apiMock.loadSkillFile.mockResolvedValue({
      path: 'skills/shared/SKILL.md',
      name: 'SKILL.md',
      content: 'skill content',
    });
    apiMock.listPackageFilesTree.mockResolvedValueOnce({
      path: '',
      nodes: [sharedNode],
      total: 1,
    });
    apiMock.loadPackageFile.mockResolvedValue({
      path: 'skills/shared/SKILL.md',
      name: 'SKILL.md',
      content: 'package content',
    });

    const { rerender } = render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    await user.click((await screen.findAllByText('SKILL.md', {}, { timeout: 20_000 }))[0]);
    expect(await screen.findByText('skill content', {}, { timeout: 20_000 })).toBeInTheDocument();

    rerender(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    await user.click((await screen.findAllByText('SKILL.md', {}, { timeout: 20_000 }))[0]);
    await waitFor(() => {
      expect(apiMock.loadPackageFile)
        .toHaveBeenCalledWith('codex', 'codex-toolkit', 'skills/shared/SKILL.md');
      expect(screen.getByText('package content')).toBeInTheDocument();
    }, { timeout: 20_000 });
    expect(screen.queryByText('skill content')).not.toBeInTheDocument();
  }, 30_000);

  it('loads and saves a skill file through package-scoped resource endpoints', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    const result = mutationResult('skills/example/SKILL.md');
    apiMock.saveSkillFile.mockResolvedValue(result);

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    expect(screen.getByRole('complementary', { name: 'Skills' })).toHaveStyle({ width: '270px' });
    await user.click((await screen.findAllByText('SKILL.md'))[0]);
    expect((await screen.findAllByText('SKILL.md')).length).toBeGreaterThanOrEqual(2);
    await user.click(await screen.findByRole('button', { name: 'shared.fileViewer.markdown.edit' }));
    const editor = await screen.findByPlaceholderText('shared.fileViewer.markdown.editPlaceholder');
    await user.clear(editor);
    await user.type(editor, '# Updated skill');
    await user.click(screen.getByRole('button', { name: 'shared.fileViewer.markdown.save' }));

    await waitFor(() => {
      expect(apiMock.saveSkillFile).toHaveBeenCalledWith(
        'codex',
        'codex-toolkit',
        'skills/example/SKILL.md',
        { revision: 'rev1', content: '# Updated skill' },
      );
    });
    expect(onMutation).toHaveBeenCalledWith(result);
  });

  it('persists content entered into an empty YAML file after closing and reopening its tab', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.listSkillTree.mockResolvedValue({
      path: 'skills',
      nodes: [
        {
          id: 'skills/example/agents/openai.yaml',
          path: 'skills/example/agents/openai.yaml',
          name: 'openai.yaml',
          type: 'file',
        },
      ],
      total: 1,
    });
    apiMock.loadSkillFile.mockResolvedValue({
      path: 'skills/example/agents/openai.yaml',
      name: 'openai.yaml',
      content: '',
    });
    apiMock.saveSkillFile.mockResolvedValue(
      mutationResult('skills/example/agents/openai.yaml'),
    );

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    const editor = await screen.findByLabelText('code-editor');
    await user.type(editor, 'name: openai');
    await user.click(screen.getByRole('button', { name: 'shared.fileViewer.toolbar.save' }));

    await waitFor(() => {
      expect(apiMock.saveSkillFile).toHaveBeenCalledWith(
        'codex',
        'codex-toolkit',
        'skills/example/agents/openai.yaml',
        { revision: 'rev1', content: 'name: openai' },
      );
    });

    await user.click(screen.getByRole('button', { name: 'shared.fileViewer.tabs.close' }));
    await user.click((await screen.findAllByText('openai.yaml'))[0]);

    expect(await screen.findByLabelText('code-editor')).toHaveValue('name: openai');
  });

  it('resizes and collapses the shared file tree second column', async () => {
    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    expect((await screen.findAllByText('SKILL.md')).length).toBeGreaterThanOrEqual(1);
    const column = screen.getByRole('complementary', { name: 'Skills' });

    fireEvent.mouseDown(screen.getByRole('separator'), { clientX: 270 });
    fireEvent.mouseMove(document, { clientX: 370 });
    fireEvent.mouseUp(document);

    expect(column).toHaveStyle({ width: '370px' });

    fireEvent.click(screen.getByRole('button', { name: 'shared.shell.collapseSidebar' }));

    expect(column).toHaveStyle({ width: '64px' });
    expect(screen.queryByPlaceholderText('marketplace.editor.fileManager.search.placeholder')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'shared.shell.expandSidebar' }));

    expect(screen.getByPlaceholderText('marketplace.editor.fileManager.search.placeholder')).toBeInTheDocument();
  });

  it('restores the package file workbench UI while saving through package file endpoints', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    const result = mutationResult('README.md');
    apiMock.savePackageFile.mockResolvedValue(result);

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    await user.click((await screen.findAllByText('README.md'))[0]);
    expect((await screen.findAllByText('README.md')).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByLabelText('marketplace.editor.fileResources.editorPlaceholder')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'common.fileTree.contextMenu.refresh' }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('marketplace.editor.fileManager.search.placeholder'),
    ).toBeInTheDocument();

    await user.click(await screen.findByRole('button', { name: 'shared.fileViewer.markdown.edit' }));
    const editor = await screen.findByPlaceholderText('shared.fileViewer.markdown.editPlaceholder');
    await user.clear(editor);
    await user.type(editor, '# Updated readme');
    await user.click(screen.getByRole('button', { name: 'shared.fileViewer.markdown.save' }));

    await waitFor(() => {
      expect(apiMock.savePackageFile).toHaveBeenCalledWith(
        'codex',
        'codex-toolkit',
        'README.md',
        { revision: 'rev1', content: '# Updated readme' },
      );
    });
    expect(onMutation).toHaveBeenCalledWith(result);
  });

  it('shows every package file, including managed dotfiles, in the files tree', async () => {
    apiMock.listPackageFilesTree.mockResolvedValue({
      path: '',
      nodes: [
        { id: '.claude-plugin', path: '.claude-plugin', name: '.claude-plugin', type: 'directory' },
        { id: '.claude-plugin/plugin.json', path: '.claude-plugin/plugin.json', name: 'plugin.json', type: 'file' },
        { id: '.mcp.json', path: '.mcp.json', name: '.mcp.json', type: 'file' },
        { id: 'README.md', path: 'README.md', name: 'README.md', type: 'file' },
      ],
      total: 4,
    });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    expect((await screen.findAllByText('.mcp.json', {}, { timeout: 20_000 })).length)
      .toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText('.claude-plugin', {}, { timeout: 20_000 })).length)
      .toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText('README.md', {}, { timeout: 20_000 })).length)
      .toBeGreaterThanOrEqual(1);
  }, 30_000);

  it('does not try to load content for an empty directory entry', async () => {
    const user = userEvent.setup();
    apiMock.listSkillTree.mockResolvedValue({
      path: 'skills',
      nodes: [
        { id: 'skills/example', path: 'skills/example', name: 'example', type: 'directory' },
      ],
      total: 1,
    });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    await user.click(await screen.findByText('example'));

    await waitFor(() => {
      expect(apiMock.loadSkillFile).not.toHaveBeenCalledWith(
        'codex',
        'codex-toolkit',
        'skills/example',
      );
    });
    const emptyTitle = await screen.findByText(
      'marketplace.editor.fileResources.directorySelected',
    );
    expect(emptyTitle).toBeInTheDocument();
    expect(emptyTitle.parentElement?.querySelector('svg')).toBeInTheDocument();
  });

  it('renames a skill entry through the shared context-menu dialog', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn();
    const promptSpy = vi.spyOn(window, 'prompt');

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    fireEvent.contextMenu((await screen.findAllByText('SKILL.md'))[0], {
      clientX: 120,
      clientY: 160,
    });
    await user.click(await screen.findByText('common.fileTree.contextMenu.rename'));
    const nameInput = screen.getByLabelText('common.fileOperations.rename.nameLabel');
    await user.clear(nameInput);
    await user.type(nameInput, 'RENAMED.md');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    await waitFor(() => {
      expect(fileConflictStartMock).toHaveBeenCalledWith({
        operation: 'move',
        targetPath: 'skills/example/RENAMED.md',
        sources: [{
          sourcePath: 'skills/example/SKILL.md',
          entryType: 'file',
        }],
        archivePath: null,
      }, {
        files: [],
        sourcePath: 'skills/example/SKILL.md',
        entryType: 'file',
      });
    });
    expect(apiMock.moveSkillEntry).not.toHaveBeenCalled();
    expect(apiMock.createSkillEntry).not.toHaveBeenCalled();
    expect(apiMock.deleteSkillEntry).not.toHaveBeenCalled();
    expect(onMutation).not.toHaveBeenCalled();
    expect(promptSpy).not.toHaveBeenCalled();

    promptSpy.mockRestore();
  });

  it('routes skill ZIP extraction through the shared conflict controller', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.listSkillTree.mockResolvedValue({
      path: 'skills',
      nodes: [
        {
          id: 'skills/example/archive.zip',
          path: 'skills/example/archive.zip',
          name: 'archive.zip',
          type: 'file',
        },
      ],
      total: 1,
    });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(1));
    fireEvent.contextMenu((await screen.findAllByText(
      'archive.zip',
      {},
      { timeout: 10_000 },
    ))[0], {
      clientX: 120,
      clientY: 160,
    });
    await user.click(await screen.findByText('common.fileTree.contextMenu.extractArchive'));

    await waitFor(() => {
      expect(fileConflictStartMock).toHaveBeenCalledWith({
        operation: 'extract',
        archivePath: 'skills/example/archive.zip',
        targetPath: 'skills/example',
        sources: null,
      }, { revision: 'rev1' });
    });
    expect(onMutation).not.toHaveBeenCalled();
  });

  it('keeps the current marketplace selection when a conflict batch partially fails', async () => {
    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );
    expect((await screen.findAllByText('SKILL.md')).length).toBeGreaterThan(0);
    const options = fileConflictControllerOptionsMock.mock.calls.at(-1)?.[0];
    await options.onCompleted({
      items: [{ sourcePath: 'ok.md', finalPath: 'skills/new.md', status: 'created', size: 1, type: 'file', error: null }, { sourcePath: 'failed.md', finalPath: null, status: 'failed', size: 0, type: 'file', error: 'failed' }],
      total: 2, succeeded: 1, skipped: 0, failed: 1,
    });
    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(2));
    expect(apiMock.loadSkillFile).not.toHaveBeenCalledWith('codex', 'codex-toolkit', 'skills/new.md');
  });

  it('refreshes the package revision and resource views after a skill execute error', async () => {
    const onMutation = vi.fn().mockResolvedValue(undefined);
    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );
    expect((await screen.findAllByText('SKILL.md')).length).toBeGreaterThan(0);

    const options = fileConflictControllerOptionsMock.mock.calls.at(-1)?.[0];
    options.onError(new Error('connection lost'), 'execute');

    await waitFor(() => expect(apiMock.getPackage).toHaveBeenCalledWith('codex', 'codex-toolkit'));
    await waitFor(() => expect(onMutation).toHaveBeenCalledWith(expect.objectContaining({
      success: true,
      revision: 'rev2',
    })));
    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(2));
  });

  it('does not reload deleted skill content while refreshing the tree', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.deleteSkillEntry.mockResolvedValue(
      mutationResult('skills/example/SKILL.md'),
    );
    apiMock.listSkillTree
      .mockResolvedValueOnce({
        path: 'skills',
        nodes: [
          {
            id: 'skills/example/SKILL.md',
            path: 'skills/example/SKILL.md',
            name: 'SKILL.md',
            type: 'file',
          },
        ],
        total: 1,
      })
      .mockResolvedValue({
        path: 'skills',
        nodes: [],
        total: 0,
      });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Skills"
            resourceType="skills"
            packageDetail={buildPackageDetail()}
            onMutation={onMutation}
          />
        </div>
      </>,
    );

    await waitFor(() => expect(apiMock.loadSkillFile).toHaveBeenCalledTimes(1));
    fireEvent.contextMenu((await screen.findAllByText('SKILL.md'))[0], {
      clientX: 120,
      clientY: 160,
    });
    await user.click(await screen.findByText('common.fileTree.contextMenu.delete'));
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.delete' }));

    await waitFor(() => expect(apiMock.deleteSkillEntry).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(2));
    expect(apiMock.loadSkillFile).toHaveBeenCalledTimes(1);
  });

  it('keeps managed roots readonly in the files context menu', async () => {
    apiMock.listPackageFilesTree.mockResolvedValue({
      path: '',
      nodes: [
        { id: '.mcp.json', path: '.mcp.json', name: '.mcp.json', type: 'file' },
        { id: 'docs', path: 'docs', name: 'docs', type: 'directory' },
      ],
      total: 2,
    });

    render(
      <>
        <div className="flex h-full">
          <MarketplaceFileResourcePage
            title="Files"
            resourceType="files"
            packageDetail={buildPackageDetail()}
            onMutation={vi.fn()}
          />
        </div>
      </>,
    );

    fireEvent.contextMenu((await screen.findAllByText('.mcp.json'))[0], {
      clientX: 120,
      clientY: 160,
    });

    expect(await screen.findByText('common.fileTree.contextMenu.copyPath')).toBeInTheDocument();
    expect(screen.queryByText('common.fileTree.contextMenu.rename')).not.toBeInTheDocument();
    expect(screen.queryByText('common.fileTree.contextMenu.delete')).not.toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    fireEvent.contextMenu(await screen.findByText('docs'), {
      clientX: 120,
      clientY: 160,
    });

    expect(await screen.findByText('common.fileTree.contextMenu.rename')).toBeInTheDocument();
    expect(screen.getByText('common.fileTree.contextMenu.delete')).toBeInTheDocument();
    expect(screen.getByText('common.fileTree.contextMenu.upload')).toBeInTheDocument();
  });
});
