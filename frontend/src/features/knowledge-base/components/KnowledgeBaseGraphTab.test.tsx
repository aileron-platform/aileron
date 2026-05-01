import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseGraphTab } from './KnowledgeBaseGraphTab';

type SigmaEvents = {
  clickNode?: (event: { node: string }) => void;
};

const apiMocks = vi.hoisted(() => ({
  getKnowledgeBaseGraph: vi.fn(),
}));
const translateMock = vi.hoisted(() => vi.fn((key: string) => key));
const sigmaEvents = vi.hoisted(() => ({ current: {} as SigmaEvents }));
const cameraMock = vi.hoisted(() => ({
  reset: vi.fn(),
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
  gotoNode: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@react-sigma/core', () => ({
  SigmaContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="wiki-graph-canvas">{children}</div>,
  useLoadGraph: () => vi.fn(),
  useRegisterEvents: () => (events: SigmaEvents) => {
    sigmaEvents.current = events;
  },
  useCamera: () => cameraMock,
}));

vi.mock('@/shared/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/shared/components/ui/scroll-area', () => ({
  ScrollArea: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
}));

vi.mock('@/shared/components/wiki-page-preview', () => ({
  WikiPagePreview: ({ path, onNavigate }: {
    path: string;
    onNavigate: (path: string) => void;
  }) => (
    <div data-testid="wiki-preview">
      <span>{path}</span>
      <button type="button" onClick={() => onNavigate('wiki/overview.md')}>preview wikilink</button>
    </div>
  ),
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  getKnowledgeBaseGraph: apiMocks.getKnowledgeBaseGraph,
}));

const graph = {
  kbId: 'kb-1',
  generatedAt: '2026-05-01T00:00:00Z',
  nodes: [
    { id: 'wiki/overview', label: 'Overview', path: 'wiki/overview.md', type: 'overview', sources: [], outboundCount: 0, inboundCount: 1, degree: 1 },
    { id: 'wiki/guide', label: 'Guide', path: 'wiki/guide.md', type: 'concept', sources: [], outboundCount: 1, inboundCount: 0, degree: 1 },
  ],
  edges: [{ id: 'edge-1', source: 'wiki/overview', target: 'wiki/guide', weight: 1, reasons: [] }],
};

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}{location.search}</div>;
};

const renderGraphTab = (initialPath = '/knowledge-bases/kb-1/graph') => render(
  <MemoryRouter initialEntries={[initialPath]}>
    <Routes>
      <Route
        path="/knowledge-bases/:id/graph"
        element={(
          <>
            <LocationProbe />
            <KnowledgeBaseGraphTab knowledgeBaseId="kb-1" />
          </>
        )}
      />
      <Route path="/knowledge-bases/:id/wiki" element={<LocationProbe />} />
      <Route path="/knowledge-bases/:id/files" element={<LocationProbe />} />
    </Routes>
  </MemoryRouter>,
);

describe('KnowledgeBaseGraphTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sigmaEvents.current = {};
    translateMock.mockImplementation((key: string) => key);
    apiMocks.getKnowledgeBaseGraph.mockResolvedValue(graph);
  });

  it('renders graph tab with node list, canvas, and preview panes', async () => {
    renderGraphTab();

    expect(await screen.findAllByTestId('wiki-graph-canvas')).not.toHaveLength(0);
    expect(screen.getByTestId('kb-graph-nodes')).toBeInTheDocument();
    expect(screen.getByTestId('kb-graph-canvas')).toBeInTheDocument();
    expect(screen.getByTestId('kb-graph-preview')).toBeInTheDocument();
    expect(within(screen.getByTestId('kb-graph-canvas')).getByRole('textbox', {
      name: 'knowledgeBase.graph.search.label',
    })).toBeInTheDocument();
    expect(within(screen.getByTestId('kb-graph-canvas')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.fit',
    })).toBeInTheDocument();
    expect(screen.getAllByTestId('wiki-preview')[0]).toHaveTextContent('wiki/overview.md');
  });

  it('fits the graph to the canvas by default', async () => {
    renderGraphTab();
    await screen.findAllByTestId('wiki-graph-canvas');

    await waitFor(() => {
      expect(cameraMock.reset).toHaveBeenCalled();
    });
    expect(cameraMock.gotoNode).not.toHaveBeenCalledWith('wiki/overview');
  });

  it('selects graph nodes and updates the preview URL state', async () => {
    renderGraphTab();
    await screen.findByText('Guide');

    act(() => {
      sigmaEvents.current.clickNode?.({ node: 'wiki/guide' });
    });

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('path=wiki%2Fguide.md');
      expect(screen.getAllByTestId('wiki-preview')[0]).toHaveTextContent('wiki/guide.md');
    });
  });

  it('selects node list items and updates graph selection', async () => {
    const user = userEvent.setup();
    renderGraphTab();
    await user.click(await screen.findByRole('button', { name: /Guide/ }));

    expect(screen.getByTestId('location')).toHaveTextContent('path=wiki%2Fguide.md');
    expect(screen.getAllByTestId('wiki-preview')[0]).toHaveTextContent('wiki/guide.md');
  });

  it('opens the selected preview page in wiki from the preview header', async () => {
    const user = userEvent.setup();
    renderGraphTab();
    await user.click(await screen.findByRole('button', { name: /Guide/ }));

    await user.click(within(screen.getByTestId('kb-graph-preview')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.openInWiki',
    }));

    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/wiki?path=wiki%2Fguide.md');
  });

  it('restores persisted pane sizes from local storage and persists changes', async () => {
    localStorage.setItem('knowledge-base-graph-layout:kb-1', JSON.stringify({
      leftWidth: 300,
      rightWidth: 360,
      leftCollapsed: false,
      rightCollapsed: false,
    }));
    renderGraphTab();
    await screen.findAllByTestId('wiki-graph-canvas');

    expect(screen.getByTestId('kb-graph-nodes')).toHaveStyle({ width: '300px' });
    expect(screen.getByTestId('kb-graph-preview')).toHaveStyle({ width: '360px' });

    await waitFor(() => {
      const stored = localStorage.getItem('knowledge-base-graph-layout:kb-1');
      expect(stored).toContain('"leftWidth":300');
      expect(stored).toContain('"rightWidth":360');
    });
  });

  it('renders graph panes with the shared default column widths', async () => {
    renderGraphTab();
    await screen.findAllByTestId('wiki-graph-canvas');

    expect(screen.getByTestId('kb-graph-nodes')).toHaveStyle({ width: '256px' });
    expect(screen.getByTestId('kb-graph-preview')).toHaveStyle({ width: '400px' });
    expect(screen.getByTestId('kb-graph-canvas')).toBeInTheDocument();
  });

  it('places collapse controls in graph pane headers', async () => {
    const user = userEvent.setup();
    renderGraphTab();
    await screen.findAllByTestId('wiki-graph-canvas');

    await user.click(within(screen.getByTestId('kb-graph-nodes')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.hideNodes',
    }));
    expect(within(screen.getByTestId('kb-graph-nodes')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.showNodes',
    })).toBeInTheDocument();

    await user.click(within(screen.getByTestId('kb-graph-preview')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.hidePreview',
    }));
    expect(within(screen.getByTestId('kb-graph-preview')).getByRole('button', {
      name: 'knowledgeBase.graph.actions.showPreview',
    })).toBeInTheDocument();
  });

});
