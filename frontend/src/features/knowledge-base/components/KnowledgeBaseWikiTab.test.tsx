import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseWikiTab } from './KnowledgeBaseWikiTab';

const apiMocks = vi.hoisted(() => ({
  listKnowledgeBaseWikiPages: vi.fn(),
  createKnowledgeBaseIngestJob: vi.fn(),
}));
const translateMock = vi.hoisted(() => vi.fn((key: string, values?: { defaultValue?: string }) => values?.defaultValue ?? key));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/shared/components/wiki-page-preview', () => ({
  WikiPagePreview: ({ path, onNavigate, onSourceOpen }: {
    path: string;
    onNavigate: (path: string) => void;
    onSourceOpen: (path: string) => void;
  }) => (
    <div data-testid="wiki-preview">
      <span>{path}</span>
      <button type="button" onClick={() => onNavigate('wiki/guide.md')}>navigate wikilink</button>
      <button type="button" onClick={() => onSourceOpen('raw/sources/source.md')}>open source</button>
    </div>
  ),
}));

vi.mock('./wiki/IssuesSection', () => ({
  IssuesSection: () => <div data-testid="wiki-issues" />,
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  listKnowledgeBaseWikiPages: apiMocks.listKnowledgeBaseWikiPages,
  createKnowledgeBaseIngestJob: apiMocks.createKnowledgeBaseIngestJob,
}));

const wikiPages = {
  groups: [{
    type: 'overview',
    labelKey: 'knowledgeBase.wiki.types.overview',
    items: [
      {
        path: 'wiki/overview.md',
        title: 'Overview',
        type: 'overview',
        tags: [],
        origin: null,
        description: null,
      },
      {
        path: 'wiki/guide.md',
        title: 'Guide',
        type: 'overview',
        tags: [],
        origin: null,
        description: null,
      },
    ],
  }],
};

const emptyWikiPages = {
  groups: [{
    type: 'overview',
    labelKey: 'knowledgeBase.wiki.types.overview',
    items: [{
      path: 'wiki/overview.md',
      title: 'Overview',
      type: 'overview',
      tags: [],
      origin: null,
      description: null,
    }],
  }],
};

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}{location.search}</div>;
};

const renderWikiTab = (initialPath = '/knowledge-bases/kb-1/wiki') => render(
  <MemoryRouter initialEntries={[initialPath]}>
    <Routes>
      <Route
        path="/knowledge-bases/:id/wiki"
        element={(
          <>
            <LocationProbe />
            <KnowledgeBaseWikiTab knowledgeBaseId="kb-1" />
          </>
        )}
      />
      <Route path="/knowledge-bases/:id/files" element={<LocationProbe />} />
      <Route path="/knowledge-bases/:id/schedules" element={<LocationProbe />} />
    </Routes>
  </MemoryRouter>,
);

describe('KnowledgeBaseWikiTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    translateMock.mockImplementation((key: string, values?: { defaultValue?: string }) => values?.defaultValue ?? key);
    apiMocks.listKnowledgeBaseWikiPages.mockResolvedValue(wikiPages);
    apiMocks.createKnowledgeBaseIngestJob.mockResolvedValue({ id: 'job-1' });
  });

  it('initializes URL state and keeps wiki as a document-only view', async () => {
    const user = userEvent.setup();
    renderWikiTab();

    await screen.findByText('Overview');
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/wiki?path=wiki%2Foverview.md');
    });

    await user.click(screen.getByRole('button', { name: /Guide/ }));
    expect(screen.getByTestId('location')).toHaveTextContent('path=wiki%2Fguide.md');
    expect(screen.queryByTestId('wiki-graph-canvas')).not.toBeInTheDocument();
  });

  it('renders the wiki navigation column with the shared default width and a resize handle', async () => {
    renderWikiTab();

    await screen.findByText('Overview');

    expect(screen.getByTestId('wiki-panel-group')).toBeInTheDocument();
    const navigation = screen.getByTestId('kb-wiki-navigation');
    expect(navigation).toHaveStyle({ width: '256px' });
    expect(screen.getByTestId('kb-wiki-preview')).toBeInTheDocument();
    expect(screen.getByRole('separator', { hidden: true })).toBeInTheDocument();
  });

  it('collapses and expands the wiki navigation column from the header', async () => {
    const user = userEvent.setup();
    renderWikiTab();

    await screen.findByText('Overview');

    await user.click(screen.getByRole('button', { name: 'workspace.layout.collapseSidebar' }));
    expect(screen.queryByText('Overview')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'workspace.layout.expandSidebar' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.layout.expandSidebar' }));
    expect(screen.getByText('Overview')).toBeInTheDocument();
  });

  it('runs ingest from the empty wiki onboarding flow and refreshes pages', async () => {
    const user = userEvent.setup();
    apiMocks.listKnowledgeBaseWikiPages.mockResolvedValue(emptyWikiPages);
    renderWikiTab();

    await user.click(await screen.findByRole('button', { name: 'knowledgeBase.wiki.empty.runIngest' }));

    await waitFor(() => {
      expect(apiMocks.createKnowledgeBaseIngestJob).toHaveBeenCalledWith('kb-1');
      expect(apiMocks.listKnowledgeBaseWikiPages).toHaveBeenCalledTimes(2);
    });
  });
});
