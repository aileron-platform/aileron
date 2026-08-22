import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceDetailFilesSection } from './MarketplaceDetailFilesSection';

const apiMock = vi.hoisted(() => ({
  listPackageFilesTree: vi.fn(),
  listSkillTree: vi.fn(),
  loadPackageFile: vi.fn(),
  loadSkillFile: vi.fn(),
}));

vi.mock('../../../../marketplace/api/marketplaceApi', () => apiMock);
vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    state: { currentLanguage: 'en' },
  }),
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

describe('MarketplaceDetailFilesSection', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('loads only the package file tree when the tab mounts', async () => {
    apiMock.listPackageFilesTree.mockResolvedValueOnce([]);

    render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    await waitFor(() => expect(apiMock.listPackageFilesTree).toHaveBeenCalledWith('codex', 'review-tools'));
    expect(await screen.findByText('marketplace.editor.fileManager.viewer.noFile')).toBeInTheDocument();
    const main = screen.getByRole('main', { name: 'marketplace.detail.viewer.contentRegion' });
    expect(main.firstElementChild?.firstElementChild).toHaveClass('h-full');
    expect(apiMock.loadPackageFile).not.toHaveBeenCalled();
  });

  it('loads only the skill tree when the tab mounts', async () => {
    apiMock.listSkillTree.mockResolvedValueOnce([]);

    render(
      <MarketplaceDetailFilesSection
        mode="skills"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledWith('codex', 'review-tools'));
    expect(apiMock.loadSkillFile).not.toHaveBeenCalled();
  });

  it('retries after the file tree fails to load', async () => {
    const user = userEvent.setup();
    apiMock.listPackageFilesTree
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce([]);

    render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    expect(await screen.findByText('marketplace.common.resourceLoadError')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));

    await waitFor(() => expect(apiMock.listPackageFilesTree).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();
  }, 20_000);

  it('keeps the latest targetClient, package, and mode tree when requests resolve out of order', async () => {
    const stalePackage = deferred<unknown>();
    const currentSkills = deferred<unknown>();
    apiMock.listPackageFilesTree.mockReturnValueOnce(stalePackage.promise);
    apiMock.listSkillTree.mockReturnValueOnce(currentSkills.promise);

    const { rerender } = render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="old-package"
      />,
    );

    await waitFor(() => expect(apiMock.listPackageFilesTree).toHaveBeenCalledTimes(1));

    rerender(
      <MarketplaceDetailFilesSection
        mode="skills"
        targetClient="claude-code"
        packageId="current-package"
      />,
    );

    await waitFor(() => {
      expect(apiMock.listSkillTree).toHaveBeenCalledWith('claude-code', 'current-package');
    });
    currentSkills.resolve([{
      id: 'skills/current/SKILL.md',
      path: 'skills/current/SKILL.md',
      name: 'CURRENT.md',
      type: 'file',
    }]);
    expect(await screen.findByText('CURRENT.md')).toBeInTheDocument();

    stalePackage.resolve([{
      id: 'STALE.md',
      path: 'STALE.md',
      name: 'STALE.md',
      type: 'file',
    }]);

    await waitFor(() => {
      expect(screen.queryByText('STALE.md')).not.toBeInTheDocument();
      expect(screen.getByText('CURRENT.md')).toBeInTheDocument();
    });
  });

  it('ignores a stale tree error while the latest identity remains loading', async () => {
    const stalePackage = deferred<unknown>();
    const currentSkills = deferred<unknown>();
    apiMock.listPackageFilesTree.mockReturnValueOnce(stalePackage.promise);
    apiMock.listSkillTree.mockReturnValueOnce(currentSkills.promise);

    const { rerender } = render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );
    await waitFor(() => expect(apiMock.listPackageFilesTree).toHaveBeenCalledTimes(1));

    rerender(
      <MarketplaceDetailFilesSection
        mode="skills"
        targetClient="codex"
        packageId="review-tools"
      />,
    );
    await waitFor(() => expect(apiMock.listSkillTree).toHaveBeenCalledTimes(1));

    stalePackage.reject(new Error('stale failure'));
    expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();

    currentSkills.resolve([]);
    await waitFor(() => {
      expect(screen.queryByText('marketplace.common.resourceLoadError')).not.toBeInTheDocument();
    });
  });

  it('does not reuse same-path content after the resource identity changes', async () => {
    const user = userEvent.setup();
    const sharedNode = {
      id: 'shared.md',
      path: 'shared.md',
      name: 'shared.md',
      type: 'file',
    };
    apiMock.listPackageFilesTree.mockResolvedValueOnce([sharedNode]);
    apiMock.loadPackageFile.mockResolvedValueOnce({ content: 'package content' });
    apiMock.listSkillTree.mockResolvedValueOnce([sharedNode]);
    apiMock.loadSkillFile.mockResolvedValueOnce({ content: 'skill content' });

    const { rerender } = render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    await user.click(await screen.findByText('shared.md'));
    expect(await screen.findByText('package content')).toBeInTheDocument();

    rerender(
      <MarketplaceDetailFilesSection
        mode="skills"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    await user.click(await screen.findByText('shared.md'));
    expect(await screen.findByText('skill content')).toBeInTheDocument();
    expect(screen.queryByText('package content')).not.toBeInTheDocument();
    expect(apiMock.loadSkillFile).toHaveBeenCalledWith('codex', 'review-tools', 'shared.md');
  });

  it('deduplicates file content loading across click and double-click', async () => {
    const user = userEvent.setup();
    apiMock.listPackageFilesTree.mockResolvedValueOnce([{
      id: 'README.md',
      path: 'README.md',
      name: 'README.md',
      type: 'file',
    }]);
    apiMock.loadPackageFile.mockResolvedValueOnce({ content: '# Readme' });

    render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    const file = await screen.findByText('README.md');
    await user.dblClick(file);

    await waitFor(() => expect(apiMock.loadPackageFile).toHaveBeenCalledTimes(1));
  }, 20_000);

  it('builds a nested tree so folders can hide and reveal descendants', async () => {
    const user = userEvent.setup();
    apiMock.listPackageFilesTree.mockResolvedValueOnce({
      path: '',
      nodes: [
        {
          id: 'skills',
          path: 'skills',
          name: 'skills',
          type: 'directory',
        },
        {
          id: 'skills/review-skill',
          path: 'skills/review-skill',
          name: 'review-skill',
          type: 'directory',
        },
        {
          id: 'skills/review-skill/SKILL.md',
          path: 'skills/review-skill/SKILL.md',
          name: 'SKILL.md',
          type: 'file',
        },
      ],
      total: 3,
    });

    render(
      <MarketplaceDetailFilesSection
        mode="package"
        targetClient="codex"
        packageId="review-tools"
      />,
    );

    const skillsFolder = await screen.findByTitle('skills');
    expect(screen.queryByText('review-skill')).not.toBeInTheDocument();

    await user.click(skillsFolder);
    expect(await screen.findByText('review-skill')).toBeInTheDocument();

    await user.click(skillsFolder);
    expect(screen.queryByText('review-skill')).not.toBeInTheDocument();
  });
});
